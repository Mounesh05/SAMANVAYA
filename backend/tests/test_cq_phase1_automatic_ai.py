"""Phase 1 CQ-27/CQ-26: automatic (webhook) PR comparisons cannot bypass the compulsory AI.

The automatic path calls ``compare_revisions`` without a caller-supplied interpreter.
It now gets the same interpretation as the manual path, under the server-owned
automation authority; a duplicate delivery replays the stored report without
calling the model or the analyzers again.
"""
from unittest.mock import AsyncMock

import pytest

from domain.services.github_api_service import GitHubAPIService
from intelligence.evidence.models import CodeQualityEvidence

BASE_SHA, HEAD_SHA = "1" * 40, "2" * 40


def _arrange(mock_db, monkeypatch, interpretation):
    from domain.services import internal_agent_adapter
    from domain.services import pr_quality_comparison as comparison
    monkeypatch.setattr(comparison, "col", mock_db.get_collection)
    authority = internal_agent_adapter.CodeAuthority(
        {"organization_id": "O", "project_id": "P", "owner_id": "github-automation:P"}, {}, "SERVER_OWNED_GITHUB_REVISION")
    monkeypatch.setattr(internal_agent_adapter, "resolve_code_authority", AsyncMock(return_value=authority))
    interpret = AsyncMock(return_value=interpretation)
    monkeypatch.setattr(internal_agent_adapter, "interpret_code", interpret)
    api = GitHubAPIService()
    api.fetch_analysis_sources = AsyncMock(return_value=({"app.py": "def ok():\n    return 1\n"}, []))

    async def analyze(service, paths, context):
        return CodeQualityEvidence(repository_id="P", commit_sha=context["commit_sha"], primary_language="python",
                                   files_analyzed=1, tools_executed=["ruff"])

    async def measure(evidence, paths):
        score = 80 if evidence.commit_sha == BASE_SHA else 84
        return {"status": "completed", "quality_analysis_status": "available", "quality_score": score,
                "quality_grade": "B", "risk_score": 20, "risk_level": "low", "tools_executed": ["ruff"],
                "tools_skipped": [], "function_discovery": evidence.function_discovery.model_dump(mode="json")}

    monkeypatch.setattr(comparison.CodeQualityService, "analyze_pr", analyze)
    monkeypatch.setattr(comparison, "measure_quality", measure)
    return comparison, api, interpret, authority


PR = {"number": 9, "base": {"sha": BASE_SHA}, "head": {"sha": HEAD_SHA}}
FILES = [{"filename": "app.py", "status": "modified"}]


@pytest.mark.anyio
async def test_automatic_pr_comparison_gets_the_compulsory_interpretation(mock_db, monkeypatch):
    completed = {"status": "completed", "analysis": "No findings.", "recommendations": [], "critical_issues": [],
                 "errors": []}
    comparison, api, interpret, authority = _arrange(mock_db, monkeypatch, completed)
    parent, _ = await comparison.compare_revisions(api, "P", "owner", "repo", PR, FILES, "webhook-opened")
    stored = await mock_db.code_quality_runs.find_one({"run_id": parent["run_id"]})
    assert stored["ai_required"] is True and stored["ai_status"] == "completed"
    assert stored["report_status"] == "complete" and stored["report_incomplete_reasons"] == []
    assert stored["ai_authorization_scope"]["owner_id"] == "github-automation:P"
    provenance = stored["ai_provenance"]
    assert provenance["policy_version"] == "code-quality-advisory-v1"
    assert provenance["evidence_digest"].startswith("sha256:") and isinstance(provenance["latency_ms"], int)
    assert provenance["model"]
    package, context = interpret.await_args.args[0], interpret.await_args.args[1]
    assert context == {"project_id": "P", "commit_sha": HEAD_SHA}
    assert package["pr_comparison"]["delta"] == 4
    assert interpret.await_args.args[2] is authority
    assert stored["quality_comparison"]["delta"] == 4  # the measured comparison is unchanged
    for side in ("base", "head"):
        child = await mock_db.code_quality_runs.find_one({"run_id": f"{parent['run_id']}-{side}"})
        assert "ai_analysis" not in child


@pytest.mark.anyio
async def test_duplicate_delivery_replays_without_a_second_model_call(mock_db, monkeypatch):
    completed = {"status": "completed", "analysis": "No findings.", "recommendations": [], "critical_issues": [],
                 "errors": []}
    comparison, api, interpret, _ = _arrange(mock_db, monkeypatch, completed)
    first, _ = await comparison.compare_revisions(api, "P", "owner", "repo", PR, FILES, "webhook-opened")
    again, _ = await comparison.compare_revisions(api, "P", "owner", "repo", PR, FILES, "webhook-synchronize")
    assert again["run_id"] == first["run_id"]
    interpret.assert_awaited_once()
    assert api.fetch_analysis_sources.await_count == 2  # base and head, once


@pytest.mark.anyio
async def test_automatic_comparison_with_the_model_down_is_partial_and_retryable(mock_db, monkeypatch):
    from domain.services import internal_agent_adapter
    down = internal_agent_adapter.failed_interpretation("MODEL_UNAVAILABLE", unavailable=True)
    comparison, api, _, _ = _arrange(mock_db, monkeypatch, down)
    parent, _ = await comparison.compare_revisions(api, "P", "owner", "repo", PR, FILES, "webhook-opened")
    stored = await mock_db.code_quality_runs.find_one({"run_id": parent["run_id"]})
    assert stored["status"] == "completed" and stored["quality_comparison"]["delta"] == 4
    assert stored["ai_status"] == "unavailable" and stored["report_status"] == "partial"
    assert stored["ai_request"]["context"]["commit_sha"] == HEAD_SHA and stored["ai_attempts"] == 1
