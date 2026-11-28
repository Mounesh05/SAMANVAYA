"""v4 AI-PR: a PR comparison parent gets one advisory AI interpretation.

Live run LIVE-04 found that PR comparisons never received an AI interpretation.
The parent now gets exactly one, built from the measured head revision and the
server-side comparison evidence. The child runs carry none, and use_ai=False skips it.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agents.code_agent import _build_evidence_text
from domain.services import internal_agent_adapter, pr_quality_comparison
from intelligence.evidence.models import CodeQualityEvidence
from tests.test_code_quality_repository_routes import (  # noqa: F401 - fixture import
    BASE, BASE_REVISION, HEAD_REVISION, repository_client,
)


def _arrange(github, monkeypatch):
    github.client.get_pull_request = AsyncMock(return_value={
        "number": 17, "base": {"sha": BASE_REVISION}, "head": {"sha": HEAD_REVISION},
    })
    github.client.get_pr_files = AsyncMock(return_value=[{"filename": "src/app.py", "status": "modified"}])
    github.fetch_analysis_sources = AsyncMock(return_value=({"src/app.py": "def ok():\n    return 1\n"}, []))

    async def fake_analyze(self, paths, context, **kwargs):
        return CodeQualityEvidence(repository_id="P", commit_sha=context["commit_sha"], primary_language="python",
                                   files_analyzed=1, tools_executed=["ruff"])

    async def fake_measure(evidence, paths):
        score = 72 if evidence.commit_sha == BASE_REVISION else 86
        return {"status": "completed", "quality_analysis_status": "available", "quality_score": score,
                "quality_grade": "B", "risk_score": 15, "risk_level": "low", "language": "python",
                "tools_executed": ["ruff"], "tools_skipped": [],
                "function_discovery": evidence.function_discovery.model_dump(mode="json")}

    monkeypatch.setattr(pr_quality_comparison.CodeQualityService, "analyze_pr", fake_analyze)
    monkeypatch.setattr(pr_quality_comparison, "measure_quality", fake_measure)

    original = internal_agent_adapter.resolve_code_authority
    user_authority = SimpleNamespace(scope={"project_id": "P", "organization_id": "ORG", "owner_id": "QA-1"})

    async def resolve(principal, context, **kwargs):
        if isinstance(principal, dict):  # the signed-in user; the automation path stays real
            return user_authority
        return await original(principal, context, **kwargs)

    monkeypatch.setattr(internal_agent_adapter, "resolve_code_authority", resolve)
    interpretation = {"status": "completed", "analysis": "No new findings.", "recommendations": [],
                      "critical_issues": [], "errors": []}
    interpret = AsyncMock(return_value=interpretation)
    monkeypatch.setattr(internal_agent_adapter, "interpret_code", interpret)
    return interpret, interpretation


@pytest.mark.anyio
async def test_pr_comparison_parent_receives_one_scoped_interpretation(repository_client, monkeypatch):
    client, _, github, mock_db = repository_client
    interpret, interpretation = _arrange(github, monkeypatch)

    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "pr_comparison", "pr_number": 17, "use_ai": True,
    })
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    parent = await mock_db.code_quality_runs.find_one({"run_id": run_id})
    assert parent["status"] == "completed"
    assert parent["ai_status"] == "completed"
    assert parent["ai_analysis"] == interpretation
    assert parent["ai_authorization_scope"]["project_id"] == "P"
    assert parent["ai_provenance"]["model_interpretation"] == "ADVISORY"

    interpret.assert_awaited_once()
    package, context = interpret.await_args.args[0], interpret.await_args.args[1]
    assert context == {"project_id": "P", "commit_sha": HEAD_REVISION}
    comparison = package["pr_comparison"]
    assert (comparison["base_score"], comparison["head_score"], comparison["delta"]) == (72, 86, 14)
    assert comparison["finding_changes"]["status"] == "available"
    # Scores stay the measured ones; the interpretation never rewrites them.
    assert parent["quality_comparison"]["head_score"] == 86

    for side in ("base", "head"):
        child = await mock_db.code_quality_runs.find_one({"run_id": f"{run_id}-{side}"})
        assert "ai_analysis" not in child


@pytest.mark.anyio
async def test_pr_comparison_interpretation_is_compulsory_even_when_ai_was_not_requested(repository_client, monkeypatch):
    client, _, github, mock_db = repository_client
    interpret, _ = _arrange(github, monkeypatch)
    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "pr_comparison", "pr_number": 17, "use_ai": False,
    })
    parent = await mock_db.code_quality_runs.find_one({"run_id": response.json()["run_id"]})
    assert parent["status"] == "completed"
    assert parent["ai_status"] == "completed"
    assert parent["report_status"] == "complete" and parent["report_incomplete_reasons"] == []
    interpret.assert_awaited_once()
    assert interpret.await_args.args[0]["dependency_audit"] == "not_checked"
    assert parent["dependency_audit"] == {"base": "not_checked", "head": "not_checked"}


@pytest.mark.anyio
async def test_failed_inference_marks_the_report_incomplete_and_keeps_measured_scores(repository_client, monkeypatch):
    client, _, github, mock_db = repository_client
    interpret, _ = _arrange(github, monkeypatch)
    interpret.return_value = internal_agent_adapter.failed_interpretation("MODEL_UNAVAILABLE", unavailable=True)
    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "pr_comparison", "pr_number": 17,
    })
    parent = await mock_db.code_quality_runs.find_one({"run_id": response.json()["run_id"]})
    assert parent["status"] == "completed"  # the measured comparison stands
    assert parent["quality_comparison"]["delta"] == 14
    assert parent["ai_status"] == "unavailable"
    assert parent["report_status"] == "incomplete"
    assert parent["report_incomplete_reasons"] == ["ai_interpretation_unavailable:MODEL_UNAVAILABLE"]


def test_clean_code_summary_is_fixed_fact_and_never_invented():
    model_answer = {"status": "completed", "analysis": "Several areas require attention.",
                    "recommendations": ["Refactor everything"], "critical_issues": ["Unclear"], "errors": []}
    grounded = internal_agent_adapter.grounded_interpretation(model_answer, {
        "files_analyzed": 2, "static_analysis": {"findings": []}, "dependency_audit": "not_checked_offline",
        "tests": {"coverage": {"line_coverage": None}}})
    assert grounded["grounding"] == "no_findings"
    assert "no findings" in grounded["analysis"] and "attention" not in grounded["analysis"]
    assert grounded["recommendations"] == [] and grounded["critical_issues"] == []
    assert grounded["evidence_basis"] == [
        "0 analyzer finding(s) from 2 analysed file(s) were given to the model.",
        "Dependency vulnerabilities were not checked: the isolated worker cannot reach advisory databases.",
        "Test coverage was not measured.",
    ]


def test_cited_recommendations_are_capped_and_kept_short():
    finding = {"file": "a.py", "line": 3, "rule_id": "RUFF-F401", "message": "unused import"}
    model_answer = {"status": "completed", "analysis": "One unused import.", "errors": [], "critical_issues": [],
                    "recommendations": [f"[a.py:3 RUFF-F401] fix {i} " + "x" * 400 for i in range(5)]}
    grounded = internal_agent_adapter.grounded_interpretation(model_answer, {
        "files_analyzed": 1, "static_analysis": {"findings": [finding]},
        "pr_comparison": {"base_score": 90, "head_score": 88,
                          "finding_changes": {"status": "available", "counts": {"new": 1, "existing": 0, "resolved": 0}}}})
    assert grounded["grounding"] == "cited_findings" and grounded["analysis"] == "One unused import."
    assert len(grounded["recommendations"]) == 3
    assert all(len(text) <= 280 for text in grounded["recommendations"])
    assert "Base vs head quality score: 90 -> 88; findings new 1, unchanged 0, resolved 0." in grounded["evidence_basis"]


def test_failed_interpretations_are_left_unchanged():
    failed = internal_agent_adapter.failed_interpretation("INVALID_AGENT_RESULT")
    assert internal_agent_adapter.grounded_interpretation(failed, {}) is failed


@pytest.mark.parametrize("record,expected", [
    ({"tools_skipped": ["dependency-advisories-offline"], "tools_executed": ["ruff"]}, "not_checked_offline"),
    ({"tools_skipped": [], "tools_executed": ["pip-audit"]}, "checked"),
    ({"tools_skipped": [], "tools_executed": ["npm-audit"]}, "checked"),
    ({"tools_skipped": ["pip-audit"], "tools_executed": ["ruff"]}, "not_checked"),
])
def test_dependency_audit_is_never_reported_as_checked_unless_an_auditor_ran(record, expected):
    assert pr_quality_comparison.dependency_audit(record) == expected


def test_comparison_evidence_is_rendered_as_data_and_withheld_changes_are_not_claimed():
    available = _build_evidence_text({"pr_comparison": {
        "base_score": 72, "head_score": 86,
        "finding_changes": {"status": "available", "counts": {"new": 1, "existing": 2, "resolved": 3}}}}, {})
    assert "score 72 -> 86" in available and "new 1, existing 2, resolved 3" in available
    withheld = _build_evidence_text({"pr_comparison": {
        "finding_changes": {"status": "unavailable", "reason": "partial_evidence"}}}, {})
    assert "partial_evidence" in withheld and "do not claim" in withheld
