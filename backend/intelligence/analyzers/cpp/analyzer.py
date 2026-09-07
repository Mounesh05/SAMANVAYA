"""
C++ Language Analyzer Adapter.
Tool chain: clang-tidy → cppcheck → lizard (Halstead) → clang diagnostic fallback

Separate from C: adds RAII, exception safety, template analysis,
and C++ Core Guidelines checks.
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
        out, err = await asyncio.wait_for(proc.communicate(), timeout=180)
        return (out + err).decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return None


class CppAnalyzer(BaseAnalyzer):
    """
    C++ adapter.
    Distinct from CAnalyzer — adds clang-tidy (C++ Core Guidelines),
    RAII / resource-leak detection, and template instantiation warnings.
    """

    language = "cpp"
    supported_extensions = [".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".h"]

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
        build_dir = self._find_build_dir(repo_path)

        tidy_findings, cppcheck_findings, complexity_ev = await asyncio.gather(
            self._clang_tidy(abs_files, repo_path, build_dir, evidence),
            self._cppcheck(abs_files, repo_path, evidence),
            analyze_complexity(files, repo_path, evidence.tools_executed, evidence.tools_skipped),
        )

        evidence.static_findings.extend(tidy_findings)
        evidence.static_findings.extend(cppcheck_findings)

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
            findings=all_sec,
        )

        evidence.complexity = complexity_ev
        evidence.duplication = analyze_duplication(files, repo_path)
        evidence.testing = self._detect_tests(repo_path, evidence)

        evidence.analysis_duration_ms = (time.monotonic() - start) * 1000
        return evidence

    # ── Clang-Tidy ────────────────────────────────────────────────────────────

    async def _clang_tidy(
        self,
        abs_files: List[str],
        repo_path: str,
        build_dir: Optional[str],
        evidence: CodeQualityEvidence,
    ) -> List[Finding]:
        if not self._tool_available("clang-tidy"):
            self._degrade_quality(evidence, "static_analysis", "clang-tidy", penalty=0.3)
            return await self._clang_fallback(abs_files, repo_path, evidence)

        # Only lint .cpp/.cc/.cxx — not headers
        src_files = [f for f in abs_files if any(f.endswith(e) for e in (".cpp", ".cc", ".cxx"))]
        if not src_files:
            return []

        cmd = ["clang-tidy", "--quiet"]
        if build_dir:
            cmd += [f"-p={build_dir}"]
        cmd += [
            "--checks=cppcoreguidelines-*,modernize-*,readability-*,bugprone-*,performance-*",
        ] + src_files

        result = await _run(cmd, cwd=repo_path)
        if result is None:
            self._degrade_quality(evidence, "static_analysis", "clang-tidy-failed", penalty=0.2)
            return []

        evidence.tools_executed.append("clang-tidy")
        return self._parse_clang_tidy(result)

    # ── Cppcheck ──────────────────────────────────────────────────────────────

    async def _cppcheck(
        self, abs_files: List[str], repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Finding]:
        if not self._tool_available("cppcheck"):
            self._degrade_quality(evidence, "static_analysis", "cppcheck", penalty=0.1)
            return []

        result = await _run(
            ["cppcheck", "--enable=all", "--std=c++17",
             "--suppress=missingIncludeSystem", "--output-format=gcc"] + abs_files,
            cwd=repo_path,
        )
        if not result:
            return []

        evidence.tools_executed.append("cppcheck")
        return self._parse_gcc_style(result, "cppcheck")

    # ── Clang Compiler Fallback ───────────────────────────────────────────────

    async def _clang_fallback(
        self, abs_files: List[str], repo_path: str, evidence: CodeQualityEvidence
    ) -> List[Finding]:
        src_files = [f for f in abs_files if any(f.endswith(e) for e in (".cpp", ".cc", ".cxx"))]
        if not src_files:
            return self._regex_cpp_patterns(abs_files, repo_path)

        for compiler in ("clang++", "g++", "c++"):
            if not self._tool_available(compiler):
                continue
            result = await _run(
                [compiler, "-Wall", "-Wextra", "-std=c++17", "-fsyntax-only"] + src_files,
                cwd=repo_path,
            )
            if result is not None:
                evidence.tools_executed.append(f"{compiler}-fallback")
                return self._parse_gcc_style(result, compiler)

        # Final fallback — regex patterns
        evidence.tools_executed.append("cpp-regex-fallback")
        return self._regex_cpp_patterns(abs_files, repo_path)

    # ── Build dir detection ───────────────────────────────────────────────────

    def _find_build_dir(self, repo_path: str) -> Optional[str]:
        root = Path(repo_path)
        for candidate in ("build", "cmake-build-debug", "cmake-build-release", ".build"):
            d = root / candidate
            if d.is_dir() and (d / "compile_commands.json").exists():
                return str(d)
        return None

    # ── Test Detection ────────────────────────────────────────────────────────

    def _detect_tests(self, repo_path: str, evidence: CodeQualityEvidence) -> TestingEvidence:
        """
        Detect C++ test framework (Google Test, Catch2, Boost.Test, CTest).
        
        Note: Does not attempt to collect coverage data.
        Degrades confidence since coverage is unavailable.
        """
        root = Path(repo_path)
        for fw, indicator in [
            ("gtest", "gtest"), ("catch2", "catch2"),
            ("boost-test", "boost/test"), ("ctest", "CMakeLists.txt"),
        ]:
            if any(root.rglob(f"*{indicator}*")):
                # Coverage data not collected - reduce confidence
                self._degrade_quality(evidence, "testing", "coverage", penalty=0.10)
                return TestingEvidence(test_framework=fw)
        # No test framework detected and no coverage - reduce confidence
        self._degrade_quality(evidence, "testing", "coverage", penalty=0.10)
        return TestingEvidence()

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_clang_tidy(output: str) -> List[Finding]:
        findings = []
        pattern = re.compile(
            r"(.+?):(\d+):(\d+):\s+(warning|error|note):\s+(.+?)\s+\[(.+?)\]"
        )
        sev_map = {"error": SeverityEnum.CRITICAL, "warning": SeverityEnum.HIGH, "note": SeverityEnum.LOW}
        for line in output.splitlines():
            m = pattern.match(line.strip())
            if m:
                findings.append(Finding(
                    file_path=m.group(1),
                    line_number=int(m.group(2)),
                    rule_id=f"CLANG-TIDY-{m.group(6).replace('-', '_').upper()[:50]}",
                    category="maintainability",
                    severity=sev_map.get(m.group(4), SeverityEnum.MEDIUM),
                    source_tool="clang-tidy",
                    message=m.group(5).strip(),
                ))
        return findings

    @staticmethod
    def _parse_gcc_style(output: str, source: str) -> List[Finding]:
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
    def _regex_cpp_patterns(abs_files: List[str], repo_path: str) -> List[Finding]:
        """C++ specific anti-patterns detected via regex."""
        PATTERNS = [
            (re.compile(r"\bnew\b.+(?!\bdelete\b)"), "CPP-NEW-NODELETE",
             SeverityEnum.HIGH, "Possible memory leak: new without matching delete"),
            (re.compile(r"catch\s*\(\s*\.\.\.\s*\)\s*\{?\s*\}"),
             "CPP-CATCH-ALL-EMPTY", SeverityEnum.HIGH, "Empty catch-all hides exceptions"),
            (re.compile(r"using namespace std;"),
             "CPP-USING-NS-STD", SeverityEnum.MEDIUM, "Avoid 'using namespace std' in headers"),
            (re.compile(r"\bprintf\s*\("),
             "CPP-PRINTF", SeverityEnum.LOW, "Prefer std::cout or std::format over printf in C++"),
            (re.compile(r"(malloc|calloc|realloc)\s*\("),
             "CPP-C-ALLOC", SeverityEnum.MEDIUM, "Use new/delete or smart pointers instead of C allocation"),
        ]
        findings = []
        for fpath in abs_files:
            try:
                lines = Path(fpath).read_text(errors="replace").splitlines()
                for ln, line in enumerate(lines, 1):
                    for pattern, rule_id, severity, msg in PATTERNS:
                        if pattern.search(line):
                            findings.append(Finding(
                                file_path=fpath, line_number=ln,
                                rule_id=rule_id, category="maintainability",
                                severity=severity, source_tool="cpp-regex-fallback",
                                message=msg,
                            ))
            except OSError:
                continue
        return findings
