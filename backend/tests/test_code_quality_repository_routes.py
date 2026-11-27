"""HTTP coverage for repository discovery and repository analysis intake."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routes import code_quality
from core import authorization, database
from core.dependencies import get_current_user
from domain.services import github_api_service

REVISION = "a" * 40
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
    github.client.get_commit = AsyncMock(return_value={"sha": REVISION})
    github.list_repository_tree_summary = AsyncMock(return_value={
        "files": ["src/app.py"], "directories": ["src"], "excluded_files_count": 0,
        "unsupported_files_count": 0, "unsupported_extensions": {},
    })
    github.list_pull_requests = AsyncMock(return_value=[{"number": 17, "title": "Fix quality scope"}])
    github.list_repository_analysis_paths = AsyncMock(return_value=[])
    github.expand_selected_paths = AsyncMock(return_value=[])
    github.fetch_analysis_sources = AsyncMock()
    monkeypatch.setattr(github_api_service, "GitHubAPIService", lambda: github)
    user = {"role": "QA", "org_id": "ORG", "employee_id": "QA-1", "project_ids": ["P"]}
    app = FastAPI()
    app.include_router(code_quality.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, user, github


@pytest.mark.anyio
@pytest.mark.parametrize(("route", "field", "expected"), [
    ("branches", "branches", [{"name": "main", "commit_sha": REVISION, "protected": False}]),
    ("files", "files", ["src/app.py"]),
    ("pull-requests", "pull_requests", [{"number": 17, "title": "Fix quality scope", "state": "open",
                                        "base_ref": None, "head_ref": None, "base_sha": None,
                                        "head_sha": None, "author": None, "updated_at": None}]),
])
async def test_discovery_routes_enforce_project_tenant(repository_client, route, field, expected):
    client, user, _ = repository_client
    path = f"{BASE}/repositories/P/{route}"
    response = await client.get(path)
    assert response.status_code == 200
    assert response.json()[field] == expected
    user["org_id"] = "OTHER"
    assert (await client.get(path)).status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [
    {"file_scope": "repository"},
    {"file_scope": "selected_files", "changed_files": ["src/"]},
])
async def test_empty_source_scope_preserves_reason(repository_client, payload):
    client, _, github = repository_client
    response = await client.post(f"{BASE}/analyze", json={"repository_id": "P", **payload})
    assert response.status_code == 202
    run = await client.get(f"{BASE}/runs/{response.json()['run_id']}")
    assert run.status_code == 200
    assert run.json()["status"] == "unsupported"
    assert run.json()["quality_unavailable_reason"] == "No supported source files found in the selected scope."
    github.fetch_analysis_sources.assert_not_awaited()


@pytest.mark.anyio
async def test_legacy_intake_requires_files_or_pr(repository_client):
    client, _, _ = repository_client
    response = await client.post(f"{BASE}/analyze", json={"repository_id": "P"})
    assert response.status_code == 422
    assert response.json()["detail"] == "At least one real changed file is required"
