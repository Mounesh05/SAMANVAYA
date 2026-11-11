"""Project authorization and server-owned approval boundary over the real routes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import algorithms, code_quality
from core.dependencies import get_current_user
from domain.models.project_code_config import ProjectCodeConfig
from domain.services.requirement_discovery_service import RequirementDiscoveryService
from test_requirement_discovery import source

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(mock_db, monkeypatch):
    service = RequirementDiscoveryService(mock_db)
    monkeypatch.setattr(algorithms, "requirement_service", service)
    monkeypatch.setattr(algorithms.ProjectRepository, "find_by_id", AsyncMock(side_effect=lambda key: {"id": key, "org_id": "org" if key == "P1" else "foreign"}))
    user = {"employee_id": "author", "org_id": "org", "role": "DEVELOPER", "project_ids": ["P1"]}
    app = FastAPI()
    app.include_router(algorithms.router, prefix="/algorithms")
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(client=client, user=user, service=service, db=mock_db)


async def test_only_authorized_project_requirements_can_be_read(api):
    response = await api.client.post("/algorithms/requirements/discover", json={"project_id": "P2"})
    assert response.status_code == 403
    response = await api.client.get("/algorithms/projects/P2/requirement-sources")
    assert response.status_code == 403


async def test_no_source_payload_can_forge_authority(api):
    response = await api.client.post("/algorithms/requirements/sources", json={**source(), "status": "APPROVED"})
    assert response.status_code == 422
    response = await api.client.post("/algorithms/requirements/discover", json={"project_id": "P1", "context": {"requirements": [{"value": 999}]}})
    assert response.status_code == 422


async def test_source_approval_is_independent_and_visible_in_discovery(api):
    doc = (await api.client.post("/algorithms/requirements/sources", json=source())).json()
    review = {"expected_fingerprint": doc["payload_fingerprint"], "source_reference": "review:1", "rationale": "Verified exact values", "scope_reviewed": True}
    path = "/algorithms/requirements/sources/" + doc["source_id"] + "/approve"
    api.user["role"] = "LEAD"
    assert (await api.client.post(path, json=review)).status_code == 403
    api.user["employee_id"] = "independent"
    assert (await api.client.post(path, json={**review, "expected_fingerprint": "stale"})).status_code == 409
    response = await api.client.post(path, json=review)
    assert response.status_code == 200
    report = (await api.client.post("/algorithms/requirements/discover", json={"project_id": "P1"})).json()
    assert report["established"][0]["value"] == 0.1
    assert report["established"][0]["authority_status"] == "AUTHORITATIVE"
    listed = (await api.client.get("/algorithms/projects/P1/requirement-sources")).json()
    assert listed["sources"][0]["approval"]["approved_by"] == "independent"


async def test_general_config_write_cannot_remove_or_forge_approved_source_references(mock_db, monkeypatch):
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    monkeypatch.setattr(code_quality, "verify_project_access", AsyncMock())
    await mock_db.project_configs.insert_one({"project_id": "P1", "algorithm_requirement_source_ids": ["real"]})
    await code_quality.save_project_config("P1", ProjectCodeConfig(project_id="P1", algorithm_requirement_source_ids=["forged"]), {})
    stored = await mock_db.project_configs.find_one({"project_id": "P1"})
    assert stored["algorithm_requirement_source_ids"] == ["real"]


async def test_pr_sync_preserves_requirement_context_without_treating_review_as_authority():
    from integrations.github.normalizer import GitHubNormalizer
    raw = {"number": 1, "title": "Budget", "state": "open", "user": {"login": "dev"}, "head": {"ref": "branch", "sha": "abc"},
        "base": {"ref": "testing"}, "created_at": "2026-11-10", "updated_at": "2026-11-11", "html_url": "https://example.invalid/pr/1", "id": 1,
        "body": "Latency matters", "mergeable_state": "clean"}
    doc = GitHubNormalizer.normalize_pull_request(raw, "P1", "a/b")
    assert doc["description"] == "Latency matters" and doc["head_sha"] == "abc" and doc["updated_at"] == "2026-11-11"
    assert "requirement_approval" not in doc
