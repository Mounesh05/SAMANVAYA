"""
Python Language Analyzer Adapter.
Tool chain: ruff → mypy → radon → pip-audit → ast fallback
"""

import asyncio
import json
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelligence.analyzers.base import BaseAnalyzer
from intelligence.analyzers.common.complexity import analyze_complexity
from intelligence.analyzers.common.duplication import analyze_duplication
from intelligence.analyzers.common.secrets_scanner import scan_secrets
from intelligence.evidence.models import (
    ArchitectureEvidence,
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


class PythonAnalyzer(BaseAnalyzer):
    """
    Python language adapter.

    Tool priority:
      Lint:       ruff → flake8 → ast syntax check
      Types:      mypy (optional supplement)
      Complexity: radon → lizard → ast (handled by common/complexity.py)
      Security:   bandit → secrets_scanner regex
      Deps:       pip-audit → safety
      Tests:      pytest --collect-only (detect) + coverage.py
    """

    language = "python"
    supported_extensions = [".py", ".pyi"]

    async def analyze(
        self,
        changed_files: List[str],
        repo_path: str,
        pr_context: dict,
    ) -> CodeQualityEvidence:
        import time
        start = time.monotonic()

        evidence = self._empty_evidence(repo_path, pr_context)
        files = self._filter_files(changed_files)
        abs_files = [str(Path(repo_path) / f) for f in files]

        evidence.files_analyzed = len(files)

        if not files:
            return evidence

        # Run all passes concurrently
        (
            lint_findings,
            security_findings,
            dep_vulns,
            complexity_ev,
        ) = await asyncio.gather(
            self._lint(files, abs_files, repo_path, evidence),
            self._security(abs_files, repo_path, evidence),
            self._dependencies(repo_path, evidence),
            analyze_complexity(files, repo_path, evidence.tools_executed, evidence.tools_skipped),
        )

        evidence.static_findings.extend(lint_findings)

        # Secrets scan (always runs, no tool required)
        secret_findings = scan_secrets(files, repo_path)
        evidence.static_findings.extend(secret_findings)

        # Security evidence
        all_sec = security_findings + [f for f in secret_findings if f.category == "security"]
        evidence.security = SecurityEvidence(
            critical_count=sum(1 for f in all_sec if f.severity == SeverityEnum.CRITICAL),
            high_count=sum(1 for f in all_sec if f.severity == SeverityEnum.HIGH),
            medium_count=sum(1 for f in all_sec if f.severity == SeverityEnum.MEDIUM),
            hardcoded_secrets=[
                {"file": f.file_path, "line": f.line_number, "type": f.rule_id}
                for f in secret_findings
            ],
            dependency_vulnerabilities=dep_vulns,
            findings=all_sec,
        )

        evidence.complexity = complexity_ev
        evidence.duplication = analyze_duplication(files, repo_path)
        evidence.testing = await self._testing(repo_path, evidence)
        evidence.architecture = self._architecture(files, repo_path)

        evidence.analysis_duration_ms = (time.monotonic() - start) * 1000
        return evidence

    # ── Lint ──────────────────────────────────────────────────────────────────

    async def _lint(
        self, files: List[str], abs_files: List[str],
        repo_path: str, evidence: CodeQualityEvidence,
    ) -> List[Finding]:
        findings: List[Finding] = []

        if self._tool_available("ruff"):
            result = await _run(
                ["ruff", "check", "--output-format=json"] + abs_files,
                cwd=repo_path,
            )
            if result:
                evidence.tools_executed.append("ruff")
                findings.extend(self._parse_ruff(result, files))
                # Supplement with mypy if available
                if self._tool_available("mypy"):
                    mypy_out = await _run(
                        ["mypy", "--output=json", "--no-error-summary"] + abs_files,
                        cwd=repo_path,
                    )
                    if mypy_out:
                        evidence.tools_executed.append("mypy")
                        findings.extend(self._parse_mypy(mypy_out, files))
                return findings
            self._degrade_quality(evidence, "static_analysis", "ruff-failed")

        if self._tool_available("flake8"):
            result = await _run(
                ["flake8", "--format=json"] + abs_files, cwd=repo_path
            )
            if result:
                evidence.tools_executed.append("flake8")
                findings.extend(self._parse_flake8(result, files))
                return findings
            self._degrade_quality(evidence, "static_analysis", "flake8-failed")
        else:
            self._degrade_quality(evidence, "static_analysis", "ruff")

        # AST syntax fallback
        evidence.tools_executed.append("ast-syntax-fallback")
        findings.extend(self._ast_syntax_check(abs_files, files))
        return findings

    # ── Security ──────────────────────────────────────────────────────────────

    async def _security(
        self, abs_files: List[str], repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Finding]:
        if not self._tool_available("bandit"):
            self._degrade_quality(evidence, "security", "bandit", penalty=0.1)
            return []

        result = await _run(
            ["bandit", "-r", "-f", "json", "-q"] + abs_files, cwd=repo_path
        )
        if not result:
            return []

        evidence.tools_executed.append("bandit")
        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            return []

        findings = []
        sev_map = {"HIGH": SeverityEnum.HIGH, "MEDIUM": SeverityEnum.MEDIUM, "LOW": SeverityEnum.LOW}
        for issue in data.get("results", []):
            findings.append(Finding(
                file_path=issue.get("filename", ""),
                line_number=issue.get("line_number"),
                rule_id=f"BANDIT-{issue.get('test_id', 'B000')}",
                category="security",
                severity=sev_map.get(issue.get("issue_severity", "LOW"), SeverityEnum.LOW),
                source_tool="bandit",
                message=issue.get("issue_text", ""),
                code_snippet=issue.get("code", "")[:200],
            ))
        return findings

    # ── Dependencies ──────────────────────────────────────────────────────────

    async def _dependencies(
        self, repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Dict]:
        for tool, cmd in [
            ("pip-audit", ["pip-audit", "--format=json", "-r", "requirements.txt"]),
            ("safety",    ["safety", "check", "--json"]),
        ]:
            if self._tool_available(tool):
                result = await _run(cmd, cwd=repo_path)
                if result:
                    evidence.tools_executed.append(tool)
                    return self._parse_dep_vulns(result)
                break
        return []

    # ── Testing ───────────────────────────────────────────────────────────────

    async def _testing(
        self, repo_path: str, evidence: CodeQualityEvidence
    ) -> TestingEvidence:
        te = TestingEvidence(test_framework="pytest")

        # Detect test framework
        if not self._tool_available("pytest"):
            self._degrade_quality(evidence, "testing", "pytest", penalty=0.15)
            return te

        # Collect test count without running
        result = await _run(
            ["pytest", "--collect-only", "-q", "--no-header"],
            cwd=repo_path,
        )
        if result:
            evidence.tools_executed.append("pytest-collect")
            lines = result.strip().splitlines()
            for line in lines:
                if "selected" in line:
                    try:
                        te.total_tests = int(line.split()[0])
                    except (ValueError, IndexError):
                        pass

        # Coverage (if .coverage file exists from previous run)
        coverage_available = False
        if self._tool_available("coverage"):
            cov_out = await _run(["coverage", "report", "--format=json"], cwd=repo_path)
            if cov_out:
                try:
                    cov_data = json.loads(cov_out)
                    te.coverage_percentage = round(cov_data.get("totals", {}).get("percent_covered", 0), 1)
                    evidence.tools_executed.append("coverage")
                    coverage_available = True
                except json.JSONDecodeError:
                    pass
        
        # Degrade confidence if coverage data unavailable
        if not coverage_available:
            self._degrade_quality(evidence, "testing", "coverage", penalty=0.10)

        return te

    # ── Architecture ──────────────────────────────────────────────────────────

    def _architecture(self, files: List[str], repo_path: str) -> ArchitectureEvidence:
        """Detect forbidden import patterns (api→db direct access, etc.)."""
        violations = []
        FORBIDDEN = [
            ("api/", "database", "API layer should not import database directly"),
            ("routes/", "models/", "Routes should go through services, not models directly"),
        ]
        for rel_path in files:
            try:
                content = (Path(repo_path) / rel_path).read_text(errors="replace")
                for from_layer, to_layer, reason in FORBIDDEN:
                    if from_layer in rel_path and f"from {to_layer}" in content:
                        violations.append({
                            "file": rel_path,
                            "violation": reason,
                            "from_layer": from_layer,
                            "to_layer": to_layer,
                        })
            except OSError:
                continue
        return ArchitectureEvidence(layer_violations=violations)

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_ruff(output: str, files: List[str]) -> List[Finding]:
        try:
            items = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return []
        sev_map = {"E": SeverityEnum.HIGH, "W": SeverityEnum.MEDIUM,
                   "F": SeverityEnum.HIGH, "S": SeverityEnum.HIGH, "C": SeverityEnum.LOW}
        findings = []
        for item in items:
            code = item.get("code", "E000")
            findings.append(Finding(
                file_path=item.get("filename", ""),
                line_number=item.get("location", {}).get("row"),
                rule_id=f"RUFF-{code}",
                category="syntax" if code.startswith(("E", "W", "F")) else "maintainability",
                severity=sev_map.get(code[0], SeverityEnum.LOW),
                source_tool="ruff",
                message=item.get("message", ""),
            ))
        return findings

    @staticmethod
    def _parse_mypy(output: str, files: List[str]) -> List[Finding]:
        findings = []
        for line in output.strip().splitlines():
            try:
                item = json.loads(line)
                if item.get("severity") in ("error", "warning"):
                    findings.append(Finding(
                        file_path=item.get("file", ""),
                        line_number=item.get("line"),
                        rule_id=f"MYPY-{item.get('code', 'misc')}",
                        category="type",
                        severity=SeverityEnum.HIGH if item["severity"] == "error" else SeverityEnum.MEDIUM,
                        source_tool="mypy",
                        message=item.get("message", ""),
                    ))
            except (json.JSONDecodeError, KeyError):
                continue
        return findings

    @staticmethod
    def _parse_flake8(output: str, files: List[str]) -> List[Finding]:
        import re
        findings = []
        pattern = re.compile(r"(.+):(\d+):(\d+): ([A-Z]\d+) (.+)")
        for line in output.splitlines():
            m = pattern.match(line)
            if m:
                code = m.group(4)
                findings.append(Finding(
                    file_path=m.group(1),
                    line_number=int(m.group(2)),
                    rule_id=f"FLAKE8-{code}",
                    category="syntax",
                    severity=SeverityEnum.HIGH if code[0] == "E" else SeverityEnum.MEDIUM,
                    source_tool="flake8",
                    message=m.group(5),
                ))
        return findings

    @staticmethod
    def _ast_syntax_check(abs_files: List[str], rel_files: List[str]) -> List[Finding]:
        import ast as ast_mod
        findings = []
        for abs_path, rel_path in zip(abs_files, rel_files):
            try:
                source = Path(abs_path).read_text(encoding="utf-8", errors="replace")
                ast_mod.parse(source)
            except SyntaxError as e:
                findings.append(Finding(
                    file_path=rel_path,
                    line_number=e.lineno,
                    rule_id="AST-SYNTAX-ERROR",
                    category="syntax",
                    severity=SeverityEnum.CRITICAL,
                    source_tool="ast-syntax-fallback",
                    message=str(e),
                ))
            except OSError:
                pass
        return findings

    @staticmethod
    def _parse_dep_vulns(output: str) -> List[Dict]:
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return [
                    {"package": v.get("name", ""), "severity": v.get("severity", "unknown"),
                     "cve": v.get("id", ""), "description": v.get("description", "")[:200]}
                    for v in data
                ]
        except (json.JSONDecodeError, AttributeError):
            pass
        return []
