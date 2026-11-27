from copy import deepcopy

import pytest
from fastapi import HTTPException

from core import authorization, database
from domain.services.release_decision_service import DecisionRequest, decision_context, record_decision
from domain.services.task_delivery_service import build_delivery_status
from repositories.project_repository import ProjectRepository


pytestmark = pytest.mark.anyio
TASK = "TSK-AB123456"
HEAD = "a" * 40
MERGE = "b" * 40
REPO = "example/service"
QA = {"employee_id": "qa", "role": "QA", "org_id": "A", "project_ids": ["P1"]}
OPS = {**QA, "employee_id": "ops", "role": "DEVOPS"}


@pytest.fixture
async def db(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    await mock_db.projects.insert_one({"id": "P1", "org_id": "A", "team_id": "team"})
    await mock_db.tasks.insert_one({"id": TASK, "project_id": "P1", "title": "Find best match", "status": "done"})
    await mock_db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "example", "repository_name": "service"})
    await mock_db.pull_requests.insert_one({"id": "pr1", "pr_number": 17, "project_id": "P1", "repo_id": REPO,
        "title": TASK + " search", "head_sha": HEAD, "merge_commit_sha": MERGE, "status": "merged"})
    await mock_db.qa_ci_configs.insert_one({"project_id": "P1", "repository": REPO, "enabled": True})
    return mock_db


def report(**fields):
    return {"id": "r1", "project_id": "P1", "organization_id": "A", "repository": REPO,
            "commit_sha": MERGE, "source": "github_actions", "workflow_run_id": "404", "run_attempt": 1,
            "ingestion_provenance": "project_ci_token", "test_suite": "acceptance", "status": "passed",
            "tests_run": 3, "tests_passed": 3, "tests_failed": 0, "tests_skipped": 0,
            "received_at": "2026-11-21T09:00:00Z", **fields}


def event(attempt, status="completed", conclusion="success", **fields):
    return {"project_id": "P1", "source": "github", "event_type": "workflow_run",
            "payload": {"repository": {"full_name": REPO}, "workflow_run": {
                "id": 404, "head_sha": MERGE, "run_attempt": attempt, "updated_at": "2026-11-21T10:00:00Z",
                "status": status, "conclusion": conclusion}}, **fields}


async def decide(action, user, expected_status):
    status = await build_delivery_status(TASK, user)
    assert status["qa"]["status"] == expected_status
    context = await decision_context(status, user)
    return await record_decision(status, user, DecisionRequest(
        decision=action, reason="Reviewed the feature checks", decision_version=context["decision_version"], revision=MERGE))


async def test_exact_revision_rerun_and_human_hold_lifecycle(db):
    await db.test_runs.insert_one(report(commit_sha=HEAD))
    status = await build_delivery_status(TASK, QA)
    assert status["revision"] == MERGE and status["revision_kind"] == "merge_commit"
    assert status["qa"]["status"] == status["production"]["status"] == "unknown"
    await db.test_runs.insert_one(report(id="merge1"))
    await decide("verify_qa", QA, "passed")
    assert (await decide("approve", OPS, "passed"))["release_decision"]["is_current"]
    await db.webhook_events.insert_one(event(2, status="in_progress", conclusion=None))
    status = await build_delivery_status(TASK, OPS)
    assert status["qa"]["status"] == "unknown"
    assert not (await decision_context(status, OPS))["release_decision"]["is_current"]
    await db.webhook_events.insert_one(event(2, conclusion="failure"))
    assert (await decide("hold", OPS, "failed"))["release_decision"]["decision"] == "hold"
    await db.webhook_events.insert_one(event(3))
    assert (await build_delivery_status(TASK, QA))["qa"]["status"] == "unknown"
    await db.test_runs.insert_one(report(id="merge3", run_attempt=3))
    status = await build_delivery_status(TASK, OPS)
    assert status["qa"]["status"] == "passed"
    assert not (await decision_context(status, OPS))["can_approve"]
    await db.tasks.update_one({"id": TASK}, {"$set": {"status": "blocked"}})
    status = await build_delivery_status(TASK, QA)
    assert status["readiness"]["status"] == "blocked"
    assert not (await decision_context(status, QA))["can_verify_qa"]


async def test_legacy_reports_remain_visible_but_require_an_authenticated_source(db):
    row = report()
    del row["ingestion_provenance"]
    await db.test_runs.insert_one(row.copy())
    qa = (await build_delivery_status(TASK, QA))["qa"]
    assert qa["status"] == "unknown" and qa["runs"][0]["provenance"] == "legacy_submission"
    artifact = {"repository": REPO, "commit_sha": MERGE, "workflow_run_id": 404, "run_attempt": 1,
                "artifact_id": 9, "artifact_sha256": "c" * 64, "verification_scope": "GITHUB_ARTIFACT_BYTES_AT_RUN"}
    await db.test_runs.insert_one({**row, "id": "verified", "test_suite": "reports/acceptance.xml",
                                   "artifact_provenance": artifact})
    qa = (await build_delivery_status(TASK, QA))["qa"]
    assert qa["status"] == "unknown" and "conclusion" in qa["reason"]
    await db.test_runs.update_one({"id": "verified"}, {"$set": {"artifact_provenance.workflow_conclusion": "failure"}})
    assert (await build_delivery_status(TASK, QA))["qa"]["status"] == "failed"
    await db.test_runs.update_one({"id": "verified"}, {"$set": {"artifact_provenance.workflow_conclusion": "success"}})
    # A successful artifact reporting a different suite cannot confer trust.
    assert (await build_delivery_status(TASK, QA))["qa"]["status"] == "unknown"
    await db.test_runs.update_one({"id": "verified"}, {"$set": {"test_suite": row["test_suite"]}})
    qa = (await build_delivery_status(TASK, QA))["qa"]
    assert qa["status"] == "passed" and {r["provenance"] for r in qa["runs"]} == {"legacy_submission", "github_artifact"}
    await db.test_runs.update_one({"id": "verified"}, {"$set": {"tests_run": 2, "tests_passed": 2}})
    assert (await build_delivery_status(TASK, QA))["qa"]["status"] == "unknown"
    await db.test_runs.update_one({"id": "verified"}, {"$set": {"artifact_provenance.commit_sha": HEAD}})
    assert (await build_delivery_status(TASK, QA))["qa"]["status"] == "unknown"


async def test_foreign_reports_events_and_identity_do_not_affect_review(db):
    await db.test_runs.insert_one(report())
    await db.test_runs.insert_one(report(id="foreign", organization_id="B", status="failed"))
    await db.webhook_events.insert_one(event(2, conclusion="failure", project_id="other"))
    assert (await build_delivery_status(TASK, QA))["qa"]["status"] == "passed"
    for user in ({**QA, "org_id": "B"}, {**OPS, "project_ids": []}, {**QA, "role": "HR"}):
        with pytest.raises(HTTPException) as exc:
            await build_delivery_status(TASK, user)
        assert exc.value.status_code in {403, 404}
    old = deepcopy(await db.pull_requests.find_one({"id": "pr1"}))
    old.pop("_id")
    await db.pull_requests.insert_one({**old, "id": "pr2", "pr_number": 18})
    status = await build_delivery_status(TASK, QA)
    assert status["implementation"]["status"] == "multiple" and status["revision"] is None
