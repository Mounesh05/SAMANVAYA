"""
Java Language Analyzer Adapter.
Tool chain: mvn/gradle compile → Checkstyle/PMD → Lizard → OWASP Dep-Check
Fallback: XML/source file parsing when build tools unavailable.
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
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        return stdout.decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return None


class JavaAnalyzer(BaseAnalyzer):
    """
    Java adapter.
    Detects Maven vs Gradle, then orchestrates compilation,
    static analysis, dependency scanning, and test detection.
    """

    language = "java"
    supported_extensions = [".java"]

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

        build_system = self._detect_build_system(repo_path)

        # Run passes concurrently
        compile_findings, dep_vulns, complexity_ev = await asyncio.gather(
            self._compile_and_lint(files, repo_path, build_system, evidence),
            self._dependencies(repo_path, build_system, evidence),
            analyze_complexity(files, repo_path, evidence.tools_executed, evidence.tools_skipped),
        )

        evidence.static_findings.extend(compile_findings)

        secret_findings = scan_secrets(files, repo_path)
        evidence.static_findings.extend(secret_findings)

        sec_findings = [f for f in secret_findings if f.category == "security"]
        evidence.security = SecurityEvidence(
            critical_count=sum(1 for f in sec_findings if f.severity == SeverityEnum.CRITICAL),
            high_count=sum(1 for f in sec_findings if f.severity == SeverityEnum.HIGH),
            medium_count=sum(1 for f in sec_findings if f.severity == SeverityEnum.MEDIUM),
            hardcoded_secrets=[
                {"file": f.file_path, "line": f.line_number, "type": f.rule_id}
                for f in secret_findings
            ],
            dependency_vulnerabilities=dep_vulns,
        )

        evidence.complexity = complexity_ev
        evidence.duplication = analyze_duplication(files, repo_path)
        evidence.testing = self._detect_tests(repo_path)

        evidence.analysis_duration_ms = (time.monotonic() - start) * 1000
        return evidence

    # ── Build System Detection ────────────────────────────────────────────────

    def _detect_build_system(self, repo_path: str) -> str:
        root = Path(repo_path)
        if (root / "pom.xml").exists():
            return "maven"
        if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            return "gradle"
        return "unknown"

    # ── Compile & Lint ────────────────────────────────────────────────────────

    async def _compile_and_lint(
        self,
        files: List[str],
        repo_path: str,
        build_system: str,
        evidence: CodeQualityEvidence,
    ) -> List[Finding]:
        findings: List[Finding] = []

        # Attempt compilation warnings (non-blocking: -q suppress output)
        if build_system == "maven" and self._tool_available("mvn"):
            result = await _run(
                ["mvn", "compile", "-q", "--no-transfer-progress"],
                cwd=repo_path,
            )
            evidence.tools_executed.append("mvn-compile")
            if result:
                findings.extend(self._parse_compiler_warnings(result, "mvn"))
        elif build_system == "gradle" and self._tool_available("gradle"):
            result = await _run(["gradle", "compileJava", "-q"], cwd=repo_path)
            evidence.tools_executed.append("gradle-compile")
            if result:
                findings.extend(self._parse_compiler_warnings(result, "gradle"))
        else:
            self._degrade_quality(evidence, "static_analysis", build_system, penalty=0.25)
            # Fallback: basic regex scan for obvious Java anti-patterns
            evidence.tools_executed.append("java-regex-fallback")
            findings.extend(self._regex_fallback(files, repo_path))

        # Checkstyle (if available)
        if self._tool_available("checkstyle"):
            cs_result = await _run(
                ["checkstyle", "-f", "xml"] + [str(Path(repo_path) / f) for f in files],
                cwd=repo_path,
            )
            if cs_result:
                evidence.tools_executed.append("checkstyle")
                findings.extend(self._parse_checkstyle(cs_result, files))

        return findings

    # ── Dependencies ──────────────────────────────────────────────────────────

    async def _dependencies(
        self, repo_path: str, build_system: str, evidence: CodeQualityEvidence
    ) -> List[Dict]:
        if build_system == "maven" and self._tool_available("mvn"):
            result = await _run(
                ["mvn", "dependency:tree", "-q", "--no-transfer-progress"],
                cwd=repo_path,
            )
            if result:
                evidence.tools_executed.append("mvn-dependency-tree")
        return []  # OWASP Dependency-Check requires separate setup — returns empty for now

    # ── Test Detection ────────────────────────────────────────────────────────

    def _detect_tests(self, repo_path: str) -> TestingEvidence:
        root = Path(repo_path)
        # Detect JUnit vs TestNG
        test_src = root / "src" / "test"
        if test_src.exists():
            java_test_files = list(test_src.rglob("*.java"))
            framework = "junit"
            for f in java_test_files:
                try:
                    content = f.read_text(errors="replace")
                    if "org.testng" in content:
                        framework = "testng"
                        break
                except OSError:
                    pass
            return TestingEvidence(
                test_framework=framework,
                total_tests=len(java_test_files),
            )
        return TestingEvidence()

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_compiler_warnings(output: str, source: str) -> List[Finding]:
        findings = []
        pattern = re.compile(r"(.+\.java):(\d+):\s+(?:warning|error):\s+(.+)")
        for line in output.splitlines():
            m = pattern.match(line)
            if m:
                findings.append(Finding(
                    file_path=m.group(1),
                    line_number=int(m.group(2)),
                    rule_id=f"{source.upper()}-COMPILER-WARNING",
                    category="syntax",
                    severity=SeverityEnum.HIGH if "error" in line else SeverityEnum.MEDIUM,
                    source_tool=source,
                    message=m.group(3).strip(),
                ))
        return findings

    @staticmethod
    def _parse_checkstyle(xml_output: str, files: List[str]) -> List[Finding]:
        findings = []
        file_pattern = re.compile(r'<file name="(.+?)"')
        error_pattern = re.compile(r'<error line="(\d+)".*?severity="(\w+)".*?message="(.+?)".*?source="(.+?)"')
        current_file = ""
        for line in xml_output.splitlines():
            fm = file_pattern.search(line)
            if fm:
                current_file = fm.group(1)
            em = error_pattern.search(line)
            if em and current_file:
                sev_map = {"error": SeverityEnum.HIGH, "warning": SeverityEnum.MEDIUM, "info": SeverityEnum.LOW}
                findings.append(Finding(
                    file_path=current_file,
                    line_number=int(em.group(1)),
                    rule_id=f"CHECKSTYLE-{em.group(4).split('.')[-1]}",
                    category="maintainability",
                    severity=sev_map.get(em.group(2), SeverityEnum.LOW),
                    source_tool="checkstyle",
                    message=em.group(3),
                ))
        return findings

    @staticmethod
    def _regex_fallback(files: List[str], repo_path: str) -> List[Finding]:
        """Basic Java anti-pattern detection without compiler."""
        findings = []
        PATTERNS = [
            (re.compile(r"System\.out\.print"), "JAVA-SYSOUT", SeverityEnum.LOW,
             "Use logging framework instead of System.out.println"),
            (re.compile(r"catch\s*\(\s*Exception\s+\w+\s*\)\s*\{?\s*\}"),
             "JAVA-SWALLOW-EX", SeverityEnum.HIGH, "Empty catch block swallows exception"),
            (re.compile(r"\.equals\(null\)"), "JAVA-NULL-EQUALS",
             SeverityEnum.HIGH, "Use == null instead of .equals(null)"),
        ]
        for rel_path in files:
            try:
                lines = (Path(repo_path) / rel_path).read_text(errors="replace").splitlines()
                for ln, line in enumerate(lines, 1):
                    for pattern, rule_id, severity, message in PATTERNS:
                        if pattern.search(line):
                            findings.append(Finding(
                                file_path=rel_path,
                                line_number=ln,
                                rule_id=rule_id,
                                category="maintainability",
                                severity=severity,
                                source_tool="java-regex-fallback",
                                message=message,
                            ))
            except OSError:
                continue
        return findings
