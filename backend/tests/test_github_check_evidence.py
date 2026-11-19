"""Unavailable CI evidence must not abort PR sync or masquerade as passing CI."""

from unittest.mock import AsyncMock

import httpx
import pytest

from domain.services.github_api_service import GitHubAPIService
from integrations.github.normalizer import GitHubNormalizer


def api_service():
    service = GitHubAPIService(github_token="test-token")
    service.client.get_pull_request = AsyncMock(return_value={
        "number": 1, "id": 1, "title": "Update", "state": "open", "user": {"login": "developer"},
        "head": {"sha": "head", "ref": "feature"}, "base": {"ref": "main"},
        "created_at": "2026-01-01T00:00:00Z", "html_url": "https://github.com/example/project/pull/1"})
    service.client.get_pr_files = AsyncMock(return_value=[])
    service.client.get_pr_commits = AsyncMock(return_value=[])
    return service


def forbidden():
    response = httpx.Response(403, request=httpx.Request("GET", "https://api.github.com/check-runs"))
    return httpx.HTTPStatusError("Permission denied", request=response.request, response=response)


@pytest.mark.anyio
@pytest.mark.parametrize("error", [forbidden(), httpx.ReadTimeout("Timed out")])
async def test_unavailable_checks_keep_response_shape_and_unknown_ci(error):
    service = api_service()
    service.client.get_commit_check_runs = AsyncMock(side_effect=error)
    result = await service.fetch_pull_request_data("example", "project", 1)
    checks = result["check_runs"]
    assert isinstance(checks, dict)
    assert checks["evidence_status"] == "unavailable"
    normalized = GitHubNormalizer.normalize_check_runs(checks)
    assert normalized["ci_status"] is None
    assert normalized["ci_evidence_status"] == "unavailable"
    assert normalized["ci_unavailable_reason"]


@pytest.mark.anyio
async def test_successful_checks_preserve_existing_passing_behavior():
    service = api_service()
    service.client.get_commit_check_runs = AsyncMock(return_value={"check_runs": [
        {"name": "tests", "status": "completed", "conclusion": "success"}]})
    result = await service.fetch_pull_request_data("example", "project", 1)
    assert GitHubNormalizer.normalize_check_runs(result["check_runs"])["ci_status"] == "passing"


@pytest.mark.anyio
async def test_successful_empty_checks_are_distinct_from_unavailable_evidence():
    service = api_service()
    service.client.get_commit_check_runs = AsyncMock(return_value={"check_runs": []})
    result = await service.fetch_pull_request_data("example", "project", 1)
    assert result["check_runs"].get("evidence_status") != "unavailable"
    assert GitHubNormalizer.normalize_check_runs(result["check_runs"])["ci_status"] is None


@pytest.mark.anyio
async def test_pr_sync_stores_unknown_ci_and_continues_when_checks_are_forbidden(mock_db, monkeypatch):
    from core import database
    from domain.services.github_sync_service import GitHubSyncService

    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr("domain.services.github_sync_service.apply_task_progress", AsyncMock(return_value={}))
    service = GitHubSyncService()
    service.api_service = api_service()
    service.api_service.client.get_commit_check_runs = AsyncMock(side_effect=forbidden())
    service.api_service.fetch_analysis_sources = AsyncMock(return_value=({}, []))
    service.analysis_service.analyze_risk = AsyncMock(return_value={"risk_score": 0, "risk_level": "low"})
    service.analysis_service.analyze_with_ai = AsyncMock()
    service.pr_repo.store_revision = AsyncMock(side_effect=lambda doc, **kwargs: (doc, True))
    result = await service.sync_pull_request("example", "project", 1, "P1", use_ai=False)
    stored = service.pr_repo.store_revision.call_args.args[0]
    assert stored["ci_status"] is None
    assert stored["ci_evidence_status"] == "unavailable"
    assert result["ci_data"]["ci_evidence_status"] == "unavailable"
    assert not result["revision_superseded"]
    service.analysis_service.analyze_with_ai.assert_not_awaited()
