"""
C Language Analyzer Adapter.
Tool chain: gcc -Wall → cppcheck → flawfinder → lizard → GCC regex fallback
Separate from C++ — C analysis focuses on memory safety, pointer issues, C89/C99 compliance.
"""

import asyncio
import json
import re
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
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
        return (out + err).decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return None


class CAnalyzer(BaseAnalyzer):
    """
    C language adapter.
    Focuses on: compiler warnings, memory safety (cppcheck),
    security flaws (flawfinder), and cyclomatic complexity (lizard).
    """

    language = "c"
    supported_extensions = [".c", ".h"]

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
        evidence.files_analyzed = len(files)

        if not files:
            return evidence

        abs_files = [str(Path(repo_path) / f) for f in files]

        compiler_findings, cppcheck_findings, security_findings, complexity_ev = await asyncio.gather(
            self._gcc_warnings(abs_files, repo_path, evidence),
            self._cppcheck(abs_files, repo_path, evidence),
            self._flawfinder(abs_files, repo_path, evidence),
            analyze_complexity(files, repo_path, evidence.tools_executed, evidence.tools_skipped),
        )

        evidence.static_findings.extend(compiler_findings)
        evidence.static_findings.extend(cppcheck_findings)

        secret_findings = scan_secrets(files, repo_path)
        evidence.static_findings.extend(secret_findings)
        all_sec = security_findings + [f for f in secret_findings if f.category == "security"]

        evidence.security = SecurityEvidence(
            critical_count=sum(1 for f in all_sec if f.severity == SeverityEnum.CRITICAL),
            high_count=sum(1 for f in all_sec if f.severity == SeverityEnum.HIGH),
            medium_count=sum(1 for f in all_sec if f.severity == SeverityEnum.MEDIUM),
            hardcoded_secrets=[
                {"file": f.file_path, "line": f.line_number, "type": f.rule_id}
                for f in secret_findings
            ],
            findings=all_sec,
        )

        evidence.complexity = complexity_ev
        evidence.duplication = analyze_duplication(files, repo_path)
        evidence.testing = self._detect_tests(repo_path)

        evidence.analysis_duration_ms = (time.monotonic() - start) * 1000
        return evidence

    # ── GCC Compiler Warnings ─────────────────────────────────────────────────

    async def _gcc_warnings(
        self, abs_files: List[str], repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Finding]:
        c_files = [f for f in abs_files if f.endswith(".c")]
        if not c_files:
            return []

        for compiler in ("gcc", "cc", "clang"):
            if not self._tool_available(compiler):
                continue
            result = await _run(
                [compiler, "-Wall", "-Wextra", "-fsyntax-only"] + c_files,
                cwd=repo_path,
            )
            if result is not None:
                evidence.tools_executed.append(compiler)
                return self._parse_gcc_output(result, compiler)

        self._degrade_quality(evidence, "static_analysis", "gcc", penalty=0.3)
        return self._regex_c_fallback([f for f in c_files], repo_path)

    # ── Cppcheck ──────────────────────────────────────────────────────────────

    async def _cppcheck(
        self, abs_files: List[str], repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Finding]:
        if not self._tool_available("cppcheck"):
            self._degrade_quality(evidence, "static_analysis", "cppcheck", penalty=0.1)
            return []

        result = await _run(
            ["cppcheck", "--enable=all", "--output-format=gcc",
             "--suppress=missingIncludeSystem"] + abs_files,
            cwd=repo_path,
        )
        if not result:
            return []

        evidence.tools_executed.append("cppcheck")
        return self._parse_gcc_output(result, "cppcheck")

    # ── Flawfinder (security) ─────────────────────────────────────────────────

    async def _flawfinder(
        self, abs_files: List[str], repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Finding]:
        if not self._tool_available("flawfinder"):
            self._degrade_quality(evidence, "security", "flawfinder", penalty=0.1)
            return self._dangerous_c_patterns([f for f in abs_files if f.endswith((".c",".h"))], repo_path)

        result = await _run(
            ["flawfinder", "--csv"] + abs_files,
            cwd=repo_path,
        )
        if not result:
            return []

        evidence.tools_executed.append("flawfinder")
        return self._parse_flawfinder_csv(result)

    # ── Test Detection ────────────────────────────────────────────────────────

    def _detect_tests(self, repo_path: str) -> TestingEvidence:
        root = Path(repo_path)
        for framework, indicator in [
            ("check", "check.h"), ("unity", "unity.h"),
            ("ctest", "CMakeLists.txt"), ("cmocka", "cmocka.h"),
        ]:
            if any(root.rglob(f"*{indicator}")):
                return TestingEvidence(test_framework=framework)
        return TestingEvidence()

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_gcc_output(output: str, source: str) -> List[Finding]:
        findings = []
        pattern = re.compile(r"(.+?):(\d+):(?:\d+:)?\s+(warning|error|note):\s+(.+?)(?:\s+\[.+\])?$")
        sev_map = {"error": SeverityEnum.CRITICAL, "warning": SeverityEnum.HIGH, "note": SeverityEnum.LOW}
        for line in output.splitlines():
            m = pattern.match(line.strip())
            if m:
                findings.append(Finding(
                    file_path=m.group(1),
                    line_number=int(m.group(2)),
                    rule_id=f"{source.upper()}-{m.group(3).upper()}",
                    category="syntax",
                    severity=sev_map.get(m.group(3), SeverityEnum.MEDIUM),
                    source_tool=source,
                    message=m.group(4).strip(),
                ))
        return findings

    @staticmethod
    def _parse_flawfinder_csv(output: str) -> List[Finding]:
        findings = []
        for line in output.splitlines()[1:]:  # skip header
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                risk = int(parts[3])
                severity = (SeverityEnum.CRITICAL if risk >= 4 else
                            SeverityEnum.HIGH if risk >= 2 else SeverityEnum.MEDIUM)
                findings.append(Finding(
                    file_path=parts[0].strip('"'),
                    line_number=int(parts[1]) if parts[1].isdigit() else None,
                    rule_id=f"FLAWFINDER-{parts[2].strip('\"').upper()[:30]}",
                    category="security",
                    severity=severity,
                    source_tool="flawfinder",
                    message=parts[5].strip('"')[:300],
                ))
            except (ValueError, IndexError):
                continue
        return findings

    @staticmethod
    def _dangerous_c_patterns(abs_files: List[str], repo_path: str) -> List[Finding]:
        """Regex fallback for common unsafe C functions."""
        DANGEROUS = [
            (re.compile(r"\bgets\s*\("), "C-GETS", SeverityEnum.CRITICAL, "Use of gets() is unsafe — use fgets()"),
            (re.compile(r"\bstrcpy\s*\("), "C-STRCPY", SeverityEnum.HIGH, "strcpy() is unsafe — use strncpy() or strlcpy()"),
            (re.compile(r"\bsprintf\s*\("), "C-SPRINTF", SeverityEnum.HIGH, "sprintf() can overflow — use snprintf()"),
            (re.compile(r"\bscanf\s*\("), "C-SCANF", SeverityEnum.MEDIUM, "scanf() without width limit is unsafe"),
            (re.compile(r"\bmalloc\s*\(.+\)(?!.*free)"), "C-MALLOC-NOFREE", SeverityEnum.MEDIUM, "Possible malloc without free"),
        ]
        findings = []
        for fpath in abs_files:
            try:
                lines = Path(fpath).read_text(errors="replace").splitlines()
                for ln, line in enumerate(lines, 1):
                    for pattern, rule_id, severity, msg in DANGEROUS:
                        if pattern.search(line):
                            findings.append(Finding(
                                file_path=fpath, line_number=ln,
                                rule_id=rule_id, category="security",
                                severity=severity, source_tool="c-regex-fallback",
                                message=msg,
                            ))
            except OSError:
                continue
        return findings

    @staticmethod
    def _regex_c_fallback(abs_files: List[str], repo_path: str) -> List[Finding]:
        return CAnalyzer._dangerous_c_patterns(abs_files, repo_path)
