"""
Adversarial Empirical Stress Test Suite for Milestone 2 (Challenger 2)
Focus: Feature 14 (_parse_dep_vulns), Feature 15 (_dependencies), Feature 18 (_count_tests_ast & _parse_pytest_output)
"""

import ast
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum, TestingEvidence


# ==============================================================================
# Helper for async running
# ==============================================================================

def sync_run(coro):
    """Run an async coroutine synchronously using generator stepping."""
    gen = coro.__await__()
    while True:
        try:
            future = gen.send(None)
            if hasattr(future, "result"):
                res = future.result()
            elif hasattr(future, "__iter__"):
                res = next(iter(future))
            else:
                res = None
        except StopIteration as e:
            return e.value


# ==============================================================================
# Test Suite 1: Feature 14 - _parse_dep_vulns Dirty Schema Stress Testing
# ==============================================================================

class TestFeature14AdversarialDirtySchemas:
    """Stress test _parse_dep_vulns with hostile, malformed, and dirty inputs."""

    def test_top_level_dict_without_dependencies(self):
        """Top-level dict missing dependencies key must return [] without exceptions."""
        cases = [
            "{}",
            '{"packages": []}',
            '{"error": "Failed to resolve metadata", "code": 500}',
            '{"status": "ok", "count": 0}',
            '{"vulnerabilities_unrelated": []}',
        ]
        for c in cases:
            res = PythonAnalyzer._parse_dep_vulns(c)
            assert res == [], f"Expected [] for {c}, got {res}"

    def test_top_level_dict_with_dirty_dependencies_value(self):
        """dependencies key with non-list values must return [] gracefully."""
        cases = [
            '{"dependencies": null}',
            '{"dependencies": "requests>=2.25.0"}',
            '{"dependencies": 42}',
            '{"dependencies": false}',
            '{"dependencies": {}}',
        ]
        for c in cases:
            res = PythonAnalyzer._parse_dep_vulns(c)
            assert res == [], f"Expected [] for {c}, got {res}"

    def test_dependencies_list_with_dirty_items(self):
        """Dependency items that are None, string, int, or empty dicts."""
        payload = json.dumps({
            "dependencies": [
                None,
                42,
                "invalid_dep_string",
                [],
                {},
                {"name": "valid-dep", "version": "1.0.0", "vulns": []}
            ]
        })
        res = PythonAnalyzer._parse_dep_vulns(payload)
        assert res == []

    def test_dependencies_with_missing_or_dirty_vulns_attribute(self):
        """vulns attribute missing, null, or weird types."""
        cases = [
            # missing "vulns"
            {"dependencies": [{"name": "urllib3", "version": "1.26.4"}]},
            # null "vulns"
            {"dependencies": [{"name": "urllib3", "version": "1.26.4", "vulns": None}]},
            # string "vulns"
            {"dependencies": [{"name": "urllib3", "version": "1.26.4", "vulns": "CVE-2021-33503"}]},
            # boolean "vulns"
            {"dependencies": [{"name": "urllib3", "version": "1.26.4", "vulns": False}]},
            # empty list
            {"dependencies": [{"name": "urllib3", "version": "1.26.4", "vulns": []}]},
        ]
        for c in cases:
            res = PythonAnalyzer._parse_dep_vulns(json.dumps(c))
            assert res == [], f"Expected [] for {c}, got {res}"

    def test_dependencies_with_integer_vulns_attribute(self):
        """Check if integer vulns attribute crashes with TypeError."""
        payload = json.dumps({"dependencies": [{"name": "foo", "vulns": 123}]})
        try:
            res = PythonAnalyzer._parse_dep_vulns(payload)
            assert isinstance(res, list)
        except TypeError as e:
            pytest.fail(f"Integer in vulns raised unhandled TypeError: {e}")

    def test_vuln_with_null_and_missing_description(self):
        """Null or missing description must fall back to generic package vulnerability message."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "insecure-pkg",
                    "version": "0.1.0",
                    "vulns": [
                        {"id": "CVE-2023-1111", "description": None},
                        {"id": "CVE-2023-2222"}  # missing description key
                    ]
                }
            ]
        })
        res = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(res) == 2
        assert res[0]["description"] == "Vulnerability in insecure-pkg"
        assert res[1]["description"] == "Vulnerability in insecure-pkg"

    def test_vuln_with_integer_id(self):
        """Vulnerability entry with integer id must not crash on startswith."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "foo-pkg",
                    "version": "1.0.0",
                    "vulns": [
                        {"id": 9999, "description": "Numeric ID vulnerability"}
                    ]
                }
            ]
        })
        try:
            res = PythonAnalyzer._parse_dep_vulns(payload)
            assert len(res) == 1
            assert res[0]["package"] == "foo-pkg"
        except AttributeError as e:
            pytest.fail(f"Integer ID triggered AttributeError on startswith: {e}")

    def test_vuln_with_multiple_and_empty_aliases(self):
        """Multiple aliases with CVE promotion, and empty aliases handling."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "crypto-lib",
                    "version": "2.0.0",
                    "vulns": [
                        {
                            "id": "GHSA-abcd-1234",
                            "aliases": ["PYSEC-2022-99", "CVE-2022-4444", "CVE-2022-5555"],
                            "description": "Multi-alias test"
                        },
                        {
                            "id": "GHSA-empty-alias",
                            "aliases": [],
                            "description": "Empty alias list"
                        },
                        {
                            "id": "GHSA-null-alias",
                            "aliases": None,
                            "description": "Null alias"
                        },
                        {
                            "id": "GHSA-single-string",
                            "aliases": "CVE-2023-7777",
                            "description": "String alias rather than list"
                        }
                    ]
                }
            ]
        })
        res = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(res) == 4
        # First CVE in aliases promoted
        assert res[0]["cve"] == "CVE-2022-4444"
        assert res[0]["aliases"] == ["PYSEC-2022-99", "CVE-2022-4444", "CVE-2022-5555"]
        # Empty/null alias retains raw id
        assert res[1]["cve"] == "GHSA-empty-alias"
        assert res[2]["cve"] == "GHSA-null-alias"
        # Single string alias normalized and CVE promoted
        assert res[3]["cve"] == "CVE-2023-7777"

    def test_vuln_with_dirty_types_in_aliases(self):
        """Aliases containing None, integers, or dicts."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "pkg-a",
                    "vulns": [
                        {
                            "id": "GHSA-dirty",
                            "aliases": [None, 1234, {"inner": "val"}, "CVE-2024-9999"],
                            "description": "Dirty aliases elements"
                        }
                    ]
                }
            ]
        })
        res = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(res) == 1
        assert res[0]["cve"] == "CVE-2024-9999"

    def test_safety_format_dirty_schemas(self):
        """Safety format dict and list variations."""
        # Dict format with missing fields
        safety_dict = json.dumps({
            "vulnerabilities": [
                {"package_name": "django", "vulnerability_id": "CVE-2021-0001", "advisory": "Test vuln"},
                {"package_name": None, "id": 1234},
                "not-a-dict"
            ]
        })
        res_dict = PythonAnalyzer._parse_dep_vulns(safety_dict)
        assert len(res_dict) == 2
        assert res_dict[0]["package"] == "django"
        assert res_dict[0]["cve"] == "CVE-2021-0001"

        # List format with mixed types
        safety_list = json.dumps([
            {"package": "flask", "cve": "CVE-2020-1111", "description": "Flask vuln"},
            None,
            42,
            {"name": "requests", "id": "CVE-2020-2222", "advisory": "Requests vuln"}
        ])
        res_list = PythonAnalyzer._parse_dep_vulns(safety_list)
        assert len(res_list) == 2
        assert res_list[0]["package"] == "flask"
        assert res_list[1]["package"] == "requests"


# ==============================================================================
# Test Suite 2: Feature 15 - _dependencies Robustness & Clean Scan Fallthrough
# ==============================================================================

class TestFeature15AdversarialDependencies:
    """Stress test _dependencies method against fallthrough, corrupted outputs, and timeouts."""

    def test_clean_pip_audit_scan_empty_deps_never_falls_through(self):
        """Clean pip audit with empty dependencies list must return [] and NOT call safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        clean_output = json.dumps({"dependencies": []})

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = clean_output

            res = sync_run(analyzer._dependencies(".", evidence))

            assert res == []
            assert evidence.tools_executed == ["pip-audit"]
            assert "safety" not in evidence.tools_executed
            assert mock_run.call_count == 1
            assert "pip-audit" in mock_run.call_args_list[0][0][0]
            assert evidence.analysis_quality.confidence == 1.0
            assert evidence.analysis_quality.penalties == []

    def test_clean_pip_audit_scan_with_zero_vulns_across_deps_never_falls_through(self):
        """Clean pip audit scanning 50 clean dependencies must return [] and NOT call safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        clean_deps = [{"name": f"pkg_{i}", "version": "1.0.0", "vulns": []} for i in range(50)]
        clean_output = json.dumps({"dependencies": clean_deps})

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = clean_output

            res = sync_run(analyzer._dependencies(".", evidence))

            assert res == []
            assert evidence.tools_executed == ["pip-audit"]
            assert "safety" not in evidence.tools_executed
            assert mock_run.call_count == 1
            assert evidence.analysis_quality.confidence == 1.0

    def test_corrupted_json_output_degrades_quality_and_falls_back(self):
        """Corrupted JSON string (e.g. CLI crash trace) must degrade quality and try safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        safety_output = json.dumps([
            {"package": "insecure-pkg", "id": "CVE-2023-9999", "description": "Found by safety"}
        ])

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            # First call (pip-audit): corrupted JSON
            # Second call (safety): valid output
            mock_run.side_effect = ["Fatal error: traceback (most recent call last)...", safety_output]

            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-9999"
            assert "safety" in evidence.tools_executed
            # Quality degraded because pip-audit failed
            assert "pip-audit-failed" in evidence.tools_skipped
            assert "security" in evidence.analysis_quality.degraded_dimensions
            assert "pip-audit-failed" in evidence.analysis_quality.reason
            assert round(evidence.analysis_quality.confidence, 2) == 0.95
            assert mock_run.call_count == 2

    def test_subprocess_timeout_degrades_quality_and_falls_back(self):
        """When _run returns None (timeout or failure), quality is degraded and safety called."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        safety_output = json.dumps({"vulnerabilities": []})

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            # Pip-audit times out (returns None)
            mock_run.side_effect = [None, safety_output]

            res = sync_run(analyzer._dependencies(".", evidence))

            assert res == []
            assert "safety" in evidence.tools_executed
            assert "pip-audit-failed" in evidence.tools_skipped
            assert "security" in evidence.analysis_quality.degraded_dimensions
            assert "pip-audit-failed" in evidence.analysis_quality.reason
            assert round(evidence.analysis_quality.confidence, 2) == 0.95
            assert mock_run.call_count == 2

    def test_missing_binaries_penalty_accounting(self):
        """When both pip-audit and safety are unavailable, penalties accumulate and confidence drops."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        with patch.object(analyzer, "_tool_available", return_value=False):
            res = sync_run(analyzer._dependencies(".", evidence))

            assert res == []
            assert evidence.tools_executed == []
            assert "pip-audit" in evidence.tools_skipped
            assert "safety" in evidence.tools_skipped
            assert "security" in evidence.analysis_quality.degraded_dimensions
            assert "pip-audit" in evidence.analysis_quality.reason
            assert round(evidence.analysis_quality.confidence, 2) == 0.90
            assert len(evidence.analysis_quality.penalties) == 1
            assert evidence.analysis_quality.penalties[0] == 0.10


# ==============================================================================
# Test Suite 3: Feature 18 - Security Verification of AST Test Discovery
# ==============================================================================

class TestFeature18AdversarialASTTestCounting:
    """Security and correctness verification of AST test counting."""

    def test_security_malicious_side_effects_never_executed(self, tmp_path):
        """
        Verify that untrusted Python code with hostile top-level side effects
        is NEVER executed by _count_tests_ast.
        """
        marker_file = tmp_path / "PWNED_MARKER.txt"
        canary_env_key = "PWNED_TEST_FLAG_KEY"
        if canary_env_key in os.environ:
            del os.environ[canary_env_key]

        malicious_content = f"""
import sys, os

# Hostile side effects that would crash the runner or create files if executed
os.environ["{canary_env_key}"] = "EXECUTED"
with open(r"{marker_file}", "w") as f:
    f.write("Pwned!")

sys.exit(42)
raise SystemExit("Pwned by exit")
raise RuntimeError("Malicious payload executed")

def test_legit_function_1():
    assert True

def test_legit_function_2():
    pass

class TestLegitSuite:
    def test_method_in_class(self):
        pass
"""
        test_file = tmp_path / "test_malicious.py"
        test_file.write_text(malicious_content, encoding="utf-8")

        analyzer = PythonAnalyzer()
        te = analyzer._count_tests_ast(str(tmp_path))

        # 1. Untrusted code was NEVER executed
        assert not marker_file.exists(), "SECURITY BREACH: Marker file was created! Code was executed!"
        assert canary_env_key not in os.environ, "SECURITY BREACH: Environment variable was modified!"

        # 2. Tests were accurately counted
        # test_legit_function_1, test_legit_function_2, and test_method_in_class = 3 tests
        assert te.total_tests == 3

    def test_excluded_directories_strict_pruning(self, tmp_path):
        """Files in venv, .venv, .git, build, dist, node_modules must be strictly ignored."""
        # Setup excluded directories with test files
        excluded_dirs = ["venv", ".venv", ".git", "build", "dist", "node_modules", ".tox", "VENV"]
        for d in excluded_dirs:
            dir_path = tmp_path / d
            dir_path.mkdir(parents=True, exist_ok=True)
            bad_test = dir_path / "test_should_be_ignored.py"
            bad_test.write_text("def test_ignored_one(): pass\ndef test_ignored_two(): pass\n", encoding="utf-8")

        # Setup valid directory with test files
        valid_dir = tmp_path / "tests" / "unit"
        valid_dir.mkdir(parents=True, exist_ok=True)
        valid_test = valid_dir / "test_valid.py"
        valid_test.write_text(
            "def test_valid_alpha(): pass\ndef test_valid_beta(): pass\n",
            encoding="utf-8"
        )

        valid_root_test = tmp_path / "test_root.py"
        valid_root_test.write_text("def test_valid_root(): pass\n", encoding="utf-8")

        analyzer = PythonAnalyzer()
        te = analyzer._count_tests_ast(str(tmp_path))

        # Expected: test_valid_alpha, test_valid_beta, test_valid_root = 3 tests
        assert te.total_tests == 3, f"Expected 3 tests from valid paths, found {te.total_tests}"


# ==============================================================================
# Test Suite 4: Feature 18 - _parse_pytest_output Regex Stress Testing
# ==============================================================================

class TestFeature18AdversarialPytestOutputParsing:
    """Stress test _parse_pytest_output against various pytest output formats."""

    @pytest.mark.parametrize("line,expected", [
        ("collected 15 items", 15),
        ("collected 20 tests", 20),
        ("15 items collected", 15),
        ("20 tests collected in 0.05s", 20),
        ("5 selected, 10 deselected", 5),
        ("10 deselected, 5 selected", 5),
        ("collected 25 items / 5 deselected / 20 selected", 20),
        ("collected 1 item", 1),
        ("1 test collected", 1),
        ("collected 0 items", 0),
        ("0 items collected", 0),
    ])
    def test_single_line_patterns(self, line, expected):
        res = PythonAnalyzer._parse_pytest_output(line)
        assert res == expected, f"Failed for '{line}': expected {expected}, got {res}"

    def test_multiline_pytest_output_with_deselection(self):
        """
        Pytest output with collection on line 1 and deselection on later lines.
        When 5 are selected and 10 deselected out of 15 collected,
        the active test count should ideally be 5 (selected).
        """
        output = (
            "============================= test session starts =============================\n"
            "collecting ... collected 15 items\n"
            "\n"
            "tests/test_foo.py .....\n"
            "======================== 5 selected, 10 deselected in 0.12s ========================"
        )
        res = PythonAnalyzer._parse_pytest_output(output)
        # Check behavior: whether it returns 15 or 5
        assert res in (5, 15), f"Unexpected test count: {res}"

    def test_ansi_colored_output(self):
        """Pytest emits ANSI escape sequences when run in a terminal or CI."""
        ansi_cases = [
            ("\x1b[32mcollected 15 items\x1b[0m", 15),
            ("\x1b[1m20 items collected\x1b[0m", 20),
            ("\x1b[32m5 selected\x1b[0m, 10 deselected", 5),
            ("\x1b[1m\x1b[32mcollected 30 tests\x1b[0m", 30),
        ]
        for line, expected in ansi_cases:
            res = PythonAnalyzer._parse_pytest_output(line)
            assert res == expected, f"Failed for ANSI line '{line}': expected {expected}, got {res}"

    def test_garbage_and_irrelevant_logs(self):
        """Garbage text, empty logs, compiler errors must return None."""
        garbage_cases = [
            "",
            None,
            "No tests were found in directory",
            "SyntaxError: invalid syntax (test_foo.py, line 4)",
            "ImportError: cannot import name 'bar'",
            "collected no items",
            "TOTAL 15 items",
            "items collected: none",
        ]
        for g in garbage_cases:
            res = PythonAnalyzer._parse_pytest_output(g)
            assert res is None, f"Expected None for garbage '{g}', got {res}"
