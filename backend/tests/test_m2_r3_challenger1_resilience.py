"""
Empirical Adversarial Test Suite - Challenger 1 (Milestone 2 Round 3)
Target: backend/intelligence/analyzers/python/analyzer.py

Empirical stress testing of PythonAnalyzer.analyze() pipeline resilience:
- Inject simulated catastrophic failures (MemoryError, UnicodeDecodeError, RuntimeError)
  during _lint, _security, analyze_complexity, _architecture, _testing,
  scan_secrets, and analyze_duplication.
- Verify whether analyze() NEVER crashes, degrades quality accurately,
  isolates failures per pass without aborting subsequent passes,
  and returns a valid CodeQualityEvidence object with duration_ms populated.
"""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
import pytest

import intelligence.analyzers.python.analyzer as analyzer_module
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


@pytest.fixture
def sample_repo():
    with TemporaryDirectory() as tmp_dir:
        p = Path(tmp_dir) / "app.py"
        p.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
        t = Path(tmp_dir) / "test_app.py"
        t.write_text("def test_hello():\n    assert True\n", encoding="utf-8")
        yield tmp_dir


@pytest.fixture
def mock_subprocesses():
    """Mock external tool subprocesses so tests execute deterministically and fast."""
    async def fake_run(cmd, cwd=None):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "ruff" in cmd_str:
            return "[]"
        if "bandit" in cmd_str:
            return json.dumps({"results": []})
        if "pip-audit" in cmd_str:
            return json.dumps({"dependencies": []})
        if "safety" in cmd_str:
            return json.dumps([])
        if "coverage" in cmd_str:
            return json.dumps({"totals": {"percent_covered": 85.0}})
        return None

    with patch("intelligence.analyzers.python.analyzer._run", side_effect=fake_run) as m_run:
        yield m_run


# ==============================================================================
# SECTION 1: Module Import Integrity & Missing Fallback Types
# ==============================================================================

class TestModuleImportIntegrity:
    """Verifies that all classes instantiated in exception fallback handlers exist in module scope."""

    def test_complexity_evidence_imported_in_analyzer_module(self):
        """ComplexityEvidence must be imported in analyzer.py for Pass 4 fallback handling."""
        assert hasattr(analyzer_module, "ComplexityEvidence"), (
            "ComplexityEvidence is referenced at line 121 of analyzer.py but never imported, "
            "causing NameError when analyze_complexity fails."
        )

    def test_duplication_evidence_imported_in_analyzer_module(self):
        """DuplicationEvidence must be imported in analyzer.py for Pass 8 fallback handling."""
        assert hasattr(analyzer_module, "DuplicationEvidence"), (
            "DuplicationEvidence is referenced at line 163 of analyzer.py but never imported, "
            "causing NameError when analyze_duplication fails."
        )


# ==============================================================================
# SECTION 2: Pass Isolation & Catastrophic Failure Recovery
# ==============================================================================

class TestSubAnalyzerCatastrophicFailures:
    """Adversarial stress-testing of PythonAnalyzer.analyze() pipeline stages."""

    @pytest.mark.parametrize("exc", [
        MemoryError("Out of memory in _lint"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        RuntimeError("Flake8/Ruff process terminated"),
    ])
    def test_lint_catastrophic_failure_handled_cleanly(self, sample_repo, mock_subprocesses, exc):
        """When _lint raises catastrophic exceptions, analyze() must not crash,

        must degrade static_analysis quality, and continue downstream passes.
        """
        analyzer = PythonAnalyzer()
        with patch.object(analyzer, "_lint", side_effect=exc):
            ev = sync_run(analyzer.analyze(["app.py"], sample_repo))

            assert isinstance(ev, CodeQualityEvidence)
            assert ev.analysis_duration_ms > 0
            assert "lint-pipeline-failed" in ev.tools_skipped
            assert ev.architecture is not None
            assert ev.testing is not None
            assert ev.files_analyzed == 1

    @pytest.mark.parametrize("exc", [
        MemoryError("Out of memory in _security"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        RuntimeError("Bandit aborted with signal 9"),
    ])
    def test_security_catastrophic_failure_handled_cleanly(self, sample_repo, mock_subprocesses, exc):
        """When _security raises catastrophic exceptions, analyze() must not crash,

        must degrade security quality, and assemble valid security evidence.
        """
        analyzer = PythonAnalyzer()
        with patch.object(analyzer, "_security", side_effect=exc):
            ev = sync_run(analyzer.analyze(["app.py"], sample_repo))

            assert isinstance(ev, CodeQualityEvidence)
            assert ev.analysis_duration_ms > 0
            assert "security-pipeline-failed" in ev.tools_skipped
            assert ev.security is not None
            assert ev.files_analyzed == 1

    @pytest.mark.parametrize("exc", [
        MemoryError("OOM during radon/lizard AST parsing"),
        UnicodeDecodeError("utf-8", b"\x80", 0, 1, "bad encoding"),
        RuntimeError("Lizard crash"),
    ])
    def test_complexity_catastrophic_failure_handled_cleanly(self, sample_repo, mock_subprocesses, exc):
        """When analyze_complexity raises catastrophic exceptions, analyze() must not crash,

        must degrade complexity quality, and not abort downstream stages due to unhandled NameError.
        """
        analyzer = PythonAnalyzer()
        with patch("intelligence.analyzers.python.analyzer.analyze_complexity", side_effect=exc):
            ev = sync_run(analyzer.analyze(["app.py"], sample_repo))

            assert isinstance(ev, CodeQualityEvidence)
            assert ev.analysis_duration_ms > 0
            assert "complexity-pipeline-failed" in ev.tools_skipped
            # Downstream passes must NOT be aborted by unhandled NameError or crash
            assert ev.security is not None, "Security pass should have executed and assembled"
            assert ev.testing is not None, "Testing pass should have executed"
            assert ev.architecture is not None, "Architecture pass should have executed"
            assert "analyzer-internal-error" not in ev.tools_skipped, (
                "analyze_complexity exception handler should not raise NameError triggering analyzer-internal-error"
            )

    @pytest.mark.parametrize("exc", [
        MemoryError("OOM in ast testing traversal"),
        UnicodeDecodeError("utf-8", b"\xfe", 0, 1, "bad byte"),
        RuntimeError("Pytest collection crash"),
    ])
    def test_testing_catastrophic_failure_handled_cleanly(self, sample_repo, mock_subprocesses, exc):
        """When _testing raises catastrophic exceptions, analyze() must not crash,

        must degrade testing quality, and return fallback TestingEvidence.
        """
        analyzer = PythonAnalyzer()
        with patch.object(analyzer, "_testing", side_effect=exc):
            ev = sync_run(analyzer.analyze(["app.py"], sample_repo))

            assert isinstance(ev, CodeQualityEvidence)
            assert ev.analysis_duration_ms > 0
            assert "testing-pipeline-failed" in ev.tools_skipped
            assert ev.testing is not None
            assert ev.testing.test_framework == "pytest"

    @pytest.mark.parametrize("exc", [
        MemoryError("OOM during architecture import parsing"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte"),
        RuntimeError("Architecture check error"),
    ])
    def test_architecture_catastrophic_failure_handled_cleanly(self, sample_repo, mock_subprocesses, exc):
        """When _architecture raises catastrophic exceptions, analyze() must not crash,

        must degrade architecture quality, and return ArchitectureEvidence.
        """
        analyzer = PythonAnalyzer()
        with patch.object(analyzer, "_architecture", side_effect=exc):
            ev = sync_run(analyzer.analyze(["app.py"], sample_repo))

            assert isinstance(ev, CodeQualityEvidence)
            assert ev.analysis_duration_ms > 0
            assert "architecture-pipeline-failed" in ev.tools_skipped
            assert ev.architecture is not None

    @pytest.mark.parametrize("exc", [
        MemoryError("OOM during duplication analysis"),
        RuntimeError("Duplication analyzer failed"),
    ])
    def test_duplication_catastrophic_failure_handled_cleanly(self, sample_repo, mock_subprocesses, exc):
        """When analyze_duplication raises catastrophic exceptions, analyze() must not crash,

        must degrade maintainability quality, and not abort downstream stages due to unhandled NameError.
        """
        analyzer = PythonAnalyzer()
        with patch("intelligence.analyzers.python.analyzer.analyze_duplication", side_effect=exc):
            ev = sync_run(analyzer.analyze(["app.py"], sample_repo))

            assert isinstance(ev, CodeQualityEvidence)
            assert ev.analysis_duration_ms > 0
            assert "duplication-pipeline-failed" in ev.tools_skipped
            # Downstream passes must NOT be aborted by unhandled NameError or crash
            assert ev.testing is not None, "Testing pass should have executed"
            assert ev.architecture is not None, "Architecture pass should have executed"
            assert "analyzer-internal-error" not in ev.tools_skipped, (
                "analyze_duplication exception handler should not raise NameError triggering analyzer-internal-error"
            )


# ==============================================================================
# SECTION 3: Duration Precision and Multi-Stage Stress Test
# ==============================================================================

class TestDurationAndMultiStageFailure:
    """Stress tests high-speed multi-stage failures and duration measurement."""

    def test_analysis_duration_ms_strictly_positive_even_under_microsecond_executions(self, sample_repo, mock_subprocesses):
        """Duration should be reliably positive (using high precision timer like time.perf_counter),

        even if passes exit immediately.
        """
        analyzer = PythonAnalyzer()
        with patch.object(analyzer, "_lint", side_effect=RuntimeError("fast fail")), \
             patch.object(analyzer, "_security", side_effect=RuntimeError("fast fail")), \
             patch.object(analyzer, "_dependencies", side_effect=RuntimeError("fast fail")), \
             patch("intelligence.analyzers.python.analyzer.analyze_complexity", side_effect=RuntimeError("fast fail")), \
             patch("intelligence.analyzers.python.analyzer.scan_secrets", side_effect=RuntimeError("fast fail")), \
             patch("intelligence.analyzers.python.analyzer.analyze_duplication", side_effect=RuntimeError("fast fail")), \
             patch.object(analyzer, "_testing", side_effect=RuntimeError("fast fail")), \
             patch.object(analyzer, "_architecture", side_effect=RuntimeError("fast fail")):

            ev = sync_run(analyzer.analyze(["app.py"], sample_repo))
            assert isinstance(ev, CodeQualityEvidence)
            # Check duration is recorded and positive
            assert ev.analysis_duration_ms > 0, (
                f"Expected analysis_duration_ms > 0, got {ev.analysis_duration_ms}. "
                "time.monotonic() has coarse 15.6ms quantum on Windows and can return 0.0."
            )
