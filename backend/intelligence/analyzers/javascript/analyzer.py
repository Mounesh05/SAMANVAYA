"""
JavaScript / TypeScript Language Analyzer Adapter.
Tool chain: ESLint → tsc → npm audit → regex fallback

Migrated from intelligence/static_analysis/javascript_analyzer.py.
Output is now normalized CodeQualityEvidence instead of a JS-specific dict.
"""

import asyncio
import json
import os
import posixpath
import shutil
from pathlib import Path
from typing import Dict, List, Optional

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


def _resolve_command(cmd: List[str], cwd: Optional[str] = None) -> Optional[List[str]]:
    """Prefer project-local tools and run Windows Node CLIs without a shell."""
    if not cmd:
        return None
    executable = None
    if cwd:
        executable = shutil.which(cmd[0], path=str(Path(cwd) / "node_modules" / ".bin"))
    executable = executable or shutil.which(cmd[0])
    if not executable:
        return None
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        # Batch wrappers need cmd.exe and shell quoting. Invoke known Node entrypoints
        # directly instead, keeping every file path as a separate process argument.
        entrypoints = {
            "npm": ("npm", "bin", "npm-cli.js"),
            "npx": ("npm", "bin", "npx-cli.js"),
            "eslint": ("eslint", "bin", "eslint.js"),
            "tsc": ("typescript", "bin", "tsc"),
        }
        entrypoint = entrypoints.get(Path(executable).stem.lower())
        if entrypoint is None:
            return None
        wrapper_dir = Path(executable).parent
        roots = [wrapper_dir.parent, wrapper_dir / "node_modules"]
        node = shutil.which("node")
        if not node:
            return None
        for root in roots:
            script = root.joinpath(*entrypoint)
            if script.is_file():
                return [node, str(script), *cmd[1:]]
        return None
    return [executable, *cmd[1:]]


async def _run(cmd: List[str], cwd: Optional[str] = None) -> Optional[str]:
    resolved_cmd = _resolve_command(cmd, cwd)
    if resolved_cmd is None:
        return None
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *resolved_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode and not stdout:
            return None
        return stdout.decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except (asyncio.TimeoutError, OSError):
                pass
        if isinstance(exc, asyncio.CancelledError):
            raise
        return None
    except (FileNotFoundError, OSError, NotImplementedError):
        return None


def _relative_path(file_path: str, repo_path: Optional[str] = None) -> str:
    normalized = posixpath.normpath(file_path.replace("\\", "/"))
    if repo_path:
        root = posixpath.normpath(str(repo_path).replace("\\", "/")).rstrip("/")
        if normalized.casefold().startswith(root.casefold() + "/"):
            normalized = normalized[len(root) + 1:]
    return normalized


class JavaScriptAnalyzer(BaseAnalyzer):
    """
    JavaScript and TypeScript adapter.
    Handles .js, .jsx, .ts, .tsx, .mjs, .cjs files.

    Reuses and normalizes the existing ESLint + tsc + npm audit logic.
    """

    language = "javascript"
    supported_extensions = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]

    async def analyze(
        self,
        changed_files: List[str],
        repo_path: str,
        pr_context: Optional[dict] = None,
    ) -> CodeQualityEvidence:
        import time
        start = time.perf_counter()

        evidence = self._empty_evidence(repo_path, pr_context or {})
        evidence.primary_language = (
            "typescript"
            if any(f.lower().endswith((".ts", ".tsx")) for f in changed_files)
            else "javascript"
        )

        files = self._filter_files(changed_files)
        evidence.files_analyzed = len(files)

        if not files:
            return evidence

        # Run passes concurrently
        lint_findings, tsc_findings, dep_vulns, complexity_ev = await asyncio.gather(
            self._eslint(files, repo_path, evidence),
            self._tsc(repo_path, evidence, changed_files=files),
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

        evidence.analysis_duration_ms = (time.perf_counter() - start) * 1000
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
                else ["npx", "--no-install", "eslint", "--format=json"] + abs_files
            )
            result = await _run(cmd, cwd=repo_path)
            if result is not None:
                try:
                    parsed = json.loads(result)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(parsed, list):
                    evidence.tools_executed.append("eslint")
                    return self._parse_eslint(result, files, repo_path)

        self._degrade_quality(evidence, "static_analysis", "eslint")
        return []

    # ── TypeScript Compiler ───────────────────────────────────────────────────

    async def _tsc(
        self, repo_path: str, evidence: CodeQualityEvidence,
        changed_files: Optional[List[str]] = None,
    ) -> List[Finding]:
        tsconfig = Path(repo_path) / "tsconfig.json"
        if not tsconfig.exists():
            return []

        for cmd in [
            ["tsc", "--noEmit", "--pretty", "false"],
            ["npx", "--no-install", "tsc", "--noEmit", "--pretty", "false"],
        ]:
            result = await _run(cmd, cwd=repo_path)
            if result is not None:
                evidence.tools_executed.append("tsc")
                return self._parse_tsc(result, changed_files, repo_path)

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
        try:
            payload = json.loads(result) if result else None
        except (json.JSONDecodeError, TypeError):
            payload = None
        if not isinstance(payload, dict) or not isinstance(payload.get("vulnerabilities"), dict) or payload.get("error"):
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
    def _parse_eslint(
        output: str, files: List[str], repo_path: Optional[str] = None,
    ) -> List[Finding]:
        try:
            results = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(results, list):
            return []
        findings = []
        sev_map = {1: SeverityEnum.MEDIUM, 2: SeverityEnum.HIGH}
        for file_result in results:
            if not isinstance(file_result, dict) or not isinstance(file_result.get("filePath"), str):
                continue
            fp = _relative_path(file_result["filePath"], repo_path)
            for msg in file_result.get("messages") or []:
                if not isinstance(msg, dict) or msg.get("severity") == 0:
                    continue
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
    def _parse_tsc(
        output: str, changed_files: Optional[List[str]] = None,
        repo_path: Optional[str] = None,
    ) -> List[Finding]:
        import re
        findings = []
        pattern = re.compile(r"(.+)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.+)")
        changed = {_relative_path(f, repo_path).casefold() for f in changed_files or []}
        for line in output.splitlines():
            m = pattern.match(line)
            if m:
                file_path = _relative_path(m.group(1), repo_path)
                in_change = changed_files is None or file_path.casefold() in changed
                findings.append(Finding(
                    file_path=file_path,
                    line_number=int(m.group(2)),
                    rule_id=f"TSC-{m.group(5)}" if in_change else f"TSC-REPO-{m.group(5)}",
                    category="type",
                    severity=SeverityEnum.HIGH if m.group(4) == "error" else SeverityEnum.MEDIUM,
                    source_tool="tsc" if in_change else "tsc-repo-wide",
                    message=m.group(6),
                ))
        return findings

    @staticmethod
    def _parse_npm_audit(output: str) -> List[Dict]:
        try:
            data = json.loads(output)
            if not isinstance(data, dict):
                return []
            vulns = data.get("vulnerabilities", {})
            if not isinstance(vulns, dict):
                return []
            result = []
            for pkg_name, info in vulns.items():
                if not isinstance(info, dict):
                    continue
                via = info.get("via") or []
                if not isinstance(via, list):
                    via = [via]
                identifiers, titles = [], []
                for advisory in via:
                    if isinstance(advisory, dict):
                        identifier = advisory.get("url") or advisory.get("source")
                        if identifier is not None:
                            identifiers.append(str(identifier))
                        if isinstance(advisory.get("title"), str):
                            titles.append(advisory["title"])
                if not identifiers:
                    identifiers = [str(v) for v in via if isinstance(v, (str, int))]
                if not titles and isinstance(info.get("title"), str):
                    titles.append(info["title"])
                result.append({
                    "package": pkg_name,
                    "severity": info.get("severity") if isinstance(info.get("severity"), str) else "unknown",
                    "cve": "; ".join(dict.fromkeys(identifiers))[:100],
                    "description": "; ".join(dict.fromkeys(titles))[:200],
                })
            return result
        except (json.JSONDecodeError, AttributeError):
            return []
