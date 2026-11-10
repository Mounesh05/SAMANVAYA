"""
Python Language Analyzer Adapter.
Tool chain: ruff → flake8 → radon → pip-audit → safety → ast fallback
"""

import ast
import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelligence.analyzers.base import EXCLUDED_DIRS, BaseAnalyzer
from intelligence.analyzers.common.complexity import analyze_complexity
from intelligence.analyzers.common.duplication import analyze_duplication
from intelligence.analyzers.common.secrets_scanner import scan_secrets
from intelligence.evidence.models import (
    AnalysisQuality,
    ArchitectureEvidence,
    CodeQualityEvidence,
    ComplexityEvidence,
    DuplicationEvidence,
    Finding,
    SecurityEvidence,
    SeverityEnum,
    TestingEvidence,
)

# Compatibility: ensure analysis_quality.penalties is accessible
if not hasattr(AnalysisQuality, "penalties"):
    AnalysisQuality.penalties = property(
        lambda self: getattr(self, "_penalties", [round(1.0 - self.confidence, 4)] if self.confidence < 1.0 else [])
    )


async def _run(cmd: List[str], cwd: Optional[str] = None) -> Optional[str]:
    proc = None
    try:
        if not cmd:
            return None
        resolved_cmd = list(cmd)
        exe = shutil.which(resolved_cmd[0])
        if exe:
            resolved_cmd[0] = exe
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
    except Exception:
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
      Tests:      static AST test counting + pytest collect + coverage.py
    """

    language = "python"
    supported_extensions = [".py", ".pyi"]

    async def analyze(
        self,
        changed_files: List[str],
        repo_path: str,
        pr_context: Optional[dict] = None,
    ) -> CodeQualityEvidence:
        import time
        start = time.perf_counter()

        pr_context = pr_context or {}
        evidence = self._empty_evidence(repo_path, pr_context)

        try:
            files = self._filter_files(changed_files)
            abs_files = [str(Path(repo_path) / f) for f in files]

            evidence.files_analyzed = len(files)

            if not files:
                return evidence

            # ── Pass 1: Linting (Ruff → Flake8 → AST Syntax Fallback) ──────
            try:
                lint_findings = await self._lint(files, abs_files, repo_path, evidence)
            except Exception:
                self._degrade_quality(evidence, "static_analysis", "lint-pipeline-failed", penalty=0.15)
                lint_findings = []

            # ── Pass 2: Security Analysis (Bandit) ─────────────────────────
            try:
                security_findings = await self._security(abs_files, repo_path, evidence)
            except Exception:
                self._degrade_quality(evidence, "security", "security-pipeline-failed", penalty=0.15)
                security_findings = []

            # ── Pass 3: Dependency Auditing (Pip-Audit → Safety) ───────────
            try:
                dep_vulns = await self._dependencies(repo_path, evidence)
            except Exception:
                self._degrade_quality(evidence, "security", "dependencies-pipeline-failed", penalty=0.10)
                dep_vulns = []

            # ── Pass 4: Complexity Analysis (Lizard → Radon → AST) ─────────
            try:
                complexity_ev = await analyze_complexity(
                    files, repo_path, evidence.tools_executed, evidence.tools_skipped
                )
            except Exception:
                self._degrade_quality(evidence, "complexity", "complexity-pipeline-failed", penalty=0.20)
                complexity_ev = ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None)

            if lint_findings:
                evidence.static_findings.extend(lint_findings)

            # ── Pass 5: Secrets Scan (Always runs, regex-based) ─────────────
            try:
                secret_findings = scan_secrets(files, repo_path)
            except Exception:
                self._degrade_quality(evidence, "security", "secrets-pipeline-failed", penalty=0.10)
                secret_findings = []

            if secret_findings:
                evidence.static_findings.extend(secret_findings)

            # ── Pass 6: Security Evidence Assembly ─────────────────────────
            try:
                all_sec = (security_findings or []) + [
                    f for f in (secret_findings or []) if getattr(f, "category", "") == "security"
                ]
                evidence.security = SecurityEvidence(
                    critical_count=sum(1 for f in all_sec if f.severity == SeverityEnum.CRITICAL),
                    high_count=sum(1 for f in all_sec if f.severity == SeverityEnum.HIGH),
                    medium_count=sum(1 for f in all_sec if f.severity == SeverityEnum.MEDIUM),
                    hardcoded_secrets=[
                        {"file": f.file_path, "line": f.line_number, "type": f.rule_id}
                        for f in (secret_findings or [])
                    ],
                    dependency_vulnerabilities=dep_vulns or [],
                    findings=all_sec,
                )
            except Exception:
                self._degrade_quality(evidence, "security", "security-aggregation-failed", penalty=0.10)

            # ── Pass 7: Complexity Evidence Attachment ─────────────────────
            evidence.complexity = complexity_ev

            # ── Pass 8: Code Duplication Detection ─────────────────────────
            try:
                evidence.duplication = analyze_duplication(files, repo_path)
            except Exception:
                self._degrade_quality(evidence, "maintainability", "duplication-pipeline-failed", penalty=0.10)
                evidence.duplication = DuplicationEvidence()

            # ── Pass 9: Test Counting & Coverage Collection ────────────────
            try:
                evidence.testing = await self._testing(repo_path, evidence)
            except Exception:
                self._degrade_quality(evidence, "testing", "testing-pipeline-failed", penalty=0.15)
                evidence.testing = TestingEvidence(test_framework="pytest")

            # ── Pass 10: Architecture & Import Rules ───────────────────────
            try:
                evidence.architecture = self._architecture(files, repo_path)
            except Exception:
                self._degrade_quality(evidence, "architecture", "architecture-pipeline-failed", penalty=0.10)
                evidence.architecture = ArchitectureEvidence()

        except Exception:
            self._degrade_quality(evidence, "general", "analyzer-internal-error", penalty=0.50)
        finally:
            evidence.analysis_duration_ms = (time.perf_counter() - start) * 1000

        return evidence

    # ── Lint ──────────────────────────────────────────────────────────────────

    async def _lint(
        self,
        files: List[str],
        abs_files: Any,
        repo_path: Any = None,
        evidence: Optional[CodeQualityEvidence] = None,
    ) -> List[Finding]:
        # Support flexible calling conventions:
        # Signature A: _lint(files, abs_files, repo_path, evidence)
        # Signature B: _lint(files, repo_path, evidence)
        if isinstance(abs_files, (str, Path)) and (isinstance(repo_path, CodeQualityEvidence) or evidence is None):
            evidence = repo_path if isinstance(repo_path, CodeQualityEvidence) else evidence
            repo_path = str(abs_files)
            abs_files_list = [str(Path(repo_path) / f) for f in files]
        elif isinstance(abs_files, list):
            abs_files_list = abs_files
            repo_path = str(repo_path) if repo_path else ""
        else:
            abs_files_list = [str(Path(repo_path) / f) for f in files] if repo_path else files
            repo_path = str(repo_path) if repo_path else ""

        if evidence is None:
            evidence = CodeQualityEvidence(repository_id=repo_path or "default", primary_language="python")

        findings: List[Finding] = []

        if self._tool_available("ruff"):
            result = await _run(
                ["ruff", "check", "--output-format=json"] + abs_files_list,
                cwd=repo_path,
            )
            if result is not None:
                evidence.tools_executed.append("ruff")
                findings.extend(self._parse_ruff(result, files))
                # Supplement with mypy if available
                if self._tool_available("mypy"):
                    mypy_out = await _run(
                        ["mypy", "--output=json", "--no-error-summary"] + abs_files_list,
                        cwd=repo_path,
                    )
                    if mypy_out is not None:
                        evidence.tools_executed.append("mypy")
                        findings.extend(self._parse_mypy(mypy_out, files))
                return findings
            self._degrade_quality(evidence, "static_analysis", "ruff-failed")

        if self._tool_available("flake8"):
            result = await _run(
                ["flake8"] + abs_files_list, cwd=repo_path
            )
            if result is not None:
                evidence.tools_executed.append("flake8")
                findings.extend(self._parse_flake8(result, files))
                return findings
            self._degrade_quality(evidence, "static_analysis", "flake8-failed")
        else:
            self._degrade_quality(evidence, "static_analysis", "flake8")

        # AST syntax fallback
        evidence.tools_executed.append("ast-syntax-fallback")
        findings.extend(self._ast_syntax_check(abs_files_list, files))
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
        tools = [
            ("pip-audit", ["pip-audit", "--format=json", "-r", "requirements.txt"]),
            ("safety",    ["safety", "check", "--json"]),
        ]
        for tool, cmd in tools:
            if self._tool_available(tool):
                try:
                    result = await _run(cmd, cwd=repo_path)
                    if result is not None:
                        # Verify result is valid JSON rather than CLI error text
                        json.loads(result)
                        parsed = self._parse_dep_vulns(result)
                        evidence.tools_executed.append(tool)
                        return parsed
                    else:
                        self._degrade_quality(evidence, "security", f"{tool}-failed", penalty=0.05)
                except Exception:
                    self._degrade_quality(evidence, "security", f"{tool}-failed", penalty=0.05)
            else:
                self._degrade_quality(evidence, "security", tool, penalty=0.05)
        return []

    # ── Testing ───────────────────────────────────────────────────────────────

    PYTEST_SELECTED_PATTERN = re.compile(r"(\d+)\s+selected", re.IGNORECASE)
    PYTEST_COLLECT_PATTERN = re.compile(
        r"(?:collected\s+(\d+)\s+(?:items?|tests?)|(\d+)\s+(?:items?|tests?)\s+collected)",
        re.IGNORECASE,
    )

    @classmethod
    def _parse_pytest_output(cls, output: str) -> Optional[int]:
        """
        Parse test count from pytest collection or execution output.
        Handles:
          - 'collected 14 items'
          - 'collected 5 tests'
          - '14 items collected'
          - '8 tests collected in 0.05s'
          - '20 selected, 5 deselected'
          - 'collected 25 items / 5 deselected / 20 selected'
        """
        if not output:
            return None
        for line in output.splitlines():
            m_sel = cls.PYTEST_SELECTED_PATTERN.search(line)
            if m_sel:
                try:
                    return int(m_sel.group(1))
                except ValueError:
                    pass
            m = cls.PYTEST_COLLECT_PATTERN.search(line)
            if m:
                count_str = next((g for g in m.groups() if g is not None), None)
                if count_str:
                    try:
                        return int(count_str)
                    except ValueError:
                        pass
        return None

    @staticmethod
    def _count_tests_in_file(file_path: Path) -> int:
        """Count test functions and test class methods in a single file via AST."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, ValueError, OSError):
            return 0

        count = 0
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    count += 1
            elif isinstance(node, ast.ClassDef):
                is_test_class = node.name.startswith("Test") or any(
                    (isinstance(b, ast.Name) and b.id == "TestCase") or
                    (isinstance(b, ast.Attribute) and b.attr == "TestCase")
                    for b in node.bases
                )
                if is_test_class:
                    has_init = any(
                        isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == "__init__"
                        for m in node.body
                    )
                    if not has_init:
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if item.name.startswith("test"):
                                    count += 1
        return count

    def _count_tests_ast(self, repo_path: str) -> TestingEvidence:
        """
        Safely count tests statically via AST traversal without executing
        untrusted project code.
        """
        te = TestingEvidence(test_framework="pytest")
        repo = Path(repo_path)
        if not repo.is_dir():
            return te

        total = 0
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [
                d for d in dirs
                if d.lower() not in EXCLUDED_DIRS and not d.startswith(".")
            ]
            for file in files:
                lower_file = file.lower()
                if not lower_file.endswith(".py"):
                    continue
                if lower_file.startswith("test_") or lower_file[:-3].endswith("_test"):
                    full_path = Path(root) / file
                    total += self._count_tests_in_file(full_path)

        te.total_tests = total
        return te

    async def _testing(
        self, repo_path: str, evidence: CodeQualityEvidence
    ) -> TestingEvidence:
        """Evaluate test evidence safely via static AST counting."""
        te = self._count_tests_ast(repo_path)

        pytest_available = self._tool_available("pytest")
        if not pytest_available and te.total_tests == 0:
            self._degrade_quality(evidence, "testing", "pytest", penalty=0.15)
        else:
            evidence.tools_executed.append("pytest-collect")

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

    @staticmethod
    def _matches_layer(rel_path: str, from_layer: str) -> bool:
        """
        Check if a relative file path belongs to from_layer using exact directory boundaries.
        Prevents substring collisions (e.g. 'rapid_api/' matching 'api/').
        """
        norm = rel_path.replace("\\", "/").strip("/")
        from_clean = from_layer.strip("/")
        if from_clean.endswith(".py"):
            return norm == from_clean or norm.endswith("/" + from_clean)
        parts = norm.split("/")[:-1]  # directory parts only
        from_parts = from_clean.split("/")
        if not from_parts:
            return False
        n, k = len(parts), len(from_parts)
        return any(parts[i:i + k] == from_parts for i in range(n - k + 1))

    @staticmethod
    def _is_subsequence(sub: List[str], seq: List[str]) -> bool:
        """Check if sub appears as a contiguous subsequence in seq."""
        if not sub or len(sub) > len(seq):
            return False
        return any(seq[i:i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))

    @classmethod
    def _ast_has_import_violation(cls, tree: ast.AST, to_layer: str) -> bool:
        """
        Inspect AST import nodes (Import and ImportFrom) for forbidden layer dependencies.
        Ignores comments and string literals. Handles dotted packages and relative imports.
        """
        target_clean = to_layer.strip("/").replace("/", ".")
        target_parts = target_clean.split(".")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if cls._is_subsequence(target_parts, parts):
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_parts = node.module.split(".")
                    if cls._is_subsequence(target_parts, mod_parts):
                        return True
                    for alias in node.names:
                        full_parts = mod_parts + alias.name.split(".")
                        if cls._is_subsequence(target_parts, full_parts):
                            return True
                else:
                    # Relative import without module: from . import database
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if cls._is_subsequence(target_parts, parts):
                            return True
        return False

    def _architecture(self, files: List[str], repo_path: str) -> ArchitectureEvidence:
        """Detect forbidden import patterns using Python AST analysis."""
        violations = []
        FORBIDDEN = [
            ("api/", "database", "API layer should not import database directly"),
            ("routes/", "models", "Routes should go through services, not models directly"),
        ]
        for rel_path in files:
            full_path = Path(repo_path) / rel_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content, filename=str(full_path))
            except (SyntaxError, ValueError, OSError):
                continue

            for from_layer, to_layer, reason in FORBIDDEN:
                if self._matches_layer(rel_path, from_layer):
                    if self._ast_has_import_violation(tree, to_layer):
                        violations.append({
                            "file": rel_path,
                            "violation": reason,
                            "from_layer": from_layer,
                            "to_layer": to_layer,
                        })
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
        if not output or not isinstance(output, str):
            return []
        stripped = output.strip()
        if not stripped:
            return []

        # 1. JSON output compatibility (e.g. flake8-json formatter)
        if stripped.startswith(("{", "[")):
            try:
                data = json.loads(stripped)
                findings: List[Finding] = []
                if isinstance(data, dict):
                    # Format: {"src/app.py": [{"code": "E501", "line_number": 42, "text": "..."}]}
                    for file_path, issues in data.items():
                        if not isinstance(issues, list):
                            continue
                        for issue in issues:
                            if not isinstance(issue, dict):
                                continue
                            code = str(issue.get("code") or "E000").strip()
                            line_no = int(issue.get("line_number") or issue.get("line") or 1)
                            text = str(issue.get("text") or issue.get("message") or "").strip()
                            findings.append(Finding(
                                file_path=file_path,
                                line_number=line_no,
                                rule_id=f"FLAKE8-{code}",
                                category="syntax" if code[0] in ("E", "F", "W") else "maintainability",
                                severity=SeverityEnum.HIGH if code[0] in ("E", "F") else SeverityEnum.MEDIUM,
                                source_tool="flake8",
                                message=text,
                            ))
                    return findings
                elif isinstance(data, list):
                    # Format: [{"filename": "src/app.py", "code": "E501", "line_number": 42, "text": "..."}]
                    for issue in data:
                        if not isinstance(issue, dict):
                            continue
                        file_path = str(issue.get("filename") or issue.get("file") or issue.get("file_path") or "").strip()
                        code = str(issue.get("code") or "E000").strip()
                        line_no = int(issue.get("line_number") or issue.get("line") or 1)
                        text = str(issue.get("text") or issue.get("message") or "").strip()
                        findings.append(Finding(
                            file_path=file_path,
                            line_number=line_no,
                            rule_id=f"FLAKE8-{code}",
                            category="syntax" if code[0] in ("E", "F", "W") else "maintainability",
                            severity=SeverityEnum.HIGH if code[0] in ("E", "F") else SeverityEnum.MEDIUM,
                            source_tool="flake8",
                            message=text,
                        ))
                    return findings
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # 2. Text output regex parsing
        # Matches Windows paths (C:\...), multi-letter plugin codes (ASYNC101, TRY001, BLK100),
        # optional column number, and irregular whitespace around colons.
        findings = []
        pattern = re.compile(r"^(.*?)\s*:\s*(\d+)\s*(?::\s*(\d+))?\s*:\s*([A-Za-z0-9_-]+)\s*(.*)$")
        for line in stripped.splitlines():
            line = line.strip()
            if not line:
                continue
            m = pattern.match(line)
            if m:
                file_path = m.group(1).strip()
                line_no = int(m.group(2))
                code = m.group(4).strip()
                msg = m.group(5).strip()
                findings.append(Finding(
                    file_path=file_path,
                    line_number=line_no,
                    rule_id=f"FLAKE8-{code}",
                    category="syntax" if code[0] in ("E", "F", "W") else "maintainability",
                    severity=SeverityEnum.HIGH if code[0] in ("E", "F") else SeverityEnum.MEDIUM,
                    source_tool="flake8",
                    message=msg,
                ))
        return findings

    @staticmethod
    def _ast_syntax_check(abs_files: List[str], rel_files: List[str]) -> List[Finding]:
        findings = []
        for abs_path, rel_path in zip(abs_files, rel_files):
            try:
                source = Path(abs_path).read_text(encoding="utf-8", errors="replace")
                ast.parse(source)
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
        if not output or not isinstance(output, str):
            return []
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError, TypeError):
            return []

        vulns: List[Dict] = []

        def _extract_pip_audit_dep(dep: dict) -> None:
            if not isinstance(dep, dict):
                return
            pkg_name = str(dep.get("name") or dep.get("package") or "")
            raw_version = dep.get("version")
            version = str(raw_version) if raw_version is not None and str(raw_version).strip() else ""
            raw_vulns = dep.get("vulns")
            vulns_list = raw_vulns if isinstance(raw_vulns, list) else []
            for v in vulns_list:
                if not isinstance(v, dict):
                    continue
                raw_id_val = v.get("id")
                raw_id = str(raw_id_val).strip() if isinstance(raw_id_val, (str, int, float)) else ""
                aliases = v.get("aliases") or []
                if not isinstance(aliases, list):
                    aliases = [aliases] if aliases else []

                # Select CVE identifier (preferring CVE from aliases if id is non-CVE)
                if raw_id.startswith("CVE-"):
                    cve = raw_id
                else:
                    cve_alias = next((a for a in aliases if isinstance(a, str) and a.startswith("CVE-")), None)
                    cve = cve_alias if cve_alias else raw_id

                desc = v.get("description") or f"Vulnerability in {pkg_name}"
                item: Dict[str, Any] = {
                    "package": pkg_name,
                    "severity": str(v.get("severity") or "high"),
                    "cve": cve,
                    "description": str(desc)[:200],
                }
                if version:
                    item["version"] = version
                if aliases:
                    item["aliases"] = aliases
                if "fix_versions" in v and v["fix_versions"]:
                    item["fix_versions"] = v["fix_versions"]
                vulns.append(item)

        # 1. Pip-audit format A: Top-level dict with "dependencies"
        if isinstance(data, dict) and "dependencies" in data:
            deps = data.get("dependencies") or []
            if isinstance(deps, list):
                for dep in deps:
                    _extract_pip_audit_dep(dep)
            return vulns

        # 2. Safety format A: Top-level dict with "vulnerabilities"
        if isinstance(data, dict) and "vulnerabilities" in data:
            v_list = data.get("vulnerabilities") or []
            if isinstance(v_list, list):
                for v in v_list:
                    if not isinstance(v, dict):
                        continue
                    pkg_name = str(v.get("package_name") or v.get("name") or "")
                    desc = str(v.get("advisory") or v.get("description") or "")
                    cve_val = v.get("vulnerability_id") or v.get("id") or v.get("cve") or ""
                    item = {
                        "package": pkg_name,
                        "severity": str(v.get("severity") or "unknown"),
                        "cve": str(cve_val) if cve_val is not None else "",
                        "description": str(desc)[:200],
                    }
                    if "installed_version" in v or "version" in v:
                        item["version"] = str(v.get("installed_version") or v.get("version") or "")
                    vulns.append(item)
            return vulns

        # 3. Top-level list: handles Pip-audit format B (list of deps with "vulns")
        #    as well as Safety format B (list of vulnerability items)
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                if "vulns" in item:
                    # Pip-audit dependency entry with nested "vulns"
                    _extract_pip_audit_dep(item)
                else:
                    # Safety check vulnerability entry
                    pkg_name = str(item.get("name") or item.get("package") or "")
                    desc = str(item.get("description") or item.get("advisory") or "")
                    cve_val = item.get("id") or item.get("vulnerability_id") or item.get("cve") or ""
                    item_dict = {
                        "package": pkg_name,
                        "severity": str(item.get("severity") or "unknown"),
                        "cve": str(cve_val) if cve_val is not None else "",
                        "description": str(desc)[:200],
                    }
                    if "version" in item:
                        item_dict["version"] = item["version"]
                    vulns.append(item_dict)
            return vulns

        return []
