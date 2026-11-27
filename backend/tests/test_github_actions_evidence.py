"""Actions observations remain separate from Checks and independently verified tests."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

SHA = "a" * 40
REPO = "example/project"


def workflow(identifier=10, status="completed", conclusion="success"):
    return {"id": identifier, "workflow_id": 2, "run_attempt": 1, "repository": {"full_name": REPO},
            "head_sha": SHA, "status": status, "conclusion": conclusion, "name": "CI", "event": "pull_request"}


def job(run_id=10, status="completed", conclusion="success"):
    return {"id": run_id + 100, "run_id": run_id, "run_attempt": 1, "head_sha": SHA,
            "run_url": f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}",
            "name": "tests", "status": status, "conclusion": conclusion}


def client(runs=None, jobs=None):
    runs = [workflow()] if runs is None else runs
    jobs = [job()] if jobs is None else jobs
    return SimpleNamespace(list_workflow_runs=AsyncMock(return_value={"total_count": len(runs), "workflow_runs": runs}),
        list_workflow_jobs=AsyncMock(return_value={"total_count": len(jobs), "jobs": jobs}))


def http_error(status, headers=None):
    response = httpx.Response(status, headers=headers, request=httpx.Request("GET", "https://api.github.com"))
    return httpx.HTTPStatusError("Provider failure", request=response.request, response=response)


@pytest.mark.anyio
@pytest.mark.parametrize("conclusion,expected", [("success", "success"), ("failure", "failure"),
    ("cancelled", "cancelled"), ("timed_out", "failure"), ("skipped", "unknown")])
async def test_exact_run_and_job_identity_and_reported_outcomes(conclusion, expected):
    from integrations.github.ci_evidence import collect_actions_ci

    api = client([workflow(conclusion=conclusion)], [job(conclusion=conclusion)])
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert result["status"] == "available"
    assert result["reported_outcome"] == expected
    assert result["repository"] == REPO and result["commit_sha"] == SHA
    assert result["runs"][0]["run_id"] == 10 and result["runs"][0]["run_attempt"] == 1
    assert result["runs"][0]["jobs"][0]["job_id"] == 110
    assert len(result["content_sha256"]) == 64
    assert result["authority"] == "GITHUB_REPORTED_OUTCOME"
    assert "check_runs" not in result and "tests_passed" not in str(result)
    api.list_workflow_jobs.assert_awaited_once_with("example", "project", 10, 1, page=1)


@pytest.mark.anyio
async def test_pending_workflow_is_not_a_pass():
    from integrations.github.ci_evidence import collect_actions_ci

    result = await collect_actions_ci(client([workflow(status="in_progress", conclusion=None)],
        [job(status="queued", conclusion=None)]), "example", "project", SHA)
    assert result["reported_outcome"] == "pending"


@pytest.mark.anyio
async def test_multiple_workflows_are_retained_not_counted_as_independent_proof():
    from integrations.github.ci_evidence import collect_actions_ci

    api = client([workflow(), workflow(20, conclusion="failure")])
    api.list_workflow_jobs.side_effect = [{"total_count": 1, "jobs": [job()]}, {"total_count": 1, "jobs": [job(20, conclusion="failure")]}]
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert len(result["runs"]) == 2 and result["reported_outcome"] == "failure"


@pytest.mark.anyio
async def test_no_matching_workflows_is_missing_not_permission_denied():
    from integrations.github.ci_evidence import collect_actions_ci

    result = await collect_actions_ci(client([]), "example", "project", SHA)
    assert result["status"] == "missing" and result["reported_outcome"] == "unknown"


@pytest.mark.anyio
@pytest.mark.parametrize("field,value", [("head_sha", "b" * 40), ("repository", {"full_name": "other/repo"})])
async def test_wrong_commit_or_repository_is_rejected(field, value):
    from integrations.github.ci_evidence import collect_actions_ci

    run = workflow()
    run[field] = value
    api = client([run])
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert result["status"] == "partial" and result["runs"] == []
    assert result["reported_outcome"] == "unknown"
    api.list_workflow_jobs.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("field,value", [("run_id", 999), ("run_attempt", 2), ("head_sha", "b" * 40),
    ("run_url", "https://api.github.com/repos/other/repo/actions/runs/10")])
async def test_wrong_job_scope_never_becomes_evidence(field, value):
    from integrations.github.ci_evidence import collect_actions_ci

    invalid = job()
    invalid[field] = value
    result = await collect_actions_ci(client(jobs=[invalid]), "example", "project", SHA)
    assert result["status"] == "partial" and result["reported_outcome"] == "unknown"
    assert result["runs"][0]["jobs"] == []


@pytest.mark.anyio
@pytest.mark.parametrize("error,kind", [(http_error(403), "permission_denied"),
    (http_error(403, {"x-ratelimit-remaining": "0"}), "rate_limited"),
    (http_error(429, {"Retry-After": "60"}), "rate_limited")])
async def test_denied_and_rate_limited_requests_are_not_missing_ci(error, kind):
    from integrations.github.ci_evidence import collect_actions_ci

    api = client()
    api.list_workflow_runs.side_effect = error
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert result["status"] == "unavailable" and result["errors"][0]["kind"] == kind
    assert api.list_workflow_runs.await_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("error", [http_error(503), httpx.ReadTimeout("timeout")])
async def test_transient_failures_have_one_bounded_retry(error):
    from integrations.github.ci_evidence import collect_actions_ci

    api = client()
    api.list_workflow_runs.side_effect = [error, {"total_count": 1, "workflow_runs": [workflow()]}]
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert result["status"] == "available" and api.list_workflow_runs.await_count == 2


@pytest.mark.anyio
async def test_job_outage_keeps_run_identity_but_prevents_success_summary():
    from integrations.github.ci_evidence import collect_actions_ci

    api = client()
    api.list_workflow_jobs.side_effect = http_error(503)
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert result["status"] == "partial" and result["reported_outcome"] == "unknown"
    assert result["runs"][0]["run_id"] == 10


@pytest.mark.anyio
async def test_workflow_pagination_keeps_the_commit_filter():
    from integrations.github.ci_evidence import collect_actions_ci

    api = client()
    api.list_workflow_runs.side_effect = [{"total_count": 2, "workflow_runs": [workflow()]},
        {"total_count": 2, "workflow_runs": [workflow(20)]}]
    api.list_workflow_jobs.side_effect = [{"total_count": 1, "jobs": [job()]}, {"total_count": 1, "jobs": [job(20)]}]
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert len(result["runs"]) == 2
    api.list_workflow_runs.assert_any_await("example", "project", SHA, page=2)


@pytest.mark.anyio
async def test_pagination_bound_and_malformed_payloads_cannot_claim_complete_success():
    from integrations.github.ci_evidence import collect_actions_ci

    api = client()
    api.list_workflow_runs.return_value = {"total_count": 1000, "workflow_runs": [workflow()]}
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert result["status"] == "partial" and result["reported_outcome"] == "unknown"
    assert api.list_workflow_runs.await_count <= 3
    api.list_workflow_runs.return_value = [deepcopy(workflow())]
    result = await collect_actions_ci(api, "example", "project", SHA)
    assert result["status"] == "unavailable"


@pytest.mark.anyio
async def test_pat_fallback_does_not_fabricate_checks_or_a_global_pass():
    from domain.services.github_api_service import GitHubAPIService
    from integrations.github.normalizer import GitHubNormalizer

    service = GitHubAPIService(github_token="test-token")
    service.client.get_pull_request = AsyncMock(return_value={"head": {"sha": SHA}})
    service.client.get_pr_files = AsyncMock(return_value=[])
    service.client.get_pr_commits = AsyncMock(return_value=[])
    service.client.get_commit_check_runs = AsyncMock(side_effect=http_error(403))
    api = client()
    service.client.list_workflow_runs = api.list_workflow_runs
    service.client.list_workflow_jobs = api.list_workflow_jobs
    result = await service.fetch_pull_request_data("example", "project", 1)
    assert result["check_runs"]["check_runs"] == []
    assert result["check_runs"]["failure_kind"] == "permission_denied"
    assert result["actions_ci"]["reported_outcome"] == "success"
    normalized = GitHubNormalizer.normalize_ci_evidence(result["check_runs"], result["actions_ci"])
    assert normalized["ci_status"] is None  # No universal/all-provider green status.
    assert normalized["ci_evidence_status"] == "partial"
    assert normalized["non_actions_checks"]["status"] == "unavailable"
    assert normalized["github_actions_ci"]["runs"][0]["jobs"][0]["job_id"] == 110


@pytest.mark.anyio
async def test_authorized_app_retains_checks_without_requiring_actions_access():
    from domain.services.github_api_service import GitHubAPIService

    service = GitHubAPIService(github_token="installation-token")
    service.client.get_pull_request = AsyncMock(return_value={"head": {"sha": SHA}})
    service.client.get_pr_files = AsyncMock(return_value=[])
    service.client.get_pr_commits = AsyncMock(return_value=[])
    payload = {"check_runs": [{"id": 3, "name": "External scan", "status": "completed", "conclusion": "success"}]}
    service.client.get_commit_check_runs = AsyncMock(return_value=payload)
    service.client.list_workflow_runs = AsyncMock()
    result = await service.fetch_pull_request_data("example", "project", 1)
    assert result["check_runs"] == payload
    service.client.list_workflow_runs.assert_not_awaited()


@pytest.mark.anyio
async def test_actions_client_requests_are_read_only_and_attempt_pinned():
    from integrations.github.client import GitHubClient

    api = GitHubClient(token="test-token")
    api._make_request = AsyncMock(return_value=httpx.Response(200, json={}))
    await api.list_workflow_runs("example", "project", SHA, page=2)
    api._make_request.assert_awaited_with("GET", f"https://api.github.com/repos/{REPO}/actions/runs",
        params={"head_sha": SHA, "per_page": 100, "page": 2})
    await api.list_workflow_jobs("example", "project", 10, 2)
    api._make_request.assert_awaited_with("GET", f"https://api.github.com/repos/{REPO}/actions/runs/10/attempts/2/jobs",
        params={"per_page": 100, "page": 1})


@pytest.mark.anyio
async def test_shared_github_rate_limit_defers_fallback_without_spending_more_requests():
    from domain.services.github_api_service import GitHubAPIService

    service = GitHubAPIService(github_token="test-token")
    service.client.get_pull_request = AsyncMock(return_value={"head": {"sha": SHA}})
    service.client.get_pr_files = AsyncMock(return_value=[])
    service.client.get_pr_commits = AsyncMock(return_value=[])
    service.client.get_commit_check_runs = AsyncMock(side_effect=http_error(403, {"x-ratelimit-remaining": "0"}))
    service.client.list_workflow_runs = AsyncMock(return_value={"total_count": 0, "workflow_runs": []})
    result = await service.fetch_pull_request_data("example", "project", 1)
    assert result["actions_ci"]["status"] == "unavailable"
    assert result["actions_ci"]["errors"][0]["kind"] == "rate_limited"
    service.client.list_workflow_runs.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("project,repository,expected", [("P1", "other", 403), ("P2", "project", 403),
    ("P3", "project", 403), ("P1", "project", 200)])
async def test_sync_requires_project_scope_and_matching_server_repository(mock_db, monkeypatch, project, repository, expected):
    from fastapi import FastAPI
    from core.dependencies import get_current_user
    from api.routes import github
    from unittest.mock import Mock

    await mock_db.projects.insert_many([{"id": "P1", "org_id": "A"}, {"id": "P2", "org_id": "B"}, {"id": "P3", "org_id": "A"}])
    await mock_db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "example", "repository_name": "project"})
    monkeypatch.setattr(github, "col", lambda name: mock_db[name])
    async def find_project(self, key):
        return await mock_db.projects.find_one({"id": key})
    monkeypatch.setattr("repositories.project_repository.ProjectRepository.find_by_id", find_project)
    service = SimpleNamespace(sync_pull_request=AsyncMock(return_value={"pr": {"id": "PR1", "risk_level": "low", "risk_score": 1}}))
    factory = Mock(return_value=service)
    monkeypatch.setattr(github, "GitHubSyncService", factory)
    app = FastAPI()
    app.include_router(github.router)
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "D", "role": "DEVELOPER", "org_id": "A", "project_ids": ["P1"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client_http:
        result = await client_http.post("/sync-pr", json={"owner": "example", "repo": repository, "pr_number": 1, "project_id": project})
    assert result.status_code == expected
    if expected == 403:
        factory.assert_not_called()
    else:
        service.sync_pull_request.assert_awaited_once()


@pytest.mark.anyio
async def test_health_uses_existing_client_and_preserves_rate_limit(monkeypatch):
    from api.routes.github import github_integration_health
    from integrations.github.client import GitHubClient

    call = AsyncMock(return_value={"login": "private-identity", "rate_limit": {"remaining": 42}})
    monkeypatch.setattr(GitHubClient, "get_authenticated_user", call)
    assert await github_integration_health({"employee_id": "reviewer"}) == {
        "status": "operational", "rate_limit_remaining": 42}
    call.assert_awaited_once()


@pytest.mark.anyio
async def test_health_failure_never_reports_operational_or_exposes_exception(monkeypatch):
    from api.routes.github import github_integration_health
    from integrations.github.client import GitHubClient

    monkeypatch.setattr(GitHubClient, "get_authenticated_user", AsyncMock(side_effect=RuntimeError("private-provider-detail")))
    report = await github_integration_health({"employee_id": "reviewer"})
    assert report["status"] == "error"
    assert "private-provider-detail" not in str(report)
