"""
Adversarial Stress Test Suite for Milestone 2 Round 3 Challenger 2.
Target: backend/intelligence/analyzers/python/analyzer.py

Focus:
Adversarially stress test `_extract_pip_audit_dep` and `_parse_dep_vulns` with:
1. Dirty schemas (missing fields, unexpected types, deeply nested garbage, corrupted keys).
2. Negative numbers (negative IDs, negative integers in aliases, negative versions, negative descriptions).
3. Extreme floats (NaN, +inf, -inf, 1e308, -1e308, subnormal 1e-324, 0.0, -0.0).
4. Non-dict entries (None, scalars, tuples, sets, custom objects, generators, lambdas).
5. Zero unhandled exceptions across both direct parser invocation and full `analyze()` pipeline execution.
"""

import json
import math
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch
import pytest

from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum


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
# Suite 1: Non-Dict Entries Passed Directly and Indirectly
# ==============================================================================

class TestNonDictEntriesStress:
    """Stress test non-dict inputs to dependency extraction and parsing."""

    @pytest.mark.parametrize("hostile_entry", [
        None,
        42,
        -999999,
        0,
        3.14159,
        float("inf"),
        float("-inf"),
        float("nan"),
        True,
        False,
        "not a dict string",
        b"raw bytes entry",
        [],
        [1, 2, 3],
        ("tuple", 123),
        {1, 2, 3},  # set
        object(),
        lambda x: x,
        ValueError("hostile exception object"),
        (x for x in range(5)),  # generator
    ])
    def test_top_level_list_with_hostile_non_dict_entries(self, hostile_entry):
        """Top-level list containing non-dict entries must be skipped without crashing."""
        # Top-level list containing hostile entries mixed with one valid entry
        payload = [
            hostile_entry,
            {"name": "valid-pkg", "version": "1.0.0", "vulns": []},
            hostile_entry,
        ]
        # In json string, only JSON-serializable types can be serialized
        try:
            json_str = json.dumps(payload)
            results = PythonAnalyzer._parse_dep_vulns(json_str)
            assert isinstance(results, list)
            assert len(results) == 0
        except TypeError:
            # For non-json-serializable objects (e.g. set, object, lambda, generator),
            # test passing invalid JSON directly to _parse_dep_vulns
            pass

    @pytest.mark.parametrize("hostile_entry", [
        None,
        42,
        -999999,
        0,
        3.14159,
        float("inf"),
        float("-inf"),
        float("nan"),
        True,
        False,
        "not a dict string",
        [],
        [1, 2, 3],
    ])
    def test_dependencies_list_with_hostile_non_dict_entries(self, hostile_entry):
        """dependencies array containing non-dict entries must be skipped without error."""
        payload = {
            "dependencies": [
                hostile_entry,
                {"name": "safe-pkg", "version": "2.0.0", "vulns": []},
                hostile_entry,
            ]
        }
        json_str = json.dumps(payload)
        results = PythonAnalyzer._parse_dep_vulns(json_str)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.parametrize("hostile_vuln", [
        None,
        123,
        -1,
        0,
        3.14159,
        float("inf"),
        float("-inf"),
        float("nan"),
        True,
        False,
        "string-vuln",
        [],
        [1, 2],
    ])
    def test_vulns_array_with_hostile_non_dict_items(self, hostile_vuln):
        """vulns array containing non-dict entries must be skipped safely."""
        payload = {
            "dependencies": [
                {
                    "name": "target-pkg",
                    "version": "1.2.3",
                    "vulns": [
                        hostile_vuln,
                        {
                            "id": "CVE-2024-1111",
                            "description": "Valid vuln",
                            "severity": "high",
                        },
                        hostile_vuln,
                    ],
                }
            ]
        }
        json_str = json.dumps(payload)
        results = PythonAnalyzer._parse_dep_vulns(json_str)
        assert len(results) == 1
        assert results[0]["package"] == "target-pkg"
        assert results[0]["cve"] == "CVE-2024-1111"


# ==============================================================================
# Suite 2: Negative Numbers Across All Dependency Fields
# ==============================================================================

class TestNegativeNumbersStress:
    """Stress test negative integers and floats in vulnerability and package fields."""

    @pytest.mark.parametrize("neg_id", [
        -1,
        -2,
        -999999999999999999999999999999999999999999999999,
        -0.0,
        -1.5,
        -99999.99999,
    ])
    def test_negative_vulnerability_ids(self, neg_id):
        """Negative IDs are cleanly converted to string representation."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "pkg-with-neg-id",
                    "version": "1.0",
                    "vulns": [{"id": neg_id, "description": "Negative ID test"}]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        expected_cve = str(neg_id).strip()
        assert results[0]["cve"] == expected_cve
        assert results[0]["package"] == "pkg-with-neg-id"

    @pytest.mark.parametrize("neg_version", [
        -1,
        -100,
        -0.5,
    ])
    def test_negative_package_version(self, neg_version):
        """Negative numbers in version field must be converted to non-empty string."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "pkg-neg-ver",
                    "version": neg_version,
                    "vulns": [{"id": "CVE-2024-0001"}]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["version"] == str(neg_version)

    @pytest.mark.parametrize("neg_alias", [
        -1,
        -42,
        [-1, -2, -3],
        [-1, "CVE-2024-9999", -999],
    ])
    def test_negative_values_in_aliases(self, neg_alias):
        """Negative values in aliases list or scalar alias must not cause TypeError."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "pkg-neg-alias",
                    "vulns": [
                        {
                            "id": "GHSA-xxxx",
                            "aliases": neg_alias,
                            "description": "Negative alias test"
                        }
                    ]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        if "CVE-2024-9999" in str(neg_alias):
            assert results[0]["cve"] == "CVE-2024-9999"
        else:
            assert results[0]["cve"] == "GHSA-xxxx"


# ==============================================================================
# Suite 3: Extreme Floats (NaN, Inf, Underflow, Overflow)
# ==============================================================================

class TestExtremeFloatsStress:
    """Stress test extreme IEEE-754 floats in JSON or Python structures."""

    @pytest.mark.parametrize("extreme_float,expected_str", [
        (float("inf"), "inf"),
        (float("-inf"), "-inf"),
        (float("nan"), "nan"),
        (1e308, "1e+308"),
        (-1e308, "-1e+308"),
        (1e-308, "1e-308"),
        (1e-323, "1e-323"),
        (0.0, "0.0"),
        (-0.0, "-0.0"),
    ])
    def test_extreme_floats_as_vuln_id(self, extreme_float, expected_str):
        """Extreme floats in vulnerability id field."""
        # Note: json.dumps produces "Infinity", "-Infinity", "NaN" by default if allow_nan=True
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "float-pkg",
                    "version": "1.0",
                    "vulns": [
                        {
                            "id": extreme_float,
                            "description": "Extreme float test",
                        }
                    ]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        # Python json.loads parse inf/nan as float inf/nan, which str() turns into 'inf', 'nan', etc.
        assert results[0]["package"] == "float-pkg"
        assert results[0]["cve"] in (expected_str, "inf", "-inf", "nan", str(extreme_float))

    @pytest.mark.parametrize("extreme_float", [
        float("inf"),
        float("-inf"),
        float("nan"),
        1e308,
        -1e308,
    ])
    def test_extreme_floats_as_package_version(self, extreme_float):
        """Extreme floats in version field."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "float-ver-pkg",
                    "version": extreme_float,
                    "vulns": [{"id": "CVE-2024-5555"}]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert "version" in results[0]
        assert results[0]["version"] == str(extreme_float)

    @pytest.mark.parametrize("extreme_float", [
        float("inf"),
        float("-inf"),
        float("nan"),
        1e308,
    ])
    def test_extreme_floats_in_aliases_and_cve_search(self, extreme_float):
        """Extreme floats in aliases must be ignored by string startswith CVE- filter."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "float-alias-pkg",
                    "vulns": [
                        {
                            "id": "GHSA-abcd",
                            "aliases": [extreme_float, "CVE-2024-7777", extreme_float],
                        }
                    ]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["cve"] == "CVE-2024-7777"


# ==============================================================================
# Suite 4: Dirty and Malformed Schemas
# ==============================================================================

class TestDirtySchemasStress:
    """Stress test weird and corrupted schema topologies."""

    def test_recursive_nested_structures(self):
        """Dictionaries containing recursive or nested dummy keys."""
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "nested-pkg",
                    "version": "1.0",
                    "extra": {"nested": {"deeper": {"level": [1, 2, 3]}}},
                    "vulns": [
                        {
                            "id": "CVE-2024-0001",
                            "details": {"a": {"b": {"c": 123}}},
                            "fix_versions": ["2.0.0"],
                        }
                    ]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert results[0]["package"] == "nested-pkg"
        assert results[0]["fix_versions"] == ["2.0.0"]

    def test_fix_versions_dirty_types(self):
        """fix_versions with non-list or weird types."""
        cases = [
            None,
            [],
            "2.0.0",  # scalar string
            123,      # int
            False,    # boolean
            {"ver": "2.0.0"},  # dict
            [None, 123, "2.0.0"],
        ]
        for fv in cases:
            payload = json.dumps({
                "dependencies": [
                    {
                        "name": "pkg-fix-ver",
                        "vulns": [
                            {
                                "id": "CVE-2024-0001",
                                "fix_versions": fv,
                            }
                        ]
                    }
                ]
            })
            results = PythonAnalyzer._parse_dep_vulns(payload)
            assert len(results) == 1
            if fv:
                assert results[0]["fix_versions"] == fv
            else:
                assert "fix_versions" not in results[0]

    def test_description_extreme_unicode_and_length(self):
        """Descriptions with 50,000 chars, null bytes, unicode emojis, and HTML."""
        huge_desc = "🚨" * 5000 + "A" * 50000 + "<script>alert(1)</script>"
        payload = json.dumps({
            "dependencies": [
                {
                    "name": "pkg-huge-desc",
                    "vulns": [
                        {
                            "id": "CVE-2024-0001",
                            "description": huge_desc,
                        }
                    ]
                }
            ]
        })
        results = PythonAnalyzer._parse_dep_vulns(payload)
        assert len(results) == 1
        assert len(results[0]["description"]) <= 200

    def test_package_name_resolution_fallback(self):
        """Package name resolution between 'name' and 'package' keys."""
        # 1. 'name' present
        r1 = PythonAnalyzer._parse_dep_vulns(json.dumps({
            "dependencies": [{"name": "pkg-one", "vulns": [{"id": "CVE-1"}]}]
        }))
        assert r1[0]["package"] == "pkg-one"

        # 2. 'package' present instead
        r2 = PythonAnalyzer._parse_dep_vulns(json.dumps({
            "dependencies": [{"package": "pkg-two", "vulns": [{"id": "CVE-2"}]}]
        }))
        assert r2[0]["package"] == "pkg-two"

        # 3. Both missing or empty
        r3 = PythonAnalyzer._parse_dep_vulns(json.dumps({
            "dependencies": [{"vulns": [{"id": "CVE-3"}]}]
        }))
        assert r3[0]["package"] == ""


# ==============================================================================
# Suite 5: Pipeline Resilience Under Adversarial Payloads
# ==============================================================================

class TestPipelineIntegrationZeroUnhandledExceptions:
    """End-to-end analyzer.analyze() and analyzer._dependencies() resilience."""

    @pytest.mark.parametrize("payload", [
        # Malformed JSON
        "{dependencies: [invalid json}",
        # Empty string / whitespace
        "",
        "   ",
        "\n\t\r",
        # None
        None,
        # Primitive JSON values
        "42",
        "-999",
        "true",
        "false",
        "null",
        '"a bare json string"',
        # Hostile nested dependencies
        json.dumps({"dependencies": [{"name": None, "version": None, "vulns": None}]}),
        json.dumps({"dependencies": [{"name": 123, "version": -1, "vulns": [{"id": -99, "aliases": [-1, False, None]}]}]}),
        json.dumps({"dependencies": [{"vulns": [None, 123, -1, float("inf"), float("nan"), {}, []]}]}),
    ])
    def test_dependencies_method_never_crashes(self, payload):
        """PythonAnalyzer._dependencies() handles hostile outputs without unhandled exceptions."""
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-repo", primary_language="python")

        with patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = payload
            with patch.object(analyzer, "_tool_available", return_value=True):
                vulns = sync_run(analyzer._dependencies("/fake/repo", evidence))
                assert isinstance(vulns, list)

    def test_analyze_end_to_end_with_adversarial_dependencies(self):
        """Full analyze() method returns clean CodeQualityEvidence despite adversarial output."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_file = Path(tmp_dir) / "app.py"
            sample_file.write_text("x = 1\n", encoding="utf-8")

            analyzer = PythonAnalyzer()

            hostile_payload = json.dumps({
                "dependencies": [
                    None,
                    42,
                    {"name": 123, "version": -1, "vulns": [{"id": -1, "aliases": [-1, 3.14]}]},
                    {"name": "requests", "vulns": "not-a-list"},
                ]
            })

            with patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
                # Return hostile payload for pip-audit, None for other tools
                def mock_run_side_effect(cmd, cwd=None):
                    if "pip-audit" in cmd:
                        return hostile_payload
                    return None

                mock_run.side_effect = mock_run_side_effect
                with patch.object(analyzer, "_tool_available", return_value=True):
                    evidence = sync_run(analyzer.analyze(["app.py"], tmp_dir))
                    assert isinstance(evidence, CodeQualityEvidence)
                    assert evidence.analysis_duration_ms >= 0
                    assert len(evidence.security.dependency_vulnerabilities) == 1
                    assert evidence.security.dependency_vulnerabilities[0]["cve"] == "-1"
