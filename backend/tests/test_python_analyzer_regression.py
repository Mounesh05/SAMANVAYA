"""
Targeted Regression Test Suite for Python Analyzer Reliability (Milestone 2, Task 1.3).
Covers Features 14, 15, 16, 17, 18 with Boundary Value Analysis (BVA),
Malformed Fixture Tolerance, AST Import Rules, and Static Test Discovery.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.evidence.models import (
    CodeQualityEvidence,
    Finding,
    SeverityEnum,
    TestingEvidence,
)


import inspect

def sync_run(coro):
    """
    Run a coroutine synchronously by recursively stepping through yielded child coroutines.
    Guarantees deterministic execution across platforms without starting an IOCP event loop.
    """
    try:
        val = None
        while True:
            sub = coro.send(val)
            val = sync_run(sub) if inspect.iscoroutine(sub) else sub
    except StopIteration as e:
        return e.value


# ==============================================================================
# FEATURE 14: Pip-Audit Format Handling & Vulnerability Extraction
# ==============================================================================

class TestFeature14PipAuditFormatHandling:
    """Verifies parsing of top-level dict, top-level list, CVE alias extraction, and version metadata."""

    def test_top_level_dict_single_dep_single_vuln(self):
        output = json.dumps({
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.25.0",
                    "vulns": [
                        {
                            "id": "CVE-2023-32681",
                            "description": "Requests unintended leak of Proxy-Authorization header",
                            "fix_versions": ["2.31.0"],
                        }
                    ],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "requests"
        assert vulns[0]["cve"] == "CVE-2023-32681"
        assert vulns[0]["version"] == "2.25.0"
        assert vulns[0]["fix_versions"] == ["2.31.0"]
        assert "Proxy-Authorization" in vulns[0]["description"]

    def test_top_level_dict_multiple_vulns_per_dependency(self):
        output = json.dumps({
            "dependencies": [
                {
                    "name": "django",
                    "version": "3.1.2",
                    "vulns": [
                        {"id": "CVE-2021-3281", "description": "Path traversal"},
                        {"id": "CVE-2020-36242", "description": "Buffer overflow"},
                    ],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 2
        cves = {v["cve"] for v in vulns}
        assert "CVE-2021-3281" in cves
        assert "CVE-2020-36242" in cves
        for v in vulns:
            assert v["package"] == "django"
            assert v["version"] == "3.1.2"

    def test_top_level_dict_cve_extracted_from_aliases_when_id_is_ghsa(self):
        output = json.dumps({
            "dependencies": [
                {
                    "name": "urllib3",
                    "version": "1.26.4",
                    "vulns": [
                        {
                            "id": "GHSA-q2q7-5pp4-w6pg",
                            "aliases": ["CVE-2021-33503"],
                            "description": "Catastrophic backtracking in URL authority parser",
                        }
                    ],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["cve"] == "CVE-2021-33503"
        assert vulns[0]["package"] == "urllib3"

    def test_top_level_dict_preserves_package_version_and_name(self):
        output = json.dumps({
            "dependencies": [
                {
                    "name": "cryptography",
                    "version": "3.3.1",
                    "vulns": [{"id": "PYSEC-2021-62", "description": "RSA issue"}],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "cryptography"
        assert vulns[0]["version"] == "3.3.1"

    def test_top_level_list_single_dependency_with_vuln(self):
        output = json.dumps([
            {
                "name": "urllib3",
                "version": "1.26.4",
                "vulns": [
                    {
                        "id": "GHSA-q2q7-5pp4-w6pg",
                        "description": "Urllib3 vulnerability",
                        "aliases": ["CVE-2021-33503"],
                    }
                ],
            }
        ])
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "urllib3"
        assert vulns[0]["cve"] == "CVE-2021-33503"
        assert "Urllib3 vulnerability" in vulns[0]["description"]

    def test_top_level_list_multiple_dependencies_with_empty_and_active_vulns(self):
        output = json.dumps([
            {"name": "requests", "version": "2.31.0", "vulns": []},
            {
                "name": "flask",
                "version": "2.0.1",
                "vulns": [
                    {
                        "id": "GHSA-xxxx-yyyy-zzzz",
                        "aliases": ["CVE-2023-30861"],
                        "description": "Cookie disclosure",
                    }
                ],
            },
            {"name": "black", "version": "24.3.0", "vulns": []},
        ])
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "flask"
        assert vulns[0]["cve"] == "CVE-2023-30861"

    def test_top_level_list_extracts_cve_from_aliases(self):
        output = json.dumps([
            {
                "name": "cryptography",
                "version": "3.3.1",
                "vulns": [
                    {
                        "id": "PYSEC-2021-62",
                        "aliases": ["CVE-2020-36242", "GHSA-x5rh-mg29-hw47"],
                        "description": "Buffer overflow",
                    }
                ],
            }
        ])
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["cve"] == "CVE-2020-36242"

    def test_top_level_list_clean_scan_empty_list_returns_empty(self):
        output = "[]"
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert vulns == []

    def test_top_level_dict_clean_scan_empty_dependencies_returns_empty(self):
        output = json.dumps({"dependencies": []})
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert vulns == []

    def test_clean_scan_with_zero_vulns_across_all_deps_returns_empty(self):
        output = json.dumps({
            "dependencies": [
                {"name": "pytest", "version": "8.3.3", "vulns": []},
                {"name": "pydantic", "version": "2.9.2", "vulns": []},
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert vulns == []

    def test_safety_format_list_compatibility_preserved(self):
        output = json.dumps([
            {
                "name": "django",
                "id": "CVE-2023-1234",
                "severity": "critical",
                "description": "Django SQL injection",
                "version": "3.2.0",
            }
        ])
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "django"
        assert vulns[0]["cve"] == "CVE-2023-1234"
        assert vulns[0]["severity"] == "critical"
        assert vulns[0]["version"] == "3.2.0"

    def test_safety_format_vulnerabilities_dict_compatibility_preserved(self):
        output = json.dumps({
            "vulnerabilities": [
                {
                    "package_name": "jinja2",
                    "vulnerability_id": "CVE-2024-22195",
                    "severity": "high",
                    "advisory": "XSS in jinja2 compiler",
                    "installed_version": "3.1.2",
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "jinja2"
        assert vulns[0]["cve"] == "CVE-2024-22195"
        assert vulns[0]["severity"] == "high"
        assert vulns[0]["version"] == "3.1.2"

    def test_malformed_truncated_json_returns_empty_without_exception(self):
        assert PythonAnalyzer._parse_dep_vulns('{"dependencies": [{"name":') == []
        assert PythonAnalyzer._parse_dep_vulns("") == []
        assert PythonAnalyzer._parse_dep_vulns("None") == []
        assert PythonAnalyzer._parse_dep_vulns("invalid non-json text") == []

    def test_vulnerability_with_none_or_missing_description_uses_fallback(self):
        output = json.dumps({
            "dependencies": [
                {
                    "name": "test-pkg",
                    "version": "1.0.0",
                    "vulns": [{"id": "CVE-TEST-1", "description": None}],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert "Vulnerability in test-pkg" in vulns[0]["description"]

    def test_vulnerability_description_truncated_to_200_chars(self):
        long_desc = "A" * 500
        output = json.dumps({
            "dependencies": [
                {
                    "name": "test-pkg",
                    "version": "1.0.0",
                    "vulns": [{"id": "CVE-TEST-2", "description": long_desc}],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert len(vulns[0]["description"]) == 200


# ==============================================================================
# FEATURE 15: Explicit Dependency Tool Failure Handling
# ==============================================================================

class TestFeature15ExplicitDependencyToolFailureHandling:
    """Verifies tool fallback, clean scan early exit, and explicit quality degradation."""

    def test_clean_pip_audit_scan_does_not_fall_through_to_safety(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-clean", primary_language="python")
        clean_pip_audit = json.dumps({"dependencies": []})
        call_count = 0

        async def fake_run(cmd, cwd=None):
            nonlocal call_count
            call_count += 1
            return clean_pip_audit

        with patch.object(analyzer, "_tool_available", return_value=True):
            with patch.object(py_mod, "_run", fake_run):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert vulns == []
                assert "pip-audit" in evidence.tools_executed
                assert "safety" not in evidence.tools_executed
                assert call_count == 1

    def test_pip_audit_failure_records_explicit_quality_degradation(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-fail", primary_language="python")

        async def fake_run_fail(cmd, cwd=None):
            return None

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "pip-audit"):
            with patch.object(py_mod, "_run", fake_run_fail):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert vulns == []
                assert "pip-audit-failed" in evidence.tools_skipped or "pip-audit" in evidence.tools_skipped
                assert evidence.analysis_quality.confidence < 1.0

    def test_pip_audit_timeout_handled_cleanly_and_degrades_quality(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-timeout", primary_language="python")

        async def fake_run_none(cmd, cwd=None):
            return None

        with patch.object(analyzer, "_tool_available", return_value=True):
            with patch.object(py_mod, "_run", fake_run_none):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert vulns == []
                assert "pip-audit-failed" in evidence.tools_skipped

    def test_fallback_to_safety_when_pip_audit_not_installed(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-fallback", primary_language="python")
        safety_output = json.dumps([{"name": "django", "id": "CVE-2022-1234", "description": "SQLi"}])

        async def fake_run_safety(cmd, cwd=None):
            return safety_output

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "safety"):
            with patch.object(py_mod, "_run", fake_run_safety):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert len(vulns) == 1
                assert "safety" in evidence.tools_executed
                assert "pip-audit" in evidence.tools_skipped

    def test_clean_safety_scan_returns_empty_and_records_safety_executed(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-safety-clean", primary_language="python")

        async def fake_run_safety(cmd, cwd=None):
            return "[]"

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "safety"):
            with patch.object(py_mod, "_run", fake_run_safety):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert vulns == []
                assert "safety" in evidence.tools_executed

    def test_both_dependency_tools_unavailable_records_penalty_and_returns_empty(self):
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-none", primary_language="python")

        with patch.object(analyzer, "_tool_available", return_value=False):
            vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
            assert vulns == []
            assert "pip-audit" in evidence.tools_skipped
            assert "safety" in evidence.tools_skipped
            assert evidence.analysis_quality.confidence < 1.0

    def test_failed_pip_audit_falls_back_to_safety_and_extracts_vulns(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-failover", primary_language="python")
        safety_output = json.dumps([{"name": "flask", "id": "CVE-2023-9999", "description": "Auth bypass"}])

        async def fake_run(cmd, cwd=None):
            if "pip-audit" in cmd[0]:
                return None
            return safety_output

        with patch.object(analyzer, "_tool_available", return_value=True):
            with patch.object(py_mod, "_run", fake_run):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert len(vulns) == 1
                assert vulns[0]["package"] == "flask"
                assert "pip-audit-failed" in evidence.tools_skipped
                assert "safety" in evidence.tools_executed

    def test_invalid_json_cli_error_degrades_quality_and_falls_back(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-err-output", primary_language="python")

        async def fake_run(cmd, cwd=None):
            if "pip-audit" in cmd[0]:
                return "pip-audit: error: failed to resolve requirements"
            return json.dumps([{"name": "urllib3", "id": "CVE-2021-33503"}])

        with patch.object(analyzer, "_tool_available", return_value=True):
            with patch.object(py_mod, "_run", fake_run):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert len(vulns) == 1
                assert "pip-audit-failed" in evidence.tools_skipped
                assert "safety" in evidence.tools_executed


# ==============================================================================
# FEATURE 16: Flake8 Clean Run & Format Compatibility
# ==============================================================================

class TestFeature16Flake8Compatibility:
    """Verifies clean Flake8 runs, multi-letter plugin error codes, Windows paths, and JSON format."""

    def test_clean_run_empty_stdout_returns_empty_and_does_not_degrade_quality(self):
        analyzer = PythonAnalyzer()
        findings = analyzer._parse_flake8("", ["app.py"])
        assert findings == []

    def test_standard_flake8_text_output_parsed(self):
        raw_output = "src/app.py:15:1: F401 'os' imported but unused\n"
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/app.py"])
        assert len(findings) == 1
        assert findings[0].file_path == "src/app.py"
        assert findings[0].line_number == 15
        assert findings[0].rule_id == "FLAKE8-F401"
        assert findings[0].severity == SeverityEnum.HIGH
        assert findings[0].category == "syntax"

    def test_modern_multi_letter_plugin_codes_parsed(self):
        raw_output = (
            "src/worker.py:10:5: ASYNC101 Async function contains blocking call\n"
            "src/utils.py:55:12: TRY001 Use custom exceptions\n"
            "src/main.py:20:1: BLK100 Format error\n"
        )
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/worker.py", "src/utils.py", "src/main.py"])
        assert len(findings) == 3
        rule_ids = [f.rule_id for f in findings]
        assert "FLAKE8-ASYNC101" in rule_ids
        assert "FLAKE8-TRY001" in rule_ids
        assert "FLAKE8-BLK100" in rule_ids

    def test_windows_drive_letter_paths_parsed_correctly(self):
        raw_output = r"C:\project\src\main.py:25:1: F401 'os' imported but unused" + "\n"
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/main.py"])
        assert len(findings) == 1
        assert findings[0].line_number == 25
        assert findings[0].rule_id == "FLAKE8-F401"
        assert findings[0].file_path == r"C:\project\src\main.py"

    def test_windows_relative_paths_with_backslashes_parsed(self):
        raw_output = r"src\models\user.py:5:2: W292 no newline at end of file" + "\n"
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/models/user.py"])
        assert len(findings) == 1
        assert findings[0].line_number == 5
        assert findings[0].rule_id == "FLAKE8-W292"
        assert findings[0].severity == SeverityEnum.MEDIUM

    def test_irregular_whitespace_around_colons_parsed(self):
        raw_output = "src/app.py : 10 : 5 : E501 line too long\n"
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/app.py"])
        assert len(findings) == 1
        assert findings[0].line_number == 10
        assert findings[0].rule_id == "FLAKE8-E501"

    def test_flake8_json_output_dict_format_parsed(self):
        json_output = json.dumps({
            "src/app.py": [
                {
                    "code": "E501",
                    "line_number": 42,
                    "text": "line too long (88 > 79 characters)",
                }
            ],
            "src/worker.py": [
                {
                    "code": "ASYNC101",
                    "line_number": 10,
                    "text": "Async function contains blocking call",
                }
            ],
        })
        findings = PythonAnalyzer._parse_flake8(json_output, ["src/app.py", "src/worker.py"])
        assert len(findings) == 2
        rules = {f.rule_id for f in findings}
        assert "FLAKE8-E501" in rules
        assert "FLAKE8-ASYNC101" in rules

    def test_flake8_json_output_list_format_parsed(self):
        json_output = json.dumps([
            {
                "filename": "src/app.py",
                "code": "F401",
                "line_number": 12,
                "text": "sys imported but unused",
            }
        ])
        findings = PythonAnalyzer._parse_flake8(json_output, ["src/app.py"])
        assert len(findings) == 1
        assert findings[0].file_path == "src/app.py"
        assert findings[0].rule_id == "FLAKE8-F401"
        assert findings[0].line_number == 12

    def test_flake8_json_output_empty_dict_returns_empty_findings(self):
        assert PythonAnalyzer._parse_flake8("{}", ["app.py"]) == []
        assert PythonAnalyzer._parse_flake8("[]", ["app.py"]) == []

    def test_severity_mapping_error_vs_warning(self):
        output = (
            "app.py:1:1: E501 error msg\n"
            "app.py:2:1: F401 error msg\n"
            "app.py:3:1: W503 warning msg\n"
            "app.py:4:1: C901 complex msg\n"
        )
        findings = PythonAnalyzer._parse_flake8(output, ["app.py"])
        assert len(findings) == 4
        assert findings[0].severity == SeverityEnum.HIGH  # E
        assert findings[1].severity == SeverityEnum.HIGH  # F
        assert findings[2].severity == SeverityEnum.MEDIUM  # W
        assert findings[3].severity == SeverityEnum.MEDIUM  # C

    def test_missing_flake8_binary_falls_back_to_ast_syntax_check(self):
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-noflake8", primary_language="python")

        with patch.object(analyzer, "_tool_available", return_value=False):
            with TemporaryDirectory() as tmp_dir:
                good_file = Path(tmp_dir) / "good.py"
                good_file.write_text("x = 1\n", encoding="utf-8")
                findings = sync_run(analyzer._lint(["good.py"], tmp_dir, evidence))
                assert findings == []
                assert "ast-syntax-fallback" in evidence.tools_executed
                assert "flake8" in evidence.tools_skipped

    def test_lint_calling_signatures_3_args_and_4_args(self):
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            file_a = Path(tmp_dir) / "mod.py"
            file_a.write_text("x = 1\n", encoding="utf-8")

            async def fake_run(cmd, cwd=None):
                return ""  # clean run

            with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "flake8"):
                with patch.object(py_mod, "_run", fake_run):
                    # 3-arg invocation: _lint(files, repo_path, evidence)
                    ev3 = CodeQualityEvidence(repository_id="test3", primary_language="python")
                    res3 = sync_run(analyzer._lint(["mod.py"], tmp_dir, ev3))
                    assert res3 == []
                    assert "flake8" in ev3.tools_executed

                    # 4-arg invocation: _lint(files, abs_files, repo_path, evidence)
                    ev4 = CodeQualityEvidence(repository_id="test4", primary_language="python")
                    res4 = sync_run(analyzer._lint(["mod.py"], [str(file_a)], tmp_dir, ev4))
                    assert res4 == []
                    assert "flake8" in ev4.tools_executed


# ==============================================================================
# FEATURE 17: Python-Aware AST Architecture Rules
# ==============================================================================

class TestFeature17PythonAwareASTArchitectureRules:
    """Verifies AST-based import analysis ignoring comments/strings and detecting qualified imports."""

    def test_direct_import_violation_detected(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "users.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("import database\n", encoding="utf-8")
            arch = analyzer._architecture(["api/users.py"], tmp_dir)
            assert len(arch.layer_violations) == 1
            assert "database" in arch.layer_violations[0]["to_layer"]

    def test_from_import_violation_detected(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "orders.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from database import get_session\n", encoding="utf-8")
            arch = analyzer._architecture(["api/orders.py"], tmp_dir)
            assert len(arch.layer_violations) == 1
            assert "database" in arch.layer_violations[0]["to_layer"]

    def test_package_qualified_import_violation_detected(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "payments.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from app.database import get_db\n", encoding="utf-8")
            arch = analyzer._architecture(["api/payments.py"], tmp_dir)
            assert len(arch.layer_violations) == 1
            assert "database" in arch.layer_violations[0]["to_layer"]

    def test_import_qualified_module_violation_detected(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "checkout.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("import app.database\n", encoding="utf-8")
            arch = analyzer._architecture(["api/checkout.py"], tmp_dir)
            assert len(arch.layer_violations) == 1

    def test_relative_import_violation_detected(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "routes" / "users.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from ..models import User\n", encoding="utf-8")
            arch = analyzer._architecture(["routes/users.py"], tmp_dir)
            assert len(arch.layer_violations) == 1
            assert "models" in arch.layer_violations[0]["to_layer"]

    def test_relative_import_dot_syntax_violation_detected(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "db_helper.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from . import database\n", encoding="utf-8")
            arch = analyzer._architecture(["api/db_helper.py"], tmp_dir)
            assert len(arch.layer_violations) == 1

    def test_comments_containing_forbidden_imports_ignored(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "safe.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("# from database import session  -- legacy comment\nx = 1\n", encoding="utf-8")
            arch = analyzer._architecture(["api/safe.py"], tmp_dir)
            assert len(arch.layer_violations) == 0

    def test_string_literals_containing_forbidden_imports_ignored(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "query.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('sql = "SELECT id from database"\n', encoding="utf-8")
            arch = analyzer._architecture(["api/query.py"], tmp_dir)
            assert len(arch.layer_violations) == 0

    def test_docstrings_containing_forbidden_imports_ignored(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "doc.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            doc = '"""Module documentation: do not import database here."""\nx = 1\n'
            f.write_text(doc, encoding="utf-8")
            arch = analyzer._architecture(["api/doc.py"], tmp_dir)
            assert len(arch.layer_violations) == 0

    def test_path_boundary_no_substring_false_positive(self):
        """'rapid_api/' must not match 'api/' layer rule."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "rapid_api" / "handler.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("import database\n", encoding="utf-8")
            arch = analyzer._architecture(["rapid_api/handler.py"], tmp_dir)
            assert len(arch.layer_violations) == 0

    def test_routes_layer_to_models_violation_detected(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "routes" / "items.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from models import Item\n", encoding="utf-8")
            arch = analyzer._architecture(["routes/items.py"], tmp_dir)
            assert len(arch.layer_violations) == 1
            assert "models" in arch.layer_violations[0]["to_layer"]

    def test_syntax_error_in_file_handled_safely_without_crash(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "broken.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("def broken(:\n", encoding="utf-8")
            arch = analyzer._architecture(["api/broken.py"], tmp_dir)
            assert arch.layer_violations == []

    def test_multiple_files_and_multiple_violations_aggregated(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "api" / "u.py"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("import database\n", encoding="utf-8")

            f2 = Path(tmp_dir) / "routes" / "r.py"
            f2.parent.mkdir(parents=True, exist_ok=True)
            f2.write_text("from models import User\n", encoding="utf-8")

            arch = analyzer._architecture(["api/u.py", "routes/r.py"], tmp_dir)
            assert len(arch.layer_violations) == 2


# ==============================================================================
# FEATURE 18: Static AST Test Counting & Pytest Output Parsing
# ==============================================================================

class TestFeature18StaticASTTestCounting:
    """Verifies static test discovery via AST without code execution, and regex collection parsing."""

    def test_counts_top_level_test_functions(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_math.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("def test_add(): pass\ndef test_sub(): pass\n", encoding="utf-8")
            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 2

    def test_counts_async_top_level_test_functions(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_async.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("async def test_async_fetch(): pass\n", encoding="utf-8")
            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 1

    def test_counts_test_class_methods(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_suite.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            code = (
                "class TestSuite:\n"
                "    def test_one(self): pass\n"
                "    def test_two(self): pass\n"
                "    def helper(self): pass\n"
            )
            f.write_text(code, encoding="utf-8")
            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 2

    def test_ignores_helper_methods_in_test_classes(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_helpers.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            code = (
                "class TestHelpers:\n"
                "    def setup_method(self): pass\n"
                "    def teardown_method(self): pass\n"
                "    def test_valid(self): pass\n"
            )
            f.write_text(code, encoding="utf-8")
            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 1

    def test_ignores_classes_with_init(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_init.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            code = (
                "class TestInvalid:\n"
                "    def __init__(self): pass\n"
                "    def test_method(self): pass\n"
            )
            f.write_text(code, encoding="utf-8")
            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 0

    def test_untrusted_side_effect_code_never_executed(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_malicious.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(
                "raise RuntimeError('Untrusted arbitrary code execution')\n"
                "def test_safe(): pass\n",
                encoding="utf-8",
            )
            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 1

    def test_discovers_tests_across_nested_subdirectories(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "tests" / "unit" / "test_u.py"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("def test_unit(): pass\n", encoding="utf-8")

            f2 = Path(tmp_dir) / "tests" / "integration" / "test_i.py"
            f2.parent.mkdir(parents=True, exist_ok=True)
            f2.write_text("def test_integ(): pass\n", encoding="utf-8")

            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 2

    def test_syntax_error_in_test_file_skipped_without_crashing_suite(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "tests" / "test_broken.py"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("def test_broken(:\n", encoding="utf-8")

            f2 = Path(tmp_dir) / "tests" / "test_good.py"
            f2.parent.mkdir(parents=True, exist_ok=True)
            f2.write_text("def test_good(): pass\n", encoding="utf-8")

            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 1

    def test_large_repository_hundred_tests_counted_accurately(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_hundred.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            code = "\n".join(f"def test_{i}(): pass" for i in range(100))
            f.write_text(code, encoding="utf-8")
            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 100

    def test_skips_excluded_directories(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "venv" / "test_lib.py"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("def test_venv(): pass\n", encoding="utf-8")

            f2 = Path(tmp_dir) / "node_modules" / "test_node.py"
            f2.parent.mkdir(parents=True, exist_ok=True)
            f2.write_text("def test_node(): pass\n", encoding="utf-8")

            f3 = Path(tmp_dir) / "tests" / "test_real.py"
            f3.parent.mkdir(parents=True, exist_ok=True)
            f3.write_text("def test_real(): pass\n", encoding="utf-8")

            te = analyzer._count_tests_ast(tmp_dir)
            assert te.total_tests == 1

    def test_pytest_regex_parses_collected_n_items(self):
        assert PythonAnalyzer._parse_pytest_output("rootdir: /repo\ncollected 14 items\n") == 14

    def test_pytest_regex_parses_n_tests_collected(self):
        assert PythonAnalyzer._parse_pytest_output("8 tests collected in 0.05s\n") == 8

    def test_pytest_regex_parses_n_items_collected(self):
        assert PythonAnalyzer._parse_pytest_output("2 items collected in 0.02s\n") == 2

    def test_pytest_regex_parses_collected_n_tests(self):
        assert PythonAnalyzer._parse_pytest_output("collected 5 tests\n") == 5

    def test_pytest_regex_parses_selected_and_deselected(self):
        assert PythonAnalyzer._parse_pytest_output("collected 25 items / 5 deselected / 20 selected\n") == 20

    def test_pytest_regex_handles_zero_and_singular_items(self):
        assert PythonAnalyzer._parse_pytest_output("collected 1 item\n") == 1
        assert PythonAnalyzer._parse_pytest_output("collected 0 items\n") == 0

    def test_pytest_regex_returns_none_for_unrelated_output(self):
        assert PythonAnalyzer._parse_pytest_output("") is None
        assert PythonAnalyzer._parse_pytest_output("No tests were run.") is None


# ==============================================================================
# BOUNDARY VALUE ANALYSIS (BVA) & COMPOSITE SCENARIOS
# ==============================================================================

class TestPythonAnalyzerBoundaryAndCompositeScenarios:
    """Verifies empty repos, unicode files, mixed findings, and quality calculations."""

    def test_empty_changed_files_list_returns_empty_evidence(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            ev = sync_run(analyzer.analyze([], tmp_dir))
            assert ev.files_analyzed == 0
            assert ev.static_findings == []
            assert ev.security.findings == []

    def test_non_python_files_filtered_out(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            ev = sync_run(analyzer.analyze(["readme.md", "app.js"], tmp_dir))
            assert ev.files_analyzed == 0

    def test_pyi_type_stub_files_supported(self):
        analyzer = PythonAnalyzer()
        assert ".pyi" in analyzer.supported_extensions

    def test_unicode_and_special_characters_in_source_handled(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "unicode_mod.py"
            f.write_text("# 日本語コメント\nhello = 'こんにちは'\n", encoding="utf-8")
            findings = analyzer._ast_syntax_check([str(f)], ["unicode_mod.py"])
            assert findings == []

    def test_analyze_method_default_pr_context_none(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            f.write_text("x = 1\n", encoding="utf-8")
            with patch("shutil.which", return_value=None):
                ev = sync_run(analyzer.analyze(["app.py"], tmp_dir))
                assert ev.files_analyzed == 1
                assert ev.primary_language == "python"

    def test_composite_full_analyze_pipeline_integration(self):
        analyzer = PythonAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            api_file = Path(tmp_dir) / "api" / "users.py"
            api_file.parent.mkdir(parents=True, exist_ok=True)
            api_file.write_text("import database\n", encoding="utf-8")

            test_file = Path(tmp_dir) / "tests" / "test_api.py"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text("def test_get_users(): pass\n", encoding="utf-8")

            with patch("shutil.which", return_value=None):
                ev = sync_run(analyzer.analyze(["api/users.py", "tests/test_api.py"], tmp_dir))
                assert ev.files_analyzed == 2
                assert len(ev.architecture.layer_violations) == 1
                assert ev.testing.total_tests == 1


# ==============================================================================
# DEFENSIVE SCHEMA RELIABILITY & CRASH RESILIENCE REGRESSION TESTS
# ==============================================================================

class TestDefensiveSchemaReliabilityAndCrashResilience:
    """
    Regression coverage for defensive parsing of dirty scanner schemas and
    crash-resilient degradation in dependency scanning (Features 14 & 15).
    """

    def test_vulnerability_with_numeric_ids(self):
        """Feature 14: Numeric vulnerability IDs (positive, zero, float) must not raise AttributeError."""
        cases = [
            (9999, "9999"),
            (0, "0"),
            (123456, "123456"),
            (42.5, "42.5"),
        ]
        for num_id, expected_cve in cases:
            output = json.dumps({
                "dependencies": [
                    {
                        "name": "foo-pkg",
                        "version": "1.0.0",
                        "vulns": [
                            {"id": num_id, "description": f"Numeric ID {num_id}"}
                        ]
                    }
                ]
            })
            vulns = PythonAnalyzer._parse_dep_vulns(output)
            assert len(vulns) == 1
            assert vulns[0]["package"] == "foo-pkg"
            assert vulns[0]["cve"] == expected_cve
            assert vulns[0]["version"] == "1.0.0"

    def test_vulnerability_with_numeric_id_and_cve_alias_promotion(self):
        """Feature 14: When id is numeric, CVE alias must still be preferred if present."""
        output = json.dumps({
            "dependencies": [
                {
                    "name": "crypto-dep",
                    "version": "2.1.0",
                    "vulns": [
                        {
                            "id": 8888,
                            "aliases": ["PYSEC-2023-1", "CVE-2023-9999"],
                            "description": "Numeric ID with CVE alias"
                        }
                    ]
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["cve"] == "CVE-2023-9999"

    def test_dependencies_with_non_iterable_vulns_attribute(self):
        """Feature 14: Non-list vulns values (int, bool, string, float, dict) must return empty list without TypeError."""
        for dirty in [123, True, False, "invalid-vulns-string", 45.6, {"not": "a list"}]:
            output = json.dumps({
                "dependencies": [
                    {"name": "test-pkg", "version": "1.0.0", "vulns": dirty}
                ]
            })
            vulns = PythonAnalyzer._parse_dep_vulns(output)
            assert vulns == [], f"Expected empty list for dirty vulns {dirty}, got {vulns}"

    def test_top_level_list_with_numeric_id_and_non_iterable_vulns(self):
        """Feature 14: Top-level list schema with numeric id and non-list vulns handled cleanly."""
        output = json.dumps([
            {"name": "clean-pkg", "vulns": 999},
            {
                "name": "dirty-id-pkg",
                "vulns": [{"id": 7777, "description": "Numeric ID in list"}]
            }
        ])
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "dirty-id-pkg"
        assert vulns[0]["cve"] == "7777"

    def test_dependencies_pipeline_successful_numeric_id_accounting(self):
        """Feature 15: Pipeline does not crash or trigger spurious fallback when pip-audit produces numeric ID."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        output = json.dumps({
            "dependencies": [
                {
                    "name": "sec-lib",
                    "version": "1.5.0",
                    "vulns": [{"id": 4321, "description": "Advisory description"}]
                }
            ]
        })

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = output
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "4321"
            assert res[0]["package"] == "sec-lib"
            assert evidence.tools_executed == ["pip-audit"]
            assert "pip-audit-failed" not in evidence.tools_skipped
            assert "safety" not in evidence.tools_executed
            assert evidence.analysis_quality.confidence == 1.0

    def test_dependencies_pipeline_recovers_from_unhandled_parser_exception(self):
        """Feature 15: Unhandled exceptions during parsing are caught, quality is degraded, and fallback tool executes."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([
            {
                "name": "safety-pkg",
                "version": "2.0.0",
                "id": "CVE-2023-5555",
                "advisory": "Fallback vulnerability found"
            }
        ])

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ["{}", safety_output]
            with patch.object(analyzer, "_parse_dep_vulns", side_effect=[RuntimeError("Simulated unhandled parser error"), [{"package": "safety-pkg", "cve": "CVE-2023-5555"}]]):
                res = sync_run(analyzer._dependencies(".", evidence))

                assert res == [{"package": "safety-pkg", "cve": "CVE-2023-5555"}]
                # pip-audit must NOT be in tools_executed because parsing failed
                assert evidence.tools_executed == ["safety"]
                assert "pip-audit-failed" in evidence.tools_skipped
                assert round(evidence.analysis_quality.confidence, 2) == 0.95

    def test_dependencies_pipeline_both_tools_raising_unhandled_exceptions(self):
        """Feature 15: When all tools encounter unhandled exceptions, pipeline degrades quality without crashing."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ["{}", "{}"]
            with patch.object(analyzer, "_parse_dep_vulns", side_effect=KeyError("Simulated missing key error")):
                res = sync_run(analyzer._dependencies(".", evidence))

                assert res == []
                assert evidence.tools_executed == []
                assert "pip-audit-failed" in evidence.tools_skipped
                assert "safety-failed" in evidence.tools_skipped
                assert round(evidence.analysis_quality.confidence, 2) == 0.90


# ==============================================================================
# FEATURE 15 (SUPPLEMENT): Subprocess Exception Recovery & analyze() Resilience
# ==============================================================================

class CustomToolExecutionError(Exception):
    """Custom exception simulating arbitrary subprocess failure."""
    pass


class TestSubprocessExceptionRecoveryAndAnalyzeResilience:
    """
    Verifies catastrophic tool execution exception recovery in _dependencies,
    fallback to safety, correct evidence auditing, and analyze() crash resilience.
    """

    def test_run_memory_error_during_pip_audit_degrades_and_falls_back_to_safety(self):
        """When _run raises MemoryError during pip-audit, _dependencies must degrade and fall back to safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([
            {"package": "safety-pkg", "id": "CVE-2023-7777", "description": "Fallback advisory"}
        ])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [MemoryError("Out of memory during pip-audit execution"), safety_output]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-7777"
            assert res[0]["package"] == "safety-pkg"
            assert evidence.tools_executed == ["safety"]
            assert "pip-audit-failed" in evidence.tools_skipped
            assert round(evidence.analysis_quality.confidence, 2) == 0.95

    def test_run_unicode_decode_error_during_pip_audit_degrades_and_falls_back_to_safety(self):
        """When _run raises UnicodeDecodeError during pip-audit, _dependencies must degrade and fall back to safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([
            {"package": "safety-pkg", "id": "CVE-2023-8888", "description": "Fallback advisory"}
        ])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), safety_output]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-8888"
            assert evidence.tools_executed == ["safety"]
            assert "pip-audit-failed" in evidence.tools_skipped
            assert round(evidence.analysis_quality.confidence, 2) == 0.95

    def test_run_custom_subprocess_exception_during_pip_audit_degrades_and_falls_back(self):
        """When _run raises CustomToolExecutionError during pip-audit, _dependencies must degrade and fall back to safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([
            {"package": "safety-pkg", "id": "CVE-2023-9999", "description": "Fallback advisory"}
        ])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [CustomToolExecutionError("Subprocess failed abnormally"), safety_output]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-9999"
            assert evidence.tools_executed == ["safety"]
            assert "pip-audit-failed" in evidence.tools_skipped
            assert round(evidence.analysis_quality.confidence, 2) == 0.95

    def test_run_both_dependency_tools_catastrophic_exceptions_handled(self):
        """When both pip-audit and safety raise catastrophic execution exceptions, quality degrades and [] is returned."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                MemoryError("pip-audit OOM"),
                RuntimeError("safety process died"),
            ]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert res == []
            assert evidence.tools_executed == []
            assert "pip-audit-failed" in evidence.tools_skipped
            assert "safety-failed" in evidence.tools_skipped
            assert round(evidence.analysis_quality.confidence, 2) == 0.90

    def test_analyze_end_to_end_resilience_on_dependency_tool_runner_memory_error(self):
        """End-to-end analyze() pipeline must never crash when pip-audit execution throws MemoryError."""
        analyzer = PythonAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            f.write_text("import os\n", encoding="utf-8")

            async def selective_run(cmd, cwd=None):
                if cmd and "pip-audit" in cmd[0]:
                    raise MemoryError("OOM inside tool runner")
                if cmd and "safety" in cmd[0]:
                    return json.dumps([{"package": "pkg1", "id": "CVE-2024-0001"}])
                return None

            with patch.object(analyzer, "_tool_available", return_value=True), \
                 patch("intelligence.analyzers.python.analyzer._run", side_effect=selective_run):
                ev = sync_run(analyzer.analyze(["app.py"], tmp_dir))

                assert ev.files_analyzed == 1
                assert len(ev.security.dependency_vulnerabilities) == 1
                assert ev.security.dependency_vulnerabilities[0]["cve"] == "CVE-2024-0001"
                assert "safety" in ev.tools_executed
                assert "pip-audit-failed" in ev.tools_skipped
                assert ev.analysis_duration_ms > 0

    def test_analyze_end_to_end_resilience_when_all_dependency_tools_crash_in_run(self):
        """End-to-end analyze() must complete with valid evidence when all dependency tools crash during execution."""
        analyzer = PythonAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            f.write_text("x = 42\n", encoding="utf-8")

            async def crashing_run(cmd, cwd=None):
                if cmd and ("pip-audit" in cmd[0] or "safety" in cmd[0]):
                    raise RuntimeError("All dependency tools crashing")
                return None

            with patch.object(analyzer, "_tool_available", return_value=True), \
                 patch("intelligence.analyzers.python.analyzer._run", side_effect=crashing_run):
                ev = sync_run(analyzer.analyze(["app.py"], tmp_dir))

                assert ev.files_analyzed == 1
                assert ev.security.dependency_vulnerabilities == []
                assert "pip-audit-failed" in ev.tools_skipped
                assert "safety-failed" in ev.tools_skipped
                assert ev.complexity is not None
                assert ev.testing is not None
                assert ev.architecture is not None
                assert ev.analysis_duration_ms > 0

    def test_analyze_end_to_end_resilience_when_passes_raise_unexpected_exceptions(self):
        """End-to-end analyze() must complete and never raise when individual passes fail catastrophically."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "mod.py"
            f.write_text("a = 1\n", encoding="utf-8")

            with patch.object(analyzer, "_lint", side_effect=RuntimeError("Lint crash")), \
                 patch.object(analyzer, "_security", side_effect=TypeError("Security crash")), \
                 patch.object(analyzer, "_architecture", side_effect=ValueError("Architecture crash")):
                ev = sync_run(analyzer.analyze(["mod.py"], tmp_dir))

                assert ev.files_analyzed == 1
                assert "lint-pipeline-failed" in ev.tools_skipped
                assert "security-pipeline-failed" in ev.tools_skipped
                assert "architecture-pipeline-failed" in ev.tools_skipped
                assert ev.analysis_duration_ms > 0

    def test_run_helper_absorbs_unexpected_exceptions_and_empty_command(self):
        """Direct unit test of _run: empty command list and subprocess execution errors return None cleanly."""
        from intelligence.analyzers.python.analyzer import _run

        # Empty command returns None
        assert sync_run(_run([])) is None

        # Catastrophic exception during subprocess execution returns None cleanly
        with patch("asyncio.create_subprocess_exec", side_effect=MemoryError("Subprocess OOM")):
            assert sync_run(_run(["pip-audit"])) is None

        with patch("asyncio.create_subprocess_exec", side_effect=RuntimeError("Subprocess spawn failed")):
            assert sync_run(_run(["safety"])) is None
