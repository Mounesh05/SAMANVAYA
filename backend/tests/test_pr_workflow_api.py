"""Versioned manual API boundaries and controlled worker lifecycle."""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

import test_pr_workflow_durability as durability_tests
import test_pr_workflow_durability_mongo as mongo_tests
from test_pr_multi_agent import add_qa
from api.routes import pr_workflows
from core.config import settings
from core.dependencies import get_current_user
from core.security import create_access_token, decode_token, revoke_token
from domain.services.auth_service import AuthService
from domain.services.pr_workflow_runtime import PRWorkflowRuntime

durable = durability_tests.durable
setup = durability_tests.setup
real = mongo_tests.real
pytestmark = pytest.mark.anyio
ROOT = "/api/ai/workflows/v1"


@pytest.fixture
async def endpoint(durable, monkeypatch):
    monkeypatch.setattr(settings, "PR_MULTI_AGENT_MANUAL_ENABLED", True)
    runtime = PRWorkflowRuntime(service_factory=lambda: durable[-1])
    async def paused():
        await asyncio.Event().wait()
    monkeypatch.setattr(runtime, "_loop", paused)
    await runtime.start()
    app = FastAPI()
    app.state.pr_workflow_runtime = runtime
    app.include_router(pr_workflows.router, prefix=ROOT)
    actor = {"employee_id": "A", "role": "LEAD"}
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client, durable, actor, runtime, app
    finally:
        await runtime.stop()


async def start(client, **fields):
    return await client.post(ROOT + "/pr-analysis", json={"project_id": "P1", "pr_number": 7, **fields})


async def test_start_is_accepted_idempotent_and_status_is_redacted(endpoint):
    client, durable, _, _, _ = endpoint
    first, second = await start(client), await start(client)
    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    key = first.json()["job_id"]
    status = await client.get(ROOT + f"/jobs/{key}")
    assert status.status_code == 200 and status.json()["schema_version"] == "pr-workflow-status-v1"
    assert status.json()["status"] == "PENDING" and not status.json()["report_available"]
    assert status.json()["head_sha"] == "a" * 40 and status.json()["repository"] == "owner/repo"
    assert not {"snapshot", "step_results", "worker_id", "generation", "lease_expires_at"} & status.json().keys()
    assert not durable[3]  # Accepting a request does not execute specialists in that request.
    assert (await client.get(ROOT + f"/jobs/{key}/report")).status_code == 409


async def test_report_preserves_single_specialist_partial_and_advisory_authority(endpoint):
    client, durable, _, _, _ = endpoint
    key = (await start(client)).json()["job_id"]
    await durable[-1].execute(key)
    status = (await client.get(ROOT + f"/jobs/{key}")).json()
    assert status["report_available"] and status["analysis_status"] == "PARTIAL_SINGLE_SPECIALIST_ADVISORY"
    assert [step["status"] for step in status["specialists"]] == ["SUCCEEDED", "SKIPPED"]
    report = await client.get(ROOT + f"/jobs/{key}/report")
    assert report.status_code == 200
    assert report.json()["schema_version"] == "pr-multi-agent-report-v2"
    assert report.json()["collaboration"] == "SINGLE_SPECIALIST" and report.json()["read_only"]
    assert report.json()["authoritative_score"] is None


async def test_exact_advisory_lookup_is_owner_scoped_and_never_starts_a_job(endpoint):
    client, durable, actor, _, _ = endpoint
    db, api = durable[:2]
    head = "a" * 40
    await db.pull_requests.insert_one({"id": "pr7", "project_id": "P1", "repo_id": "owner/repo",
                                       "pr_number": 7, "head_sha": head, "merge_commit_sha": "b" * 40})
    params = {"project_id": "P1", "repository": "owner/repo", "pr_number": 7, "head_sha": head}
    path = ROOT + "/pr-analysis/report"
    missing = await client.get(path, params=params)
    assert missing.status_code == 200 and missing.json() is None
    assert await db.pr_multi_agent_jobs.count_documents({}) == 0
    assert not api.client.get_pull_request.called and not durable[3]
    key = (await start(client)).json()["job_id"]
    assert (await client.get(path, params=params)).json() is None
    await durable[-1].execute(key)
    calls = api.client.get_pull_request.call_count
    report = await client.get(path, params=params)
    assert report.status_code == 200 and report.headers["cache-control"] == "no-store"
    assert report.json()["job_id"] == key and report.json()["scope"]["head_sha"] == head
    assert report.json()["authoritative_score"] is None
    assert (await client.get(path, params={**params, "head_sha": "b" * 40})).status_code == 409
    assert (await client.get(path, params={**params, "repository": "other/repo"})).status_code == 409
    assert (await client.get(path, params={**params, "project_id": "P2"})).status_code == 404
    await db.users.insert_one({"employee_id": "B", "role": "LEAD", "org_id": "O1", "project_ids": ["P1"]})
    actor["employee_id"] = "B"
    assert (await client.get(path, params=params)).json() is None
    await db.users.update_one({"employee_id": "B"}, {"$set": {"role": "DEVELOPER"}})
    assert (await client.get(path, params=params)).status_code == 403
    actor["employee_id"] = "A"
    await db.pull_requests.update_one({"id": "pr7"}, {"$set": {"head_sha": "f" * 40}})
    assert (await client.get(path, params=params)).status_code == 409
    assert api.client.get_pull_request.call_count == calls
    assert await db.pr_multi_agent_jobs.count_documents({}) == 1


async def test_advisory_lookup_refuses_ambiguous_comparison_bases(endpoint):
    client, durable, _, _, _ = endpoint
    db, api = durable[:2]
    await db.pull_requests.insert_one({"project_id": "P1", "repo_id": "owner/repo", "pr_number": 7, "head_sha": "a" * 40})
    await start(client)
    api.client.get_pull_request.return_value["base"]["sha"] = "f" * 40
    await start(client)
    response = await client.get(ROOT + "/pr-analysis/report", params={
        "project_id": "P1", "repository": "owner/repo", "pr_number": 7, "head_sha": "a" * 40})
    assert response.status_code == 409 and "base revisions" in response.json()["detail"]
    assert not durable[3]


@pytest.mark.parametrize("extra", [{"evidence": {"status": "SERVER_VERIFIED"}}, {"repository": "foreign/repo"},
                                   {"owner_id": "B"}, {"organization_id": "O2"}, {"score": 100}])
async def test_client_authority_and_evidence_fields_are_rejected(endpoint, extra):
    client, durable, _, _, _ = endpoint
    assert (await start(client, **extra)).status_code == 422
    assert await durable[0].pr_multi_agent_jobs.count_documents({}) == 0


@pytest.mark.parametrize("change", [{"role": "HR", "is_admin": True}, {"role": "DEVELOPER"},
                                     {"org_id": "O2"}, {"project_ids": []}, {"is_active": False}])
async def test_current_permissions_and_scope_are_rechecked_on_every_api_operation(endpoint, change):
    client, durable, _, _, _ = endpoint
    key = (await start(client)).json()["job_id"]
    await durable[-1].execute(key)
    await durable[0].users.update_one({"employee_id": "A"}, {"$set": change})
    for response in (await start(client), await client.get(ROOT + f"/jobs/{key}"), await client.get(ROOT + f"/jobs/{key}/report")):
        assert response.status_code in {403, 404}
        assert "supported_conclusion" not in response.text and "snapshot" not in response.text


async def test_cross_user_and_cross_project_access_are_denied(endpoint):
    client, durable, actor, _, _ = endpoint
    key = (await start(client)).json()["job_id"]
    assert (await start(client, project_id="P2")).status_code == 404
    await durable[0].users.insert_one({"employee_id": "B", "role": "LEAD", "org_id": "O1", "project_ids": ["P1"]})
    actor["employee_id"] = "B"
    assert (await client.get(ROOT + f"/jobs/{key}")).status_code == 404
    assert (await client.get(ROOT + f"/jobs/{key}/report")).status_code == 404


@pytest.mark.parametrize("flag", ["PR_MULTI_AGENT_INTERNAL_ENABLED", "PR_MULTI_AGENT_MANUAL_ENABLED", "production"])
async def test_disabled_and_production_gates_reject_all_endpoints_without_new_work(endpoint, monkeypatch, flag):
    client, durable, _, _, _ = endpoint
    key = (await start(client)).json()["job_id"]
    if flag == "production":
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    else:
        monkeypatch.setattr(settings, flag, False)
    assert (await start(client)).status_code == 404
    assert (await client.get(ROOT + f"/jobs/{key}")).status_code == 404
    assert (await client.get(ROOT + f"/jobs/{key}/report")).status_code == 404
    assert (await client.get(ROOT + "/pr-analysis/report", params={"project_id": "P1", "repository": "owner/repo",
                  "pr_number": 7, "head_sha": "a" * 40})).status_code == 404
    assert not durable[3]


async def test_authentication_is_required_and_stopped_worker_cannot_accept_work(endpoint):
    client, _, _, runtime, app = endpoint
    app.dependency_overrides.clear()
    assert (await start(client)).status_code in {401, 422}
    assert (await client.get(ROOT + "/jobs/" + "a" * 64)).status_code in {401, 422}
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "A"}
    await runtime.stop()
    assert (await start(client)).status_code == 503


async def test_historical_report_access_does_not_rewrite_the_original_revision(endpoint):
    client, durable, _, _, _ = endpoint
    key = (await start(client)).json()["job_id"]
    await durable[-1].execute(key)
    before = (await client.get(ROOT + f"/jobs/{key}/report")).json()
    durable[1].client.get_pull_request.return_value["head"]["sha"] = "f" * 40
    assert (await client.get(ROOT + f"/jobs/{key}/report")).json() == before


async def test_runtime_is_single_owned_worker_and_recovers_pending_jobs(durable, monkeypatch):
    monkeypatch.setattr(settings, "PR_MULTI_AGENT_MANUAL_ENABLED", True)
    await add_qa(durable[0])
    job = await durable[-1].start({"project_id": "P1", "pr_number": 7}, {"employee_id": "A"})
    runtime = PRWorkflowRuntime(service_factory=lambda: durable[-1])
    runtime.poll_seconds = 0.01
    await runtime.start()
    task = runtime._task
    await runtime.start()
    assert runtime._task is task
    try:
        async with asyncio.timeout(5):
            while (await durable[-1].get(job["job_id"], {"employee_id": "A"}))["status"] != "FINALIZED":
                await asyncio.sleep(0.01)
        assert len(durable[3]) == 2
    finally:
        await runtime.stop()
    assert task.done() and not runtime.running


async def test_off_runtime_does_not_construct_a_service_or_touch_mongo(monkeypatch):
    monkeypatch.setattr(settings, "PR_MULTI_AGENT_MANUAL_ENABLED", False)
    def forbidden():
        raise AssertionError("Disabled runtime constructed service")
    runtime = PRWorkflowRuntime(service_factory=forbidden)
    await runtime.start()
    assert not runtime.running
    await runtime.stop()


async def test_project_choices_use_server_tenant_and_membership_not_client_org(endpoint):
    client, durable, _, _, _ = endpoint
    await durable[0].projects.insert_one({"id": "P3", "org_id": "O1", "name": "Unassigned project"})
    response = await client.get(ROOT + "/projects", params={"org_id": "O2"})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["projects"]] == ["P1"]
    await durable[0].users.update_one({"employee_id": "A"}, {"$set": {"role": "HR", "is_admin": True}})
    assert (await client.get(ROOT + "/projects")).status_code == 403


async def test_real_jwt_refreshes_authority_and_logout_prevents_manual_reads(endpoint):
    client, durable, _, _, app = endpoint
    account = await durable[0].users.find_one({"employee_id": "A"})
    token = create_access_token(AuthService._token_payload(account))
    app.dependency_overrides.clear()
    client.headers["Authorization"] = "Bearer " + token
    key = (await start(client)).json()["job_id"]
    assert (await client.get(ROOT + f"/jobs/{key}")).status_code == 200
    await durable[0].users.update_one({"employee_id": "A"}, {"$set": {"project_ids": []}})
    assert (await client.get(ROOT + f"/jobs/{key}")).status_code == 404
    await durable[0].users.update_one({"employee_id": "A"}, {"$set": {"project_ids": ["P1"]}})
    claims = decode_token(token)
    await revoke_token(claims["jti"], datetime.fromtimestamp(claims["exp"], timezone.utc))
    assert (await client.get(ROOT + f"/jobs/{key}/report")).status_code == 401


async def test_api_intake_is_bounded_and_does_not_create_background_tasks(endpoint, monkeypatch):
    client, durable, _, _, _ = endpoint
    began, finish = asyncio.Event(), asyncio.Event()
    original = durable[-1].start
    async def held(*args):
        began.set()
        await finish.wait()
        return await original(*args)
    monkeypatch.setattr(durable[-1], "start", held)
    first = asyncio.create_task(start(client))
    await asyncio.wait_for(began.wait(), 5)
    try:
        assert (await start(client)).status_code == 429
    finally:
        finish.set()
    assert (await first).status_code == 202
    assert await durable[0].pr_multi_agent_jobs.count_documents({}) == 1 and not durable[3]


async def test_runtime_shutdown_retains_checkpoint_and_restart_resumes(durable, monkeypatch):
    monkeypatch.setattr(settings, "PR_MULTI_AGENT_MANUAL_ENABLED", True)
    await add_qa(durable[0])
    service = durable[-1]
    job = await service.start({"project_id": "P1", "pr_number": 7}, {"employee_id": "A"})
    entered = asyncio.Event()
    async def held(view):
        entered.set()
        await asyncio.Event().wait()
    original = durable[2].qa_specialist
    durable[2].qa_specialist = held
    first = PRWorkflowRuntime(service_factory=lambda: service)
    await first.start()
    try:
        await asyncio.wait_for(entered.wait(), 5)
    finally:
        await first.stop()
    record = await service.get(job["job_id"], {"employee_id": "A"})
    assert record["status"] == "RUNNING" and len(record["step_results"]) == 1 and "report" not in record
    durable[4].advance()
    durable[2].qa_specialist = original
    second = PRWorkflowRuntime(service_factory=lambda: service)
    second.poll_seconds = 0.01
    await second.start()
    try:
        async with asyncio.timeout(5):
            while (await service.get(job["job_id"], {"employee_id": "A"}))["status"] != "FINALIZED":
                await asyncio.sleep(0.01)
    finally:
        await second.stop()
    assert [view.specialist for view in durable[3]] == ["code_analysis", "qa_analysis"]


async def test_runtime_poll_errors_are_retried_with_one_owned_task(durable, monkeypatch):
    monkeypatch.setattr(settings, "PR_MULTI_AGENT_MANUAL_ENABLED", True)
    original = durable[-1].run_ready
    calls = []
    async def flaky(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ConnectionError("unavailable")
        return await original(**kwargs)
    monkeypatch.setattr(durable[-1], "run_ready", flaky)
    runtime = PRWorkflowRuntime(service_factory=lambda: durable[-1])
    runtime.poll_seconds = 0.01
    await asyncio.gather(runtime.start(), runtime.start())
    try:
        async with asyncio.timeout(5):
            while len(calls) < 2:
                await asyncio.sleep(0.01)
        assert runtime.running and all(row == {"limit": 1} for row in calls)
    finally:
        await runtime.stop()


async def test_lifespan_stops_manual_worker_before_closing_database(monkeypatch):
    import main
    from api.routes.webhooks import event_processor
    from core import security
    from domain.services.hitl_workflow_service import hitl_service
    from intelligence.baselines.repository_baseline import RepositoryBaseline
    from repositories.qa_repository import QARepository
    from domain.services import pr_workflow_runtime
    order = []
    class Runtime:
        async def start(self): order.append("manual-start")
        async def stop(self): order.append("manual-stop")
    monkeypatch.setattr(pr_workflow_runtime, "PRWorkflowRuntime", Runtime)
    monkeypatch.setattr(RepositoryBaseline, "ensure_index", AsyncMock())
    monkeypatch.setattr(hitl_service, "_ensure_indexes", AsyncMock())
    monkeypatch.setattr(QARepository, "ensure_indexes", AsyncMock())
    monkeypatch.setattr(security, "ensure_revocation_indexes", AsyncMock())
    async def start_webhook(): order.append("webhook-start")
    async def stop_webhook(): order.append("webhook-stop")
    async def close(): order.append("database-close")
    monkeypatch.setattr(event_processor, "start", start_webhook)
    monkeypatch.setattr(event_processor, "stop", stop_webhook)
    monkeypatch.setattr(main, "close_db", close)
    async with main.lifespan(main.app):
        assert isinstance(main.app.state.pr_workflow_runtime, Runtime)
    assert order == ["webhook-start", "manual-start", "manual-stop", "webhook-stop", "database-close"]


async def test_duplicate_after_publication_returns_existing_job_and_immutable_report(endpoint):
    client, durable, _, _, _ = endpoint
    key = (await start(client)).json()["job_id"]
    await durable[-1].execute(key)
    original = (await client.get(ROOT + f"/jobs/{key}/report")).json()
    response = await start(client)
    assert response.status_code == 202 and response.json()["job_id"] == key and response.json()["status"] == "FINALIZED"
    assert (await client.get(ROOT + f"/jobs/{key}/report")).json() == original


async def test_project_choice_limit_follows_authorization_filtering(endpoint):
    client, durable, _, _, _ = endpoint
    ids = [f"PX-{number:03}" for number in range(110)]
    await durable[0].projects.insert_many([{"id": key, "org_id": "O1"} for key in ids])
    await durable[0].users.update_one({"employee_id": "A"}, {"$set": {"project_ids": ids}})
    result = await client.get(ROOT + "/projects")
    assert result.status_code == 200 and result.json()["truncated"]
    assert len(result.json()["projects"]) == 100
    assert all(project["id"].startswith("PX-") for project in result.json()["projects"])


@pytest.mark.skipif(os.getenv("SAMANVAYA_MONGO_TESTS") != "1", reason="Opt-in real Mongo manual API execution")
async def test_real_mongo_api_submission_progresses_through_owned_runtime(real, monkeypatch):
    monkeypatch.setattr(settings, "PR_MULTI_AGENT_MANUAL_ENABLED", True)
    db, _, calls, repo, service, _ = real
    await add_qa(db)
    runtime = PRWorkflowRuntime(service_factory=lambda: service)
    runtime.poll_seconds = 0.01
    app = FastAPI()
    app.state.pr_workflow_runtime = runtime
    app.include_router(pr_workflows.router, prefix=ROOT)
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "A"}
    await runtime.start()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await start(client)
            assert response.status_code == 202
            key = response.json()["job_id"]
            async with asyncio.timeout(5):
                while True:
                    status = await client.get(ROOT + f"/jobs/{key}")
                    assert status.status_code == 200
                    if status.json()["report_available"]:
                        break
                    await asyncio.sleep(0.01)
            report = await client.get(ROOT + f"/jobs/{key}/report")
            assert report.status_code == 200 and report.json()["collaboration"] == "TWO_SPECIALIST"
            assert len(calls) == 2 and await repo.collection.count_documents({"report": {"$exists": True}}) == 1
    finally:
        await runtime.stop()
