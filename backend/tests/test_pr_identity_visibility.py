"""GitHub authors and employee IDs are separate, tenant-scoped identities."""

import pytest

from repositories.pr_repository import PRRepository
from integrations.github.normalizer import GitHubNormalizer


def test_mergeability_is_not_review_approval():
    raw = {"id": 1, "number": 1, "title": "Update", "state": "open", "user": {"login": "developer"},
           "head": {"ref": "feature"}, "base": {"ref": "main"}, "created_at": "2026-01-01T00:00:00Z",
           "html_url": "https://github.com/example/project/pull/1", "mergeable_state": "clean"}
    assert GitHubNormalizer.normalize_pull_request(raw, "P1", "example/project")["review_status"] == "pending"


@pytest.mark.anyio
async def test_github_identity_lookup_includes_existing_prs_without_cross_scope_reads(mock_db, monkeypatch):
    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    await mock_db.users.insert_one({"employee_id": "DEV", "org_id": "A", "github_username": "Developer-Login", "project_ids": ["P1", "P-FOREIGN"]})
    await mock_db.projects.insert_many([{"id": "P1", "org_id": "A"}, {"id": "P2", "org_id": "A"}, {"id": "P-FOREIGN", "org_id": "B"}])
    await mock_db.pull_requests.insert_many([
        {"id": "github", "project_id": "P1", "author_id": "developer-login"},
        {"id": "legacy", "project_id": "P1", "author_id": "DEV"},
        {"id": "other-author", "project_id": "P1", "author_id": "someone-else"},
        {"id": "other-project", "project_id": "P2", "author_id": "developer-login"},
        {"id": "other-tenant", "project_id": "P-FOREIGN", "author_id": "developer-login"},
    ])
    result = await PRRepository().find_by_employee("DEV")
    assert {r["id"] for r in result} == {"github", "legacy"}


@pytest.mark.anyio
async def test_unlinked_employee_does_not_guess_a_github_identity(mock_db, monkeypatch):
    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    await mock_db.users.insert_one({"employee_id": "DEV", "org_id": "A", "name": "Developer Login", "project_ids": ["P1"]})
    await mock_db.projects.insert_one({"id": "P1", "org_id": "A"})
    await mock_db.pull_requests.insert_one({"id": "github", "project_id": "P1", "author_id": "developer-login"})
    assert await PRRepository().find_by_employee("DEV") == []


@pytest.mark.anyio
async def test_lead_queue_uses_team_project_scope_even_without_author_mapping(mock_db, monkeypatch):
    from api.roles import lead

    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.project_repository.col", lambda name: mock_db[name])
    await mock_db.projects.insert_many([
        {"id": "P1", "org_id": "A", "team_id": "T"},
        {"id": "P2", "org_id": "A", "team_id": "OTHER"},
        {"id": "P3", "org_id": "B", "team_id": "T"},
    ])
    for project in ("P1", "P2", "P3"):
        await mock_db.pull_requests.insert_one({"id": project, "project_id": project,
            "author_id": "unlinked-github-author", "status": "open", "review_status": "pending"})
    result = await lead.review_queue(user={"employee_id": "L", "role": "LEAD", "org_id": "A", "team_id": "T"})
    assert [pr["project_id"] for pr in result["pending_review"]] == ["P1"]


@pytest.mark.anyio
@pytest.mark.parametrize("metadata", [{"org_id": ["A", "B"]}, {"org_id": "A", "organization_id": "B"},
    {"org_id": "A", "team_id": ["T", "FOREIGN"]}])
async def test_ambiguous_project_provenance_never_grants_pr_visibility(mock_db, monkeypatch, metadata):
    from api.roles import lead
    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.project_repository.col", lambda name: mock_db[name])
    await mock_db.users.insert_one({"employee_id": "DEV", "org_id": "A", "team_id": "T", "github_username": "login"})
    await mock_db.projects.insert_one({"id": "P", "team_id": "T", **metadata})
    await mock_db.pull_requests.insert_one({"id": "PRIVATE", "project_id": "P", "author_login": "login", "status": "open", "review_status": "pending"})
    assert await PRRepository().find_by_employee("DEV") == []
    assert (await lead.review_queue(user={"role": "LEAD", "org_id": "A", "team_id": "T"}))["pending_review"] == []


@pytest.mark.anyio
async def test_pr_provenance_is_filtered_for_personal_team_and_project_reads(mock_db, monkeypatch):
    from api.roles import lead
    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.project_repository.col", lambda name: mock_db[name])
    await mock_db.users.insert_one({"employee_id": "DEV", "org_id": "A", "team_id": "T", "github_username": "login"})
    await mock_db.projects.insert_one({"id": "P", "org_id": "A", "team_id": "T"})
    for row in [{"id": "array", "project_id": ["P", "FOREIGN"]},
                {"id": "foreign", "project_id": "P", "organization_id": "B"},
                {"id": "ambiguous", "project_id": "P", "org_id": ["A", "B"]},
                {"id": "valid", "project_id": "P"}]:
        await mock_db.pull_requests.insert_one({"author_login": "login", "status": "open", "review_status": "pending", **row})
    repository = PRRepository()
    assert [p["id"] for p in await repository.find_by_employee("DEV")] == ["valid"]
    assert [p["id"] for p in await repository.find_by_project("P")] == ["valid"]
    result = await lead.review_queue(user={"role": "LEAD", "org_id": "A", "team_id": "T"})
    assert [p["id"] for p in result["pending_review"]] == ["valid"]


@pytest.mark.anyio
async def test_lead_queue_includes_explicitly_assigned_same_org_projects(mock_db, monkeypatch):
    from api.roles import lead
    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.project_repository.col", lambda name: mock_db[name])
    await mock_db.projects.insert_many([{"id": "ASSIGNED", "org_id": "A", "team_id": "OTHER"},
        {"id": "FOREIGN", "org_id": "B", "team_id": "OTHER"}])
    for project in ["ASSIGNED", "FOREIGN"]:
        await mock_db.pull_requests.insert_one({"id": project, "project_id": project, "status": "open", "review_status": "pending"})
    result = await lead.review_queue(user={"role": "LEAD", "org_id": "A", "team_id": "T", "project_ids": ["ASSIGNED", "FOREIGN"]})
    assert [p["id"] for p in result["pending_review"]] == ["ASSIGNED"]


@pytest.mark.anyio
async def test_identity_mapping_is_literal_and_inactive_accounts_are_denied(mock_db, monkeypatch):
    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    await mock_db.users.insert_one({"employee_id": "DEV", "org_id": "A", "project_ids": ["P"], "github_username": "dev.*"})
    await mock_db.projects.insert_one({"id": "P", "org_id": "A"})
    await mock_db.pull_requests.insert_many([{"id": "literal", "project_id": "P", "author_login": "DEV.*"},
        {"id": "wildcard", "project_id": "P", "author_login": "developer"}])
    assert [p["id"] for p in await PRRepository().find_by_employee("DEV")] == ["literal"]
    await mock_db.users.update_one({"employee_id": "DEV"}, {"$set": {"is_active": False}})
    assert await PRRepository().find_by_employee("DEV") == []


@pytest.mark.anyio
@pytest.mark.parametrize("role,expected", [("DEVELOPER", 200), ("LEAD", 200), ("QA", 200), ("PM", 403), ("HR", 403), ("LEGACY", 403)])
async def test_project_pr_visibility_preserves_established_role_permissions(mock_db, monkeypatch, role, expected):
    from core import database, authorization
    from core.security import create_access_token
    from domain.services.auth_service import AuthService
    from repositories.project_repository import ProjectRepository
    from api.routes import github
    from fastapi import FastAPI
    import httpx
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    await mock_db.projects.insert_many([{"id": "P", "org_id": "A"}, {"id": "FOREIGN", "org_id": "B"}])
    await mock_db.pull_requests.insert_one({"id": "visible", "project_id": "P"})
    account = {"employee_id": "ACTOR", "role": "DEVELOPER" if role == "LEGACY" else role,
        "org_id": None if role == "LEGACY" else "A", "project_ids": ["P", "FOREIGN"], "is_active": True}
    await mock_db.users.insert_one(account)
    headers = {"Authorization": "Bearer " + create_access_token(AuthService._token_payload(account))}
    app = FastAPI()
    app.include_router(github.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get('/projects/P/pull-requests', headers=headers)
        assert response.status_code == expected
        if expected == 200:
            assert [p["id"] for p in response.json()["pull_requests"]] == ["visible"]
        denied = await client.get('/projects/FOREIGN/pull-requests', headers=headers)
        assert denied.status_code == 403 and 'visible' not in denied.text
