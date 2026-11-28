"""v4 DEF-V4-029 / DEF-V4-030: noisy Python findings from the live pallets/click run.

65 of 69 findings were Bandit B101 (plain assert) in pytest files, and mypy
unresolved-import diagnostics were listed as HIGH although scoring already treats
them as context. B101 in test files is now dropped (Bandit's own recommended skip
for tests). B101 elsewhere is kept, and import diagnostics are INFO.
"""

import json

import pytest

from intelligence.analyzers.python import analyzer as python_analyzer
from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum


def _issue(path, test_id="B101", severity="LOW"):
    return {"filename": path, "line_number": 3, "test_id": test_id, "issue_severity": severity,
            "issue_text": "Use of assert detected.", "code": "assert x"}


@pytest.mark.anyio
async def test_b101_is_dropped_in_test_files_but_kept_in_source(tmp_path, monkeypatch):
    report = {"results": [
        _issue(str(tmp_path / "tests" / "test_core.py")),
        _issue(str(tmp_path / "src" / "conftest_helpers_test.py")),
        _issue(str(tmp_path / "src" / "core.py")),                       # production assert: kept
        _issue(str(tmp_path / "tests" / "test_core.py"), "B602", "HIGH"),  # other rules in tests: kept
    ], "errors": []}

    async def fake_run(cmd, cwd=None, require_success=False):
        return json.dumps(report)

    monkeypatch.setattr(python_analyzer, "_run", fake_run)
    analyzer = PythonAnalyzer()
    monkeypatch.setattr(analyzer, "_tool_available", lambda binary: True)
    evidence = CodeQualityEvidence(repository_id="R", primary_language="python")
    findings = await analyzer._security([], str(tmp_path), evidence)
    kept = sorted((f.rule_id, f.file_path.replace(str(tmp_path), "")) for f in findings)
    assert kept == [("BANDIT-B101", "/src/core.py"), ("BANDIT-B602", "/tests/test_core.py")]
    assert "bandit" in evidence.tools_executed


def test_mypy_import_diagnostics_are_info_and_real_type_errors_stay_high():
    output = "\n".join(json.dumps(item) for item in [
        {"file": "a.py", "line": 1, "severity": "error", "code": "import-not-found", "message": "Cannot find module"},
        {"file": "a.py", "line": 2, "severity": "error", "code": "import-untyped", "message": "Missing stubs"},
        {"file": "a.py", "line": 3, "severity": "error", "code": "arg-type", "message": "Bad argument"},
    ])
    severities = {f.rule_id: f.severity for f in PythonAnalyzer._parse_mypy(output, ["a.py"])}
    assert severities == {"MYPY-import-not-found": SeverityEnum.INFO, "MYPY-import-untyped": SeverityEnum.INFO,
                          "MYPY-arg-type": SeverityEnum.HIGH}
