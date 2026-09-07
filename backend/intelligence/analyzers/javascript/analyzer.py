"""
JavaScript / TypeScript Language Analyzer Adapter.
Tool chain: ESLint → tsc → npm audit → regex fallback

Migrated from intelligence/static_analysis/javascript_analyzer.py.
Output is now normalized CodeQualityEvidence instead of a JS-specific dict.
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelligence.analyzers.base import BaseAnalyzer
from intelligence.analyzers.common.complexity import analyze_complexity
from intelligence.analyzers.common.duplication import analyze_duplication
from intelligence.analyzers.common.secrets_scanner import scan_secrets
from intelligence.evidence.models import (
    CodeQualityEvidence,
    Finding,
    SecurityEvidence,
    SeverityEnum,
    TestingEvidence,
)


async def _run(cmd: List[str], cwd: Optional[str] = None) -> Optional[str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        return stdout.decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return None


class JavaScriptAnalyzer(BaseAnalyzer):
    """
    JavaScript and TypeScript adapter.
    Handles .js, .jsx, .ts, .tsx, .mjs files.

    Reuses and normalizes the existing ESLint + tsc + npm audit logic.
    """

    language = "javascript"
    supported_extensions = [".js", ".jsx", ".ts", ".tsx", ".mjs"]

    async def analyze(
        self,
        changed_files: List[str],
        repo_path: str,
        pr_context: dict,
    ) -> CodeQualityEvidence:
        import time
        start = time.monotonic()

        evidence = self._empty_evidence(repo_path, pr_context)
        evidence.primary_language = (
            "typescript"
            if any(f.endswith((".ts", ".tsx")) for f in changed_files)
            else "javascript"
        )

        files = self._filter_files(changed_files)
        evidence.files_analyzed = len(files)

        if not files:
            return evidence

        # Run passes concurrently
        lint_findings, tsc_findings, dep_vulns, complexity_ev = await asyncio.gather(
            self._eslint(files, repo_path, evidence),
            self._tsc(repo_path, evidence),
            self._npm_audit(repo_path, evidence),
            analyze_complexity(files, repo_path, evidence.tools_executed, evidence.tools_skipped),
        )

        evidence.static_findings.extend(lint_findings)
        evidence.static_findings.extend(tsc_findings)

        secret_findings = scan_secrets(files, repo_path)
        evidence.static_findings.extend(secret_findings)

        all_sec = [f for f in secret_findings if f.category == "security"]
        evidence.security = SecurityEvidence(
            critical_count=sum(1 for f in all_sec if f.severity == SeverityEnum.CRITICAL),
            high_count=sum(1 for f in all_sec if f.severity == SeverityEnum.HIGH),
            medium_count=sum(1 for f in all_sec if f.severity == SeverityEnum.MEDIUM),
            hardcoded_secrets=[
                {"file": f.file_path, "line": f.line_number, "type": f.rule_id}
                for f in secret_findings
            ],
            dependency_vulnerabilities=dep_vulns,
        )

        evidence.complexity = complexity_ev
        evidence.duplication = analyze_duplication(files, repo_path)
        evidence.testing = self._detect_test_framework(repo_path, evidence)

        evidence.analysis_duration_ms = (time.monotonic() - start) * 1000
        return evidence

    # ── ESLint ────────────────────────────────────────────────────────────────

    async def _eslint(
        self, files: List[str], repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Finding]:
        abs_files = [str(Path(repo_path) / f) for f in files]

        for binary in ("eslint", "npx"):
            cmd = (
                ["eslint", "--format=json"] + abs_files
                if binary == "eslint"
                else ["npx", "eslint", "--format=json"] + abs_files
            )
            if binary == "npx" or shutil.which("eslint"):
                result = await _run(cmd, cwd=repo_path)
                if result:
                    evidence.tools_executed.append("eslint")
                    return self._parse_eslint(result, files)

        self._degrade_quality(evidence, "static_analysis", "eslint")
        return []

    # ── TypeScript Compiler ───────────────────────────────────────────────────

    async def _tsc(self, repo_path: str, evidence: CodeQualityEvidence) -> List[Finding]:
        tsconfig = Path(repo_path) / "tsconfig.json"
        if not tsconfig.exists():
            return []

        for binary, cmd in [
            ("tsc", ["tsc", "--noEmit", "--pretty", "false"]),
            ("npx", ["npx", "tsc", "--noEmit", "--pretty", "false"]),
        ]:
            if shutil.which(binary) or binary == "npx":
                result = await _run(cmd, cwd=repo_path)
                if result is not None:
                    evidence.tools_executed.append("tsc")
                    return self._parse_tsc(result)
                break

        self._degrade_quality(evidence, "static_analysis", "tsc", penalty=0.1)
        return []

    # ── npm audit ─────────────────────────────────────────────────────────────

    async def _npm_audit(
        self, repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Dict]:
        pkg_json = Path(repo_path) / "package.json"
        if not pkg_json.exists():
            return []

        result = await _run(["npm", "audit", "--json"], cwd=repo_path)
        if not result:
            self._degrade_quality(evidence, "security", "npm-audit", penalty=0.05)
            return []

        evidence.tools_executed.append("npm-audit")
        return self._parse_npm_audit(result)

    # ── Test framework detection ──────────────────────────────────────────────

    def _detect_test_framework(self, repo_path: str, evidence: CodeQualityEvidence) -> TestingEvidence:
        """
        Detect test framework from config files or package.json.
        
        Note: Does not attempt to collect coverage data.
        Degrades confidence since coverage is unavailable.
        """
        root = Path(repo_path)
        for name, framework in [
            ("jest.config.js", "jest"),
            ("jest.config.ts", "jest"),
            ("vitest.config.ts", "vitest"),
            ("jasmine.json", "jasmine"),
            ("karma.conf.js", "karma"),
        ]:
            if (root / name).exists():
                # Coverage data not collected - reduce confidence
                self._degrade_quality(evidence, "testing", "coverage", penalty=0.10)
                return TestingEvidence(test_framework=framework)
        pkg = root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                scripts = data.get("scripts", {})
                test_cmd = scripts.get("test", "")
                for fw in ("jest", "vitest", "mocha", "jasmine"):
                    if fw in test_cmd:
                        # Coverage data not collected - reduce confidence
                        self._degrade_quality(evidence, "testing", "coverage", penalty=0.10)
                        return TestingEvidence(test_framework=fw)
            except (json.JSONDecodeError, OSError):
                pass
        
        # No test framework detected and no coverage - reduce confidence
        self._degrade_quality(evidence, "testing", "coverage", penalty=0.10)
        return TestingEvidence()

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_eslint(output: str, files: List[str]) -> List[Finding]:
        try:
            results = json.loads(output)
        except json.JSONDecodeError:
            return []
        findings = []
        sev_map = {1: SeverityEnum.MEDIUM, 2: SeverityEnum.HIGH}
        for file_result in results:
            fp = file_result.get("filePath", "")
            for msg in file_result.get("messages", []):
                findings.append(Finding(
                    file_path=fp,
                    line_number=msg.get("line"),
                    rule_id=f"ESLINT-{msg.get('ruleId', 'unknown')}",
                    category="maintainability",
                    severity=sev_map.get(msg.get("severity", 1), SeverityEnum.MEDIUM),
                    source_tool="eslint",
                    message=msg.get("message", ""),
                ))
        return findings

    @staticmethod
    def _parse_tsc(output: str) -> List[Finding]:
        import re
        findings = []
        pattern = re.compile(r"(.+)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.+)")
        for line in output.splitlines():
            m = pattern.match(line)
            if m:
                findings.append(Finding(
                    file_path=m.group(1),
                    line_number=int(m.group(2)),
                    rule_id=f"TSC-{m.group(5)}",
                    category="type",
                    severity=SeverityEnum.HIGH if m.group(4) == "error" else SeverityEnum.MEDIUM,
                    source_tool="tsc",
                    message=m.group(6),
                ))
        return findings

    @staticmethod
    def _parse_npm_audit(output: str) -> List[Dict]:
        try:
            data = json.loads(output)
            vulns = data.get("vulnerabilities", {})
            result = []
            for pkg_name, info in vulns.items():
                result.append({
                    "package": pkg_name,
                    "severity": info.get("severity", "unknown"),
                    "cve": str(info.get("via", [""])[0])[:100],
                    "description": info.get("title", "")[:200],
                })
            return result
        except (json.JSONDecodeError, AttributeError):
            return []
