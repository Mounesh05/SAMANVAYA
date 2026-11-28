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
async def test_pr_comparison_without_ai_records_a_skip_and_never_calls_the_model(repository_client, monkeypatch):
    client, _, github, mock_db = repository_client
    interpret, _ = _arrange(github, monkeypatch)
    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "pr_comparison", "pr_number": 17, "use_ai": False,
    })
    parent = await mock_db.code_quality_runs.find_one({"run_id": response.json()["run_id"]})
    assert parent["status"] == "completed"
    assert parent["ai_status"] == "skipped"
    interpret.assert_not_awaited()


def test_comparison_evidence_is_rendered_as_data_and_withheld_changes_are_not_claimed():
    available = _build_evidence_text({"pr_comparison": {
        "base_score": 72, "head_score": 86,
        "finding_changes": {"status": "available", "counts": {"new": 1, "existing": 2, "resolved": 3}}}}, {})
    assert "score 72 -> 86" in available and "new 1, existing 2, resolved 3" in available
    withheld = _build_evidence_text({"pr_comparison": {
        "finding_changes": {"status": "unavailable", "reason": "partial_evidence"}}}, {})
    assert "partial_evidence" in withheld and "do not claim" in withheld
