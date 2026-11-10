"""
Empirical Adversarial Challenge Test Suite for Milestone 2 Round 2
Challenger 1: Subprocess Failures, Exception Recovery, and Fallback Degradation in _dependencies and analyze().
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import pytest

from intelligence.analyzers.python.analyzer import PythonAnalyzer, _run
from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum


import inspect

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


class CustomToolExecutionError(Exception):
    """Custom exception simulating arbitrary subprocess crash."""
    pass


class CustomParserError(Exception):
    """Custom exception simulating arbitrary parser error."""
    pass


# ==============================================================================
# SECTION 1: Output Parsing Catastrophic Exception Recovery
# ==============================================================================

class TestDependenciesOutputParsingResilience:
    """
    Stress-test _dependencies when output parsing encounters catastrophic exceptions:
    UnicodeDecodeError, MemoryError, custom exceptions, and malformed non-JSON data.
    """

    def test_output_parsing_memory_error_recovers_and_falls_back(self):
        """MemoryError during parsing must degrade quality, fall back to safety, and not crash."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([
            {"package": "fallback-pkg", "id": "CVE-2023-1111", "description": "Safe fallback"}
        ])

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ["{}", safety_output]
            with patch.object(analyzer, "_parse_dep_vulns", side_effect=[MemoryError("Simulated OOM during parsing"), [{"package": "fallback-pkg", "cve": "CVE-2023-1111"}]]):
                res = sync_run(analyzer._dependencies(".", evidence))

                assert res == [{"package": "fallback-pkg", "cve": "CVE-2023-1111"}]
                assert evidence.tools_executed == ["safety"]
                assert "pip-audit-failed" in evidence.tools_skipped
                assert round(evidence.analysis_quality.confidence, 2) == 0.95

    def test_output_parsing_unicode_decode_error_recovers_and_falls_back(self):
        """UnicodeDecodeError during parsing must degrade quality, fall back to safety, and not crash."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([
            {"package": "fallback-pkg", "id": "CVE-2023-2222", "description": "Safe fallback"}
        ])

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ["{}", safety_output]
            with patch.object(analyzer, "_parse_dep_vulns", side_effect=[UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), [{"package": "fallback-pkg", "cve": "CVE-2023-2222"}]]):
                res = sync_run(analyzer._dependencies(".", evidence))

                assert res == [{"package": "fallback-pkg", "cve": "CVE-2023-2222"}]
                assert evidence.tools_executed == ["safety"]
                assert "pip-audit-failed" in evidence.tools_skipped
                assert round(evidence.analysis_quality.confidence, 2) == 0.95

    def test_output_parsing_custom_exception_recovers_and_falls_back(self):
        """Custom exception during parsing must degrade quality, fall back to safety, and not crash."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([
            {"package": "fallback-pkg", "id": "CVE-2023-3333", "description": "Safe fallback"}
        ])

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ["{}", safety_output]
            with patch.object(analyzer, "_parse_dep_vulns", side_effect=[CustomParserError("Unexpected schema structure"), [{"package": "fallback-pkg", "cve": "CVE-2023-3333"}]]):
                res = sync_run(analyzer._dependencies(".", evidence))

                assert res == [{"package": "fallback-pkg", "cve": "CVE-2023-3333"}]
                assert evidence.tools_executed == ["safety"]
                assert "pip-audit-failed" in evidence.tools_skipped
                assert round(evidence.analysis_quality.confidence, 2) == 0.95


# ==============================================================================
# SECTION 2: Empty Output, Corrupt Non-JSON Streams, and CLI Stack Traces
# ==============================================================================

class TestCorruptedStreamsAndStackTraces:
    """Stress-test non-JSON output streams, stack traces, and empty CLI outputs."""

    def test_pip_audit_empty_string_output_falls_back_to_safety(self):
        """When pip-audit outputs empty string, it must degrade quality and fall back to safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([{"package": "sec-pkg", "id": "CVE-2023-4444"}])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ["", safety_output]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-4444"
            assert evidence.tools_executed == ["safety"]
            assert "pip-audit-failed" in evidence.tools_skipped
            assert round(evidence.analysis_quality.confidence, 2) == 0.95

    def test_pip_audit_whitespace_only_output_falls_back_to_safety(self):
        """When pip-audit outputs whitespace only, it must degrade quality and fall back to safety."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([{"package": "sec-pkg", "id": "CVE-2023-4445"}])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ["   \n\t  \r\n", safety_output]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-4445"
            assert evidence.tools_executed == ["safety"]
            assert "pip-audit-failed" in evidence.tools_skipped

    def test_pip_audit_cli_python_traceback_stream(self):
        """When pip-audit outputs a standard Python exception traceback."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        traceback_output = (
            "Traceback (most recent call last):\n"
            '  File "/usr/local/bin/pip-audit", line 8, in <module>\n'
            "    sys.exit(cli())\n"
            '  File "/pip_audit/_cli.py", line 120, in cli\n'
            "    raise ConnectionResetError('Remote disconnected')\n"
            "ConnectionResetError: Remote disconnected\n"
        )
        safety_output = json.dumps([{"package": "foo", "id": "CVE-2023-5555"}])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [traceback_output, safety_output]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-5555"
            assert evidence.tools_executed == ["safety"]
            assert "pip-audit-failed" in evidence.tools_skipped

    def test_pip_audit_corrupted_partial_json_stream(self):
        """When pip-audit outputs truncated/malformed JSON stream."""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        truncated_json = '{"dependencies": [{"name": "urllib3", "vulns": [{"id": "CVE-2023-0001"'
        safety_output = json.dumps([{"package": "foo", "id": "CVE-2023-6666"}])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [truncated_json, safety_output]
            res = sync_run(analyzer._dependencies(".", evidence))

            assert len(res) == 1
            assert res[0]["cve"] == "CVE-2023-6666"
            assert evidence.tools_executed == ["safety"]
            assert "pip-audit-failed" in evidence.tools_skipped


# ==============================================================================
# SECTION 3: Subprocess Tool Execution Exceptions (Tool-Level Failures)
# ==============================================================================

class TestToolExecutionCatastrophicExceptions:
    """
    Stress-test behavior when the subprocess execution itself (_run) raises
    catastrophic exceptions (UnicodeDecodeError, MemoryError, Custom Exceptions).
    """

    def test_run_memory_error_during_pip_audit(self):
        """When _run raises MemoryError on pip-audit, does it degrade and fall back to safety or crash?"""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([{"package": "bar", "id": "CVE-2023-7777"}])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [MemoryError("Out of memory during pip-audit execution"), safety_output]
            try:
                res = sync_run(analyzer._dependencies(".", evidence))
                assert len(res) == 1
                assert res[0]["cve"] == "CVE-2023-7777"
                assert evidence.tools_executed == ["safety"]
                assert "pip-audit-failed" in evidence.tools_skipped
            except MemoryError as e:
                pytest.fail(f"_dependencies crashed with unhandled MemoryError during _run: {e}")

    def test_run_unicode_decode_error_during_pip_audit(self):
        """When _run raises UnicodeDecodeError on pip-audit, does it degrade and fall back to safety or crash?"""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([{"package": "bar", "id": "CVE-2023-8888"}])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), safety_output]
            try:
                res = sync_run(analyzer._dependencies(".", evidence))
                assert len(res) == 1
                assert res[0]["cve"] == "CVE-2023-8888"
                assert evidence.tools_executed == ["safety"]
                assert "pip-audit-failed" in evidence.tools_skipped
            except UnicodeDecodeError as e:
                pytest.fail(f"_dependencies crashed with unhandled UnicodeDecodeError during _run: {e}")

    def test_run_custom_exception_during_pip_audit(self):
        """When _run raises CustomToolExecutionError on pip-audit, does it degrade and fall back or crash?"""
        analyzer = PythonAnalyzer()
        evidence = analyzer._empty_evidence(".", {})
        safety_output = json.dumps([{"package": "bar", "id": "CVE-2023-9999"}])

        with patch.object(analyzer, "_tool_available", return_value=True), \
             patch("intelligence.analyzers.python.analyzer._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [CustomToolExecutionError("Subprocess failed abnormally"), safety_output]
            try:
                res = sync_run(analyzer._dependencies(".", evidence))
                assert len(res) == 1
                assert res[0]["cve"] == "CVE-2023-9999"
                assert evidence.tools_executed == ["safety"]
                assert "pip-audit-failed" in evidence.tools_skipped
            except CustomToolExecutionError as e:
                pytest.fail(f"_dependencies crashed with unhandled CustomToolExecutionError during _run: {e}")

    def test_analyze_method_never_crashes_on_dependencies_failure(self):
        """Verify PythonAnalyzer.analyze() end-to-end never crashes when _run raises catastrophic exception in _dependencies."""
        analyzer = PythonAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            f.write_text("import os\n", encoding="utf-8")

            # Mock _run so that pip-audit tool run throws MemoryError
            async def selective_run(cmd, cwd=None):
                if "pip-audit" in cmd[0]:
                    raise MemoryError("OOM inside tool runner")
                if "safety" in cmd[0]:
                    return json.dumps([{"package": "pkg1", "id": "CVE-2024-0001"}])
                return None

            with patch.object(analyzer, "_tool_available", return_value=True), \
                 patch("intelligence.analyzers.python.analyzer._run", side_effect=selective_run):
                try:
                    ev = sync_run(analyzer.analyze(["app.py"], tmp_dir))
                    assert ev.files_analyzed == 1
                    assert len(ev.security.dependency_vulnerabilities) == 1
                    assert ev.security.dependency_vulnerabilities[0]["cve"] == "CVE-2024-0001"
                    assert "safety" in ev.tools_executed
                    assert "pip-audit-failed" in ev.tools_skipped
                except Exception as e:
                    pytest.fail(f"analyze() crashed with unhandled exception: {type(e).__name__}: {e}")
