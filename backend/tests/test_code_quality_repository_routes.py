"""HTTP coverage for repository discovery and repository analysis intake."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routes import code_quality
from core import authorization, database
from core.dependencies import get_current_user
from domain.services import github_api_service, pr_quality_comparison
from domain.services.github_api_service import GitHubAPIService as RealGitHubAPIService
from intelligence.evidence.models import CodeQualityEvidence

REVISION = "a" * 40
BASE_REVISION = "1" * 40
HEAD_REVISION = "2" * 40
TREE_ID = "b" * 40
BASE = "/api/code-quality"


@pytest.fixture
async def repository_client(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization._project_repo, "col", mock_db.projects)
    await mock_db.projects.insert_one({"id": "P", "org_id": "ORG"})
    await mock_db.github_project_configs.insert_one({
        "project_id": "P", "org_id": "ORG",
        "repository_owner": "owner", "repository_name": "repo", "default_branch": "main",
    })
    github = Mock()
    github.client.list_branches = AsyncMock(return_value=[{"name": "main", "commit": {"sha": REVISION}}])
    github.client.get_commit = AsyncMock(return_value={"sha": REVISION, "commit": {"tree": {"sha": TREE_ID}}})
    github.client.get_source_tree = AsyncMock(return_value={
        "sha": TREE_ID,
        "truncated": False,
        "tree": [{"path": "src/app.py", "mode": "100644", "type": "blob"}],
    })
    github.list_repository_tree_summary = AsyncMock(return_value={
        "files": ["src/app.py"], "directories": ["src"], "excluded_files_count": 0,
        "unsupported_files_count": 0, "unsupported_extensions": {},
    })
    github.list_pull_requests = AsyncMock(return_value=[{"number": 17, "title": "Fix quality scope"}])
    github.list_repository_analysis_paths = AsyncMock(return_value=[])
    github.expand_selected_paths = AsyncMock(return_value=[])
    github.fetch_analysis_sources = AsyncMock(return_value=({}, []))
    monkeypatch.setattr(github_api_service, "GitHubAPIService", lambda: github)
    user = {"role": "QA", "org_id": "ORG", "employee_id": "QA-1", "project_ids": ["P"]}
    app = FastAPI()
    app.include_router(code_quality.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, user, github, mock_db


@pytest.mark.anyio
@pytest.mark.parametrize(("route", "field", "expected"), [
    ("branches", "branches", [{"name": "main", "commit_sha": REVISION, "protected": False}]),
    ("files", "files", ["src/app.py"]),
    ("pull-requests", "pull_requests", [{"number": 17, "title": "Fix quality scope", "state": "open",
                                        "base_ref": None, "head_ref": None, "base_sha": None,
                                        "head_sha": None, "author": None, "updated_at": None}]),
])
async def test_discovery_routes_enforce_project_tenant(repository_client, route, field, expected):
    client, user, _, _ = repository_client
    path = f"{BASE}/repositories/P/{route}"
    response = await client.get(path)
    assert response.status_code == 200
    assert response.json()[field] == expected
    user["org_id"] = "OTHER"
    assert (await client.get(path)).status_code == 403


@pytest.mark.anyio
async def test_branches_fallback_when_github_fails(repository_client):
    client, _, github, _ = repository_client
    github.client.list_branches = AsyncMock(side_effect=RuntimeError("GitHub rate limited"))
    response = await client.get(f"{BASE}/repositories/P/branches")
    assert response.status_code == 200
    assert response.json() == {
        "repository_id": "P",
        "repository": "owner/repo",
        "default_branch": "main",
        "branches": [{"name": "main", "commit_sha": None, "protected": False}],
        "branches_available": False,
    }


@pytest.mark.anyio
@pytest.mark.parametrize("ref", ["../secret", "a//b", "-bad"])
async def test_files_route_rejects_invalid_ref(repository_client, ref):
    client, _, _, _ = repository_client
    response = await client.get(f"{BASE}/repositories/P/files", params={"ref": ref})
    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [
    {"file_scope": "repository", "repository_ref": "../secret"},
    {"file_scope": "repository", "repository_ref": "a..b"},
    {"file_scope": "repository", "repository_ref": "a//b"},
    {"file_scope": "repository", "repository_ref": "-bad"},
    {"file_scope": "selected_files", "changed_files": ["src/app.py"], "pr_number": 17, "repository_ref": "main"},
])
async def test_analyze_rejects_invalid_ref(repository_client, payload):
    client, _, _, _ = repository_client
    response = await client.post(f"{BASE}/analyze", json={"repository_id": "P", **payload})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_analyze_enforces_project_tenant(repository_client):
    client, user, _, _ = repository_client
    user["org_id"] = "OTHER"
    response = await client.post(f"{BASE}/analyze", json={"repository_id": "P", "file_scope": "repository"})
    assert response.status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [
    {"file_scope": "repository"},
    {"file_scope": "selected_files", "changed_files": ["src/"]},
])
async def test_empty_source_scope_preserves_reason(repository_client, payload):
    client, _, github, _ = repository_client
    response = await client.post(f"{BASE}/analyze", json={"repository_id": "P", **payload})
    assert response.status_code == 202
    run = await client.get(f"{BASE}/runs/{response.json()['run_id']}")
    assert run.status_code == 200
    assert run.json()["status"] == "unsupported"
    assert run.json()["quality_unavailable_reason"] == "No supported source files found in the selected scope."
    github.fetch_analysis_sources.assert_not_awaited()


@pytest.mark.anyio
async def test_repository_analysis_executes_non_empty_tree(repository_client, monkeypatch):
    client, _, github, _ = repository_client
    github.list_repository_analysis_paths = AsyncMock(return_value=["src/app.py"])
    github.fetch_analysis_sources = AsyncMock(return_value=({"src/app.py": "def ok():\n    return 1\n"}, []))
    evidence = CodeQualityEvidence(
        repository_id="P", commit_sha=REVISION, primary_language="python",
        files_analyzed=1, tools_executed=["ruff"],
    )
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", AsyncMock(return_value=evidence))

    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "repository", "repository_ref": "release/v2", "use_ai": False,
    })
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    github.client.get_commit.assert_awaited_once_with("owner", "repo", "release/v2")
    github.list_repository_analysis_paths.assert_awaited_once()
    github.fetch_analysis_sources.assert_awaited_once()

    run = await client.get(f"{BASE}/runs/{run_id}")
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    assert body["file_scope"] == "repository"
    assert body["repository_ref"] == "release/v2"
    assert body["commit_sha"] == REVISION
    assert body["changed_files"] == ["src/app.py"]
    assert body["source_selection_count"] == 1
    assert body["files_analyzed"] == 1
    assert body["quality_score"] is not None

    history = await client.get(f"{BASE}/repositories/P/history")
    assert history.status_code == 200
    item = history.json()["history"][0]
    assert item["changed_files"] == ["src/app.py"]
    assert item["source_selection_count"] == 1
    assert item["files_analyzed"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize("selection", ["src", "src/"])
async def test_selected_files_expands_directories_with_or_without_trailing_slash(repository_client, monkeypatch, selection):
    client, _, github, _ = repository_client
    real_api = RealGitHubAPIService()
    real_api.client = github.client
    real_api.fetch_analysis_sources = AsyncMock(return_value=({"src/app.py": "def ok():\n    return 1\n"}, []))
    monkeypatch.setattr(github_api_service, "GitHubAPIService", lambda: real_api)
    evidence = CodeQualityEvidence(
        repository_id="P", commit_sha=REVISION, primary_language="python",
        files_analyzed=1, tools_executed=["ruff"],
    )
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", AsyncMock(return_value=evidence))

    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "selected_files", "changed_files": [selection], "use_ai": False,
    })
    assert response.status_code == 202
    run = await client.get(f"{BASE}/runs/{response.json()['run_id']}")
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    assert body["file_scope"] == "selected_files"
    assert body["selected_scope"] == [selection]
    assert body["changed_files"] == ["src/app.py"]
    assert body["source_selection_count"] == 1


@pytest.mark.anyio
async def test_selected_files_requires_connected_repository(repository_client):
    client, _, _, mock_db = repository_client
    await mock_db.github_project_configs.delete_many({"project_id": "P"})
    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "selected_files", "changed_files": ["src"], "use_ai": False,
    })
    assert response.status_code == 202
    run = await client.get(f"{BASE}/runs/{response.json()['run_id']}")
    assert run.status_code == 200
    assert run.json()["status"] == "failed"
    assert "Connect a GitHub repository" in run.json()["error"]


@pytest.mark.anyio
async def test_pr_comparison_analysis_executes_via_analyze_endpoint(repository_client, monkeypatch):
    client, _, github, _ = repository_client
    github.client.get_pull_request = AsyncMock(return_value={
        "number": 17, "base": {"sha": BASE_REVISION}, "head": {"sha": HEAD_REVISION},
    })
    github.client.get_pr_files = AsyncMock(return_value=[{"filename": "src/app.py", "status": "modified"}])
    github.fetch_analysis_sources = AsyncMock(return_value=({"src/app.py": "def ok():\n    return 1\n"}, []))

    async def fake_analyze(self, paths, context, **kwargs):
        return CodeQualityEvidence(
            repository_id="P", commit_sha=context["commit_sha"], primary_language="python",
            files_analyzed=1, tools_executed=["ruff"],
        )

    async def fake_measure(evidence, paths):
        score = 72 if evidence.commit_sha == BASE_REVISION else 86
        return {
            "status": "completed", "quality_analysis_status": "available", "quality_score": score,
            "quality_grade": "B", "risk_score": 15, "risk_level": "low", "language": "python",
            "tools_executed": ["ruff"], "tools_skipped": [],
            "function_discovery": evidence.function_discovery.model_dump(mode="json"),
        }

    monkeypatch.setattr(pr_quality_comparison.CodeQualityService, "analyze_pr", fake_analyze)
    monkeypatch.setattr(pr_quality_comparison, "measure_quality", fake_measure)

    response = await client.post(f"{BASE}/analyze", json={
        "repository_id": "P", "file_scope": "pr_comparison", "pr_number": 17, "use_ai": False,
    })
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    run = await client.get(f"{BASE}/runs/{run_id}")
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    assert body["kind"] == "pr_quality_comparison"
    assert body["file_scope"] == "pr_comparison"
    assert body["child_run_ids"] == {"base": f"{run_id}-base", "head": f"{run_id}-head"}
    assert body["quality_comparison"]["base_score"] == 72
    assert body["quality_comparison"]["head_score"] == 86
    assert body["quality_comparison"]["delta"] == 14


@pytest.mark.anyio
async def test_history_projection_preserves_legacy_and_file_count_fields(repository_client):
    client, _, _, mock_db = repository_client
    await mock_db.code_quality_runs.insert_many([
        {
            "run_id": "RUN-LEGACY", "repository_id": "P", "org_id": "ORG",
            "created_at": "2026-11-27T10:00:00Z", "status": "completed",
            "quality_analysis_status": "partial", "changed_files": ["a.py"],
            "source_selection_count": 1, "files_analyzed": 1, "tools_executed": ["ruff"],
        },
        {
            "run_id": "RUN-COMP", "repository_id": "P", "org_id": "ORG",
            "created_at": "2026-11-27T11:00:00Z", "status": "completed",
            "kind": "pr_quality_comparison", "file_scope": "pr_comparison",
            "quality_analysis_status": "partial",
            "file_counts": {"base": {"selected": 1, "analyzed": 1}, "head": {"selected": 1, "analyzed": 1}},
        },
    ])
    response = await client.get(f"{BASE}/repositories/P/history")
    assert response.status_code == 200
    history = {item["run_id"]: item for item in response.json()["history"]}
    assert history["RUN-LEGACY"]["changed_files"] == ["a.py"]
    assert history["RUN-LEGACY"]["source_selection_count"] == 1
    assert history["RUN-LEGACY"]["files_analyzed"] == 1
    assert history["RUN-COMP"]["file_counts"] == {
        "base": {"selected": 1, "analyzed": 1}, "head": {"selected": 1, "analyzed": 1},
    }


@pytest.mark.anyio
async def test_legacy_intake_requires_files_or_pr(repository_client):
    client, _, _, _ = repository_client
    response = await client.post(f"{BASE}/analyze", json={"repository_id": "P"})
    assert response.status_code == 422
    assert response.json()["detail"] == "At least one real changed file is required"
