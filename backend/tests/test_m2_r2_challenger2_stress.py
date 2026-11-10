"""
Empirical Adversarial Stress Suite for Milestone 2 Round 2 Challenger 2.
Target: backend/intelligence/analyzers/python/analyzer.py

Focus:
1. Numeric vulnerability ID (0, -1, 1.5, True/False, large int)
2. Non-list vulns (False, None, {}, string, int, float)
3. Corrupted aliases (aliases=123, aliases=[None, 123, "CVE-2023-0001"], aliases=[None, 123], dict, bool)
4. Null descriptions, long descriptions (>200 chars), non-string descriptions, empty objects
5. Non-dict items in dependencies and vulns lists
6. Multi-format compatibility (pip-audit top-level dict, safety top-level dict, top-level list)
7. Analyzer pipeline crash resilience: _dependencies() execution with dirty payloads
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from intelligence.analyzers.python.analyzer import PythonAnalyzer


class TestNumericVulnerabilityIDs:
    """Stress tests for numeric, zero, negative, floating-point and boolean vulnerability IDs."""

    @pytest.mark.parametrize("vuln_id,expected_cve", [
        (0, "0"),
        (-1, "-1"),
        (1.5, "1.5"),
        (-0.0, "-0.0"),
        (999999999999999999999999, "999999999999999999999999"),
        (True, "True"),
        (False, "False"),
        ("", ""),
        ("   ", ""),
        ("GHSA-1234", "GHSA-1234"),
        ("CVE-2024-9999", "CVE-2024-9999"),
    ])
    def test_pip_audit_numeric_id_extraction(self, vuln_id, expected_cve):
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.25.0",
                    "vulns": [
                        {
                            "id": vuln_id,
                            "description": "Numeric ID test",
                            "severity": "medium",
                        }
                    ],
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["package"] == "requests"
        assert results[0]["version"] == "2.25.0"
        assert results[0]["cve"] == expected_cve

    @pytest.mark.parametrize("vuln_id,expected_cve", [
        (0, "0"),
        (-1, "-1"),
        (1.5, "1.5"),
        (None, ""),
        ([], ""),
        ({}, ""),
    ])
    def test_pip_audit_non_string_id_with_cve_alias_promotion(self, vuln_id, expected_cve):
        """When id is numeric or non-string, but aliases contains a valid CVE, CVE should be promoted."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "urllib3",
                    "version": "1.26.4",
                    "vulns": [
                        {
                            "id": vuln_id,
                            "aliases": [vuln_id, "CVE-2023-5678"],
                            "description": "Alias promotion test",
                        }
                    ],
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["cve"] == "CVE-2023-5678"

    @pytest.mark.parametrize("vuln_id,expected_cve", [
        (0, ""),  # 0 or ... evaluates to fallback empty string
        (-1, "-1"),
        (1.5, "1.5"),
        (None, ""),
    ])
    def test_safety_format_numeric_id(self, vuln_id, expected_cve):
        payload = json.dumps({
            "vulnerabilities": [
                {
                    "package_name": "django",
                    "vulnerability_id": vuln_id,
                    "advisory": "Safety numeric vuln id",
                    "installed_version": "3.1",
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["package"] == "django"
        assert results[0]["cve"] == expected_cve


class TestNonListVulnsAttribute:
    """Stress tests for dirty, corrupted, and non-list 'vulns' attributes in dependencies."""

    @pytest.mark.parametrize("dirty_vulns", [
        False,
        True,
        None,
        {},
        {"id": "CVE-2023-1111"},
        123,
        0,
        -1,
        3.14159,
        "not-a-list",
        "CVE-2023-9999",
    ])
    def test_top_level_dict_non_list_vulns(self, dirty_vulns):
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "cryptography",
                    "version": "3.4.7",
                    "vulns": dirty_vulns,
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert results == []

    @pytest.mark.parametrize("dirty_vulns", [
        False,
        True,
        None,
        {},
        {"id": "CVE-2023-1111"},
        123,
        "string-vuln",
    ])
    def test_top_level_list_non_list_vulns(self, dirty_vulns):
        payload = json.dumps([
            {
                "name": "flask",
                "version": "1.1.2",
                "vulns": dirty_vulns,
            }
        ])
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert results == []


class TestCorruptedAliases:
    """Stress tests for corrupted aliases types and content."""

    @pytest.mark.parametrize("corrupted_aliases,expected_cve", [
        (123, "GHSA-xxxx"),
        ("CVE-2023-8888", "CVE-2023-8888"),  # single string promoted if matches CVE-
        ("NOT-A-CVE", "GHSA-xxxx"),
        (True, "GHSA-xxxx"),
        (False, "GHSA-xxxx"),
        (None, "GHSA-xxxx"),
        ({}, "GHSA-xxxx"),
        ({"cve": "CVE-2023-1111"}, "GHSA-xxxx"),
    ])
    def test_scalar_or_non_list_aliases(self, corrupted_aliases, expected_cve):
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "certifi",
                    "version": "2020.12.5",
                    "vulns": [
                        {
                            "id": "GHSA-xxxx",
                            "aliases": corrupted_aliases,
                            "description": "Corrupted alias scalar test",
                        }
                    ],
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["cve"] == expected_cve

    @pytest.mark.parametrize("mixed_list,expected_cve", [
        ([None, 123, "CVE-2023-0001"], "CVE-2023-0001"),
        ([None, 123, 456], "GHSA-yyyy"),
        ([], "GHSA-yyyy"),
        ([{}, [], False, True], "GHSA-yyyy"),
        ([None, "", "   ", "NOT-CVE", 999], "GHSA-yyyy"),
        (["PYSEC-2023-1", "CVE-2023-9999", "CVE-2023-0000"], "CVE-2023-9999"),
    ])
    def test_mixed_dirty_items_in_aliases_list(self, mixed_list, expected_cve):
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "wheel",
                    "version": "0.36.2",
                    "vulns": [
                        {
                            "id": "GHSA-yyyy",
                            "aliases": mixed_list,
                            "description": "Mixed aliases list test",
                        }
                    ],
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["cve"] == expected_cve


class TestNullDescriptionsAndEmptyObjects:
    """Stress tests for null, missing, long, non-string descriptions and empty objects."""

    @pytest.mark.parametrize("desc_val,expected_desc_substr", [
        (None, "Vulnerability in my-pkg"),
        ("", "Vulnerability in my-pkg"),
        (12345, "12345"),
        (True, "True"),
        ({"key": "val"}, "{'key': 'val'}"),
        ([1, 2, 3], "[1, 2, 3]"),
        ("A" * 500, "A" * 200),  # Truncated to 200 chars
    ])
    def test_pip_audit_description_variants(self, desc_val, expected_desc_substr):
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "my-pkg",
                    "version": "1.0",
                    "vulns": [
                        {
                            "id": "CVE-2024-0001",
                            "description": desc_val,
                        }
                    ],
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert expected_desc_substr in results[0]["description"]
        assert len(results[0]["description"]) <= 200

    def test_completely_empty_objects(self):
        cases = [
            json.dumps({}),
            json.dumps([]),
            json.dumps({"dependencies": []}),
            json.dumps({"dependencies": [{}]}),
            json.dumps({"dependencies": [{"name": ""}]}),
            json.dumps({"dependencies": [{"name": "foo", "vulns": []}]}),
            json.dumps({"dependencies": [{"name": "foo", "vulns": [{}]}]}),
            json.dumps({"vulnerabilities": []}),
            json.dumps({"vulnerabilities": [{}]}),
            json.dumps([{}, {}, {}]),
        ]
        for payload in cases:
            results = PythonAnalyzer._parse_dep_vulns(payload)
            assert isinstance(results, list)

    def test_empty_vuln_dict_in_pip_audit(self):
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "pkg-a",
                    "version": "1.0.0",
                    "vulns": [{}],
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["package"] == "pkg-a"
        assert results[0]["cve"] == ""
        assert results[0]["description"] == "Vulnerability in pkg-a"
        assert results[0]["severity"] == "high"

    def test_non_dict_elements_in_lists(self):
        payload = json.dumps({
            "dependencies": [
                None,
                123,
                "some-string",
                [],
                {
                    "name": "valid-pkg",
                    "vulns": [
                        None,
                        123,
                        "not-a-dict",
                        [],
                        {"id": "CVE-2024-1234", "description": "OK"},
                    ],
                },
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["package"] == "valid-pkg"
        assert results[0]["cve"] == "CVE-2024-1234"


class TestAnalyzerDependenciesPipelineCrashResilience:
    """Verify that _dependencies() cleanly recovers from any dirty payloads and properly maintains evidence state."""

    def _sync_run(self, coro):
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

    @pytest.mark.parametrize("bad_json", [
        json.dumps({"dependencies": [{"name": "pkg", "vulns": 123}]}),
        json.dumps({"dependencies": [{"name": "pkg", "vulns": [{"id": 0}]}]}),
        json.dumps({"dependencies": [{"name": "pkg", "vulns": [{"id": -1, "aliases": [None, 123, "CVE-2023-0001"]}]}]}),
        json.dumps({"dependencies": [{"name": "pkg", "vulns": False}]}),
        json.dumps({"dependencies": [{"name": "pkg", "vulns": None}]}),
        json.dumps({"dependencies": [{"name": "pkg", "vulns": [{}]}]}),
        json.dumps({"vulnerabilities": [{"package_name": "pkg", "vulnerability_id": 0}]}),
        json.dumps([{"name": "pkg", "vulns": 123}]),
        json.dumps([{"name": "pkg", "vulns": [{"id": 1.5}]}]),
    ])
    def test_pipeline_zero_unhandled_exceptions_on_edge_schemas(self, bad_json):
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "pip-audit"), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = bad_json

            # Must NOT raise any unhandled exception
            vulns = self._sync_run(analyzer._dependencies(".", evidence))
            assert isinstance(vulns, list)
            # pip-audit succeeded in parsing and was recorded
            assert "pip-audit" in evidence.tools_executed
            assert "pip-audit-failed" not in evidence.tools_skipped

    def test_pipeline_recovers_if_parse_dep_vulns_throws_mock_exception(self):
        """If an unexpected exception is raised inside _parse_dep_vulns, _dependencies catches it, degrades quality, and does not record tool in tools_executed."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "pip-audit"), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run, \
             patch.object(analyzer, "_parse_dep_vulns", side_effect=RuntimeError("Simulated catastrophic crash")):
            mock_run.return_value = '{"dependencies": []}'

            vulns = self._sync_run(analyzer._dependencies(".", evidence))
            assert vulns == []
            assert "pip-audit" not in evidence.tools_executed
            assert "pip-audit-failed" in evidence.tools_skipped
            assert evidence.analysis_quality.confidence < 1.0
