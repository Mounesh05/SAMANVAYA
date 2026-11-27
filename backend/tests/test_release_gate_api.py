"""Machine release checks on the application's normal API registrations."""
import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from core import authorization, database
from core.ci_credentials import project_ci_token
from core.dependencies import get_current_user
from domain.services.workflow_service import WorkflowService
from repositories.project_repository import ProjectRepository


pytestmark = pytest.mark.anyio
TOKEN = "isolated-production-release-credential"
TASK = "TSK-1234ABCD"
REPO = "pilot/service"
HEAD = "a" * 40
MERGE = "b" * 40
REQUEST = {"project_id": "P", "task_id": TASK, "repository": REPO, "revision": MERGE, "environment": "production"}
GATE = "/api/release-gates/check"


@pytest.fixture
async def pilot(mock_db, monkeypatch):
    from main import app

    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    actor = {"employee_id": "qa", "role": "QA", "org_id": "A", "project_ids": ["P"]}
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: dict(actor))
    await mock_db.project_release_gates.insert_one({"_id": "P", "organization_id": "A", "repository": REPO,
        "environment": "production", "enabled": True, "token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest()})
    await mock_db.projects.insert_one({"id": "P", "org_id": "A"})
    await mock_db.tasks.insert_one({"id": TASK, "project_id": "P", "title": "Support search", "status": "done"})
    await mock_db.github_project_configs.insert_one({"project_id": "P", "repository_owner": "pilot", "repository_name": "service"})
    await mock_db.qa_ci_configs.insert_one({"project_id": "P", "repository": REPO, "enabled": True})
    await mock_db.pull_requests.insert_one({"id": "pr", "pr_number": 3, "title": TASK, "repo_id": REPO,
        "status": "merged", "head_sha": HEAD, "merge_commit_sha": MERGE, "project_id": "P"})
    await mock_db.test_runs.insert_one({"id": "report", "project_id": "P", "repository": REPO,
        "commit_sha": MERGE, "source": "github_actions", "workflow_run_id": "15", "run_attempt": 1,
        "tests_run": 1, "tests_passed": 1, "tests_failed": 0, "tests_skipped": 0, "status": "passed",
        "test_suite": "acceptance", "received_at": "2026-01-01T10:00:00Z", "ingestion_provenance": "project_ci_token"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://fixture") as client:
        yield mock_db, client, actor


async def check(client, token=TOKEN, **changes):
    headers = {"X-Release-Gate-Token": token} if token else {}
    return await client.post(GATE, headers=headers, json={**REQUEST, **changes})


async def decide(client, actor, action):
    is_qa = action == "verify_qa"
    actor.update(employee_id="qa" if is_qa else "ops", role="QA" if is_qa else "DEVOPS")
    path = f"/api/tasks/{TASK}"
    delivery = await client.get(path + "/delivery")
    payload = {"decision": action, "reason": "Reviewed exact release evidence", "revision": MERGE,
               "decision_version": delivery.json()["decision_version"]}
    result = await client.post(path + "/release-decisions", json=payload)
    assert result.status_code == 200, result.text


async def test_gate_tracks_humans_and_changes_without_writing(pilot):
    db, client, actor = pilot
    assert (await check(client)).status_code == 409
    await decide(client, actor, "verify_qa")
    assert (await check(client)).status_code == 409
    await decide(client, actor, "approve")
    actor.clear()  # No interactive user is required to check the signed-off task.
    approved = await check(client)
    assert approved.status_code == 200, approved.text
    assert approved.json() == {"allowed": True, **REQUEST}
    assert approved.headers["cache-control"] == "no-store"
    assert (await check(client, revision=HEAD)).status_code == 409
    assert (await check(client, task_id="TSK-12345678")).status_code == 409
    assert await db.release_decisions.count_documents({}) == 2
    assert await db.webhook_events.count_documents({}) == 0

    # Recorded evidence changes at the same SHA must render both decisions stale.
    await db.test_runs.update_one({"id": "report"}, {"$set": {"run_attempt": 2}})
    assert (await check(client)).status_code == 409
    actor.update(org_id="A", project_ids=["P"])
    await decide(client, actor, "verify_qa")
    await decide(client, actor, "approve")
    await decide(client, actor, "hold")
    held = await check(client)
    assert held.status_code == 409 and held.headers["cache-control"] == "no-store"


async def test_machine_credential_is_dedicated_scoped_and_revocable(pilot):
    db, client, _ = pilot
    for token in (None, "invalid", project_ci_token("P", REPO)):
        response = await check(client, token)
        assert response.status_code == 403 and response.headers["cache-control"] == "no-store"
    assert (await check(client, project_id="OTHER")).status_code == 403
    assert (await check(client, repository="other/service")).status_code == 403
    assert (await check(client, environment="staging")).status_code == 422
    assert (await check(client, revision="main")).status_code == 422
    await db.project_release_gates.update_one({"_id": "P"}, {"$set": {"enabled": False}})
    assert (await check(client)).status_code == 403
    await db.project_release_gates.update_one({"_id": "P"}, {"$set": {"enabled": True, "token_sha256": "0" * 64}})
    assert (await check(client)).status_code == 403


@pytest.mark.parametrize("ambiguity", ["sibling_title", "sibling_edge", "other_pr", "other_project", "foreign_org", "blocked"])
async def test_gate_requires_one_current_project_task_and_merged_revision(pilot, ambiguity):
    db, client, actor = pilot
    await decide(client, actor, "verify_qa")
    await decide(client, actor, "approve")
    if ambiguity == "sibling_title":
        await db.pull_requests.update_one({"id": "pr"}, {"$set": {"description": "Also implements TSK-DEADBEEF"}})
    elif ambiguity == "sibling_edge":
        await db.entity_relationships.insert_one({"source_type": "pull_request", "source_id": "pr",
            "relationship_type": "implements", "target_type": "task", "target_id": "TSK-DEADBEEF"})
    elif ambiguity == "other_pr":
        await db.pull_requests.insert_one({"id": "pr2", "pr_number": 5, "title": "other task", "repo_id": REPO,
            "status": "merged", "merge_commit_sha": MERGE, "project_id": "P"})
    elif ambiguity == "other_project":
        await db.github_project_configs.insert_one({"project_id": "Q", "repository_owner": "PILOT", "repository_name": "SERVICE"})
    elif ambiguity == "foreign_org":
        await db.projects.update_one({"id": "P"}, {"$set": {"org_id": "B"}})
    else:
        await db.tasks.update_one({"id": TASK}, {"$set": {"status": "blocked"}})
    assert (await check(client)).status_code == 409


async def test_legacy_suite_cannot_borrow_another_suites_trust(pilot):
    db, client, actor = pilot
    await decide(client, actor, "verify_qa")
    await decide(client, actor, "approve")
    legacy = await db.test_runs.find_one({"id": "report"}, {"_id": 0})
    await db.test_runs.insert_one({**legacy, "id": "legacy", "test_suite": "integration", "ingestion_provenance": "legacy_submission"})
    readout = (await client.get(f"/api/tasks/{TASK}/delivery")).json()
    assert readout["qa"]["status"] == "unknown" and "legacy" in readout["qa"]["reason"]
    assert not readout["can_approve"] and not readout["release_decision"]["is_current"]
    result = await check(client)
    assert result.status_code == 409


async def test_partial_rerun_needs_current_reports_for_each_observed_suite(pilot):
    db, client, actor = pilot
    original = await db.test_runs.find_one({"id": "report"}, {"_id": 0})
    integration = {**original, "id": "integration", "test_suite": "integration"}
    await db.test_runs.insert_one(integration.copy())
    await decide(client, actor, "verify_qa")
    await decide(client, actor, "approve")

    await db.test_runs.insert_one({**original, "id": "report-2", "run_attempt": 2})
    current = (await client.get(f"/api/tasks/{TASK}/delivery")).json()
    assert current["qa"]["status"] == "unknown" and "attempt" in current["qa"]["reason"]
    assert not current["can_approve"]
    assert (await check(client)).status_code == 409

    await db.test_runs.insert_one({**integration, "id": "integration-2", "run_attempt": 2})
    await decide(client, actor, "verify_qa")
    await decide(client, actor, "approve")
    assert (await check(client)).status_code == 200


async def test_reopening_then_closing_requires_new_qa_and_release_decisions(pilot):
    db, client, actor = pilot
    await decide(client, actor, "verify_qa")
    await decide(client, actor, "approve")
    await db.tasks.update_one({"id": TASK}, {"$set": {"due_date": "2026-12-01"}})
    assert (await check(client)).status_code == 200

    workflow = WorkflowService()
    for new_status in ("in_progress", "review", "done"):
        await workflow.transition_task(TASK, new_status, "lead", "Team Lead")
        latest = (await client.get(f"/api/tasks/{TASK}/delivery")).json()
        assert not latest["qa_verification"]["is_current"]
        assert not latest["release_decision"]["is_current"]
        assert (await check(client)).status_code == 409

    await decide(client, actor, "verify_qa")
    assert (await check(client)).status_code == 409
    await decide(client, actor, "approve")
    assert (await check(client)).status_code == 200


async def test_legacy_reopening_history_is_limited_to_the_project_and_tenant(pilot):
    db, client, actor = pilot
    await decide(client, actor, "verify_qa")
    await decide(client, actor, "approve")
    history = {"item_id": TASK, "item_type": "task", "event_type": "status_changed",
               "details": {"from_status": "done", "to_status": "in_progress"}, "created_at": "2026-01-02T10:00:00Z"}
    await db.activities.insert_one({**history, "project_id": "Q"})
    await db.activities.insert_one({**history, "project_id": "P", "org_id": "B"})
    assert (await check(client)).status_code == 200
    await db.activities.insert_one({**history, "project_id": "P"})
    assert (await check(client)).status_code == 409
