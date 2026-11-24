"""Mounted release lifecycle tests with deterministic provider observations."""
import asyncio
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from core import authorization, database
from core.config import settings
from core.dependencies import get_current_user
from domain.services import release_management as service
from repositories.project_repository import ProjectRepository

pytestmark = pytest.mark.anyio
PROJECT = "P"
ORG = "O"
REPO = "pilot/service"
BASE, TARGET = "a" * 40, "b" * 40
ARTIFACT = {"id": 31, "digest": "d" * 64, "run_id": 21, "run_attempt": 1}
TASKS = [{"id": f"TSK-{i:08d}", "title": f"Task {i}", "status": "done"} for i in range(3)]
OPS = {"employee_id": "Ops", "role": "DEVOPS", "org_id": ORG, "project_ids": [PROJECT], "is_active": True}
QA = {**OPS, "employee_id": "QA", "role": "QA"}


@pytest.fixture
async def real_release_db():
    if os.environ.get("SAMANVAYA_RELEASE_TEST_MONGO") != "1":
        pytest.skip("Set SAMANVAYA_RELEASE_TEST_MONGO=1 for an isolated local MongoDB run.")
    name = "samanvaya_release_test_" + uuid4().hex
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    try:
        yield client[name]
    finally:
        await client.drop_database(name)
        client.close()


async def pilot(db, monkeypatch):
    from main import app
    from core.audit import audit_logger

    monkeypatch.setattr(database, "get_db", lambda: db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    monkeypatch.setattr(audit_logger, "collection", db.audit_logs)
    monkeypatch.setattr(settings, "RELEASE_MANAGEMENT_ENABLED", True)
    control = {"qa": "passed", "complete": True, "pr_count": 3}
    actor = dict(OPS)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: dict(actor))
    await db.projects.insert_one({"id": PROJECT, "org_id": ORG})
    await db.github_project_configs.insert_one({"project_id": PROJECT, "repository_owner": "pilot",
                                                 "repository_name": "service"})
    await db.tasks.insert_many([{**item, "project_id": PROJECT} for item in TASKS])
    await db.users.insert_many([dict(OPS), dict(QA)])
    await db.release_environments.insert_one({"_id": service.environment_key(PROJECT, ORG),
        "baseline": {"revision": BASE, "source": "devops_initialization", "repository_id": 1}})
    await service.ensure_indexes()

    async def identity(*args):
        return REPO, 1

    async def discovery(project, org, baseline, target, run_id=None, artifact_id=None):
        assert (project, org, baseline) == (PROJECT, ORG, BASE)
        return {"repository": REPO, "repository_id": 1, "commits": [target], "reverts": [],
                "complete": control["complete"], "scope_complete": control["complete"],
                "pull_requests": [{"number": i, "head_sha": "c" * 40} for i in range(control["pr_count"])],
                "tasks": TASKS, "blockers": [] if control["complete"] else ["Unmapped change"], "unmapped_commits": [],
                "artifact": ARTIFACT if run_id else None}

    async def reports(manifest):
        return {"qa": {"status": control["qa"], "reason": "Current combined report",
                       "runs": [{"test_suite": "acceptance/junit.xml", "tests_passed": 3}]},
                "coverage_status": "missing", "coverage": None}

    monkeypatch.setattr(service, "repository_identity", identity)
    monkeypatch.setattr(service, "discover", discovery)
    monkeypatch.setattr(service, "release_tests", reports)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), actor, control


async def prepare(client):
    root = f"/api/projects/{PROJECT}/releases"
    response = await client.post(root, json={"baseline_sha": BASE, "target_sha": TARGET, "run_id": 21, "artifact_id": 31})
    assert response.status_code == 201, response.text
    row = response.json()
    assert len(row["manifest"]["pull_requests"]) == len(row["manifest"]["tasks"]) == 3
    return f"{root}/{row['id']}", row


async def decision(client, path, row, action):
    return await client.post(path + "/actions", json={"action": action, "version": row["version"],
        "evidence_digest": row["evidence_digest"], "reason": "Reviewed the complete evidence.",
        **({"verified_task_ids": [t["id"] for t in TASKS]} if action == "verify_qa" else {})})


async def approved(client, actor):
    path, row = await prepare(client)
    submit = await decision(client, path, row, "submit")
    assert submit.status_code == 200, submit.text
    assert submit.json()["state"] == "awaiting_qa"
    actor.update(QA)
    deny = await decision(client, path, submit.json(), "approve")
    assert deny.status_code == 403
    missing = await client.post(path + "/actions", json={"action": "verify_qa", "version": submit.json()["version"],
        "evidence_digest": submit.json()["evidence_digest"], "reason": "Reviewed two tasks.",
        "verified_task_ids": [t["id"] for t in TASKS[:2]]})
    assert missing.status_code == 409 and missing.json()["detail"]["code"] == "QA_TASKS_INCOMPLETE"
    qa = await decision(client, path, submit.json(), "verify_qa")
    assert qa.status_code == 200, qa.text
    actor.update(OPS)
    approve = await decision(client, path, qa.json(), "approve")
    assert approve.status_code == 200, approve.text
    assert approve.json()["eligible"]
    return path, approve.json(), qa.json()


async def gate_client(client, row):
    issue = await client.post(f"/api/projects/{PROJECT}/release-gate", json={"action": "issue", "version": 0,
                                                                             "repository": REPO})
    assert issue.status_code == 200
    token = issue.json()["token"]
    request = {"project_id": PROJECT, "repository": REPO, "environment": "production", "revision": TARGET,
               "release_id": row["id"], "artifact_id": 31, "artifact_digest": ARTIFACT["digest"]}

    async def call(**updates):
        return await client.post("/api/release-gates/check", headers={"X-Release-Gate-Token": token},
                                 json={**request, **updates})
    return call


async def test_manifest_gate_denies_mismatch_scope_changes_and_late_failures(mock_db, monkeypatch):
    client, actor, control = await pilot(mock_db, monkeypatch)
    async with client:
        path, row, _ = await approved(client, actor)
        call = await gate_client(client, row)
        allow = await call()
        assert allow.status_code == 200 and allow.json()["allowed"]
        assert (await call(artifact_digest="f" * 64)).status_code == 409
        assert (await call(revision="f" * 40)).status_code == 409
        assert (await call(project_id="other")).status_code == 403
        control["pr_count"] = 4
        assert (await call()).json()["detail"]["code"] == "RELEASE_SCOPE_CHANGED"
        control["pr_count"] = 3
        control["qa"] = "failed"
        assert (await call()).status_code == 409
        control["qa"] = "passed"
        await mock_db.users.update_one({"employee_id": "QA"}, {"$set": {"is_active": False}})
        assert (await call()).status_code == 409
        await mock_db.users.update_one({"employee_id": "QA"}, {"$set": {"is_active": True}})
        await mock_db.tasks.update_one({"id": TASKS[-1]["id"]}, {"$set": {"last_transition_id": "reopened"}})
        assert (await call()).status_code == 409
        actor["org_id"] = "foreign"
        assert (await client.get(path)).status_code == 403


async def test_incomplete_manifest_requires_release_scope_and_test_evidence(mock_db, monkeypatch):
    client, actor, control = await pilot(mock_db, monkeypatch)
    async with client:
        control["complete"] = False
        path, row = await prepare(client)
        assert row["state"] == "evidence_incomplete"
        assert (await decision(client, path, row, "submit")).status_code == 409
        control["complete"] = True
        control["qa"] = "unknown"
        refreshed = await decision(client, path, row, "refresh")
        assert refreshed.status_code == 200
        assert refreshed.json()["evidence"]["coverage_status"] == "missing"
        assert (await decision(client, path, refreshed.json(), "submit")).status_code == 409
        req = type("Legacy", (), {"project_id": PROJECT, "revision": "e" * 40, "task_id": TASKS[0]["id"]})
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="MANIFEST_REQUIRED"):
            await service.check_legacy_scope(req, ORG, 0)


async def test_real_mongo_elects_one_successor_and_keeps_audit_after_reopen(real_release_db, monkeypatch):
    client, actor, _ = await pilot(real_release_db, monkeypatch)
    async with client:
        path, row, qa = await approved(client, actor)
        outcomes = await asyncio.gather(decision(client, path, row, "hold"), decision(client, path, row, "supersede"))
        assert sorted(r.status_code for r in outcomes) == [200, 409]
        logs = (await client.get(path + "/history")).json()["history"]
        assert [item["version"] for item in logs] == [5, 4, 3, 2, 1]
        fresh = AsyncClient(transport=ASGITransport(app=client._transport.app), base_url="http://test")
        async with fresh:
            view = (await fresh.get(path)).json()
            assert view["version"] == 5 and not view["eligible"]


async def test_observation_requires_matching_repository_environment_and_artifact(mock_db, monkeypatch):
    client, actor, _ = await pilot(mock_db, monkeypatch)
    async with client:
        path, row, _ = await approved(client, actor)
        check = await gate_client(client, row)
        assert (await check()).status_code == 200
        assert (await client.get(path)).json()["deployment"]["status"] == "unknown"

        async def observe(state, when, digest, environment="production", status_id=1):
            await mock_db.webhook_events.insert_one({
                "source": "github", "event_type": "deployment_status", "project_id": PROJECT,
                "production": {"org_id": ORG, "repository": REPO, "observed_at": when, "revision": TARGET,
                               "status_id": status_id, "state": state, "deployment_id": 3},
                "payload": {"repository": {"id": 1}, "deployment": {"environment": environment, "payload": {
                    "samanvaya_release_id": row["id"], "manifest_digest": row["manifest_digest"], "artifact_id": 31,
                    "artifact_digest": digest}}},
            })

        await observe("success", "2040-01-01T12:00:00+00:00", "f" * 64, environment="staging")
        assert (await client.get(path)).json()["deployment"]["status"] == "unknown"
        await observe("success", "2040-01-01T12:00:00+00:00", ARTIFACT["digest"], status_id=2)
        await observe("failure", "2040-01-01T11:00:00+00:00", ARTIFACT["digest"])
        assert (await client.get(path)).json()["state"] == "deployed"
        assert (await check()).status_code == 409
