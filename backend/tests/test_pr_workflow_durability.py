"""Lease fencing, crash recovery and authorization of the internal durable workflow."""

import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockCollection
from pymongo.errors import AutoReconnect

import test_pr_multi_agent as workflow_tests
from test_pr_multi_agent import add_qa, reply
from domain.services.pr_workflow_durable import DurablePRWorkflowService
from repositories.pr_workflow_repository import PRWorkflowRepository, LeaseLost

pytestmark = pytest.mark.anyio
setup = workflow_tests.setup


class Clock:
    def __init__(self):
        self.value = datetime(2026, 11, 13)

    def __call__(self):
        return self.value

    def advance(self, seconds=100):
        self.value += timedelta(seconds=seconds)


@pytest.fixture
async def durable(setup, monkeypatch):
    db, api, manual, calls = setup
    # Installed mongomock_motor delegates with_options to a synchronous collection.
    # Restore only its missing async wrapper in tests; production Motor is unchanged.
    def with_options(collection, **options):
        delegate = AsyncMongoMockCollection.__getattr__(collection, "with_options")(**options)
        return AsyncMongoMockCollection(collection.database, delegate)
    monkeypatch.setattr(AsyncMongoMockCollection, "with_options", with_options, raising=False)
    clock = Clock()
    repo = PRWorkflowRepository(db.pr_multi_agent_jobs, clock=clock)
    service = DurablePRWorkflowService(manual=manual, repository=repo)
    return db, api, manual, calls, clock, repo, service


async def start(service, user="A"):
    return await service.start({"project_id": "P1", "pr_number": 7}, {"employee_id": user})


async def test_duplicate_start_races_preserve_one_immutable_snapshot(durable):
    db, _, _, _, _, _, service = durable
    jobs = await asyncio.gather(*(start(service) for _ in range(8)))
    assert len({job["job_id"] for job in jobs}) == 1
    assert await db.pr_multi_agent_jobs.count_documents({}) == 1
    original = await service.get(jobs[0]["job_id"], {"employee_id": "A"})
    await add_qa(db)
    again = await start(service)
    current = await service.get(again["job_id"], {"employee_id": "A"})
    assert current["snapshot"] == original["snapshot"] and current["snapshot_id"] == original["snapshot_id"]


async def test_atomic_claim_race_and_monotonic_generation(durable):
    _, _, _, _, clock, repo, service = durable
    job = await start(service)
    claims = await asyncio.gather(*(repo.claim(job["job_id"], f"worker-{i}") for i in range(12)))
    claimed = [claim for claim in claims if claim is not None]
    assert len(claimed) == 1 and claimed[0].generation == 1
    clock.advance()
    newer = await repo.claim(job["job_id"], "new-process")
    assert newer.generation == 2
    with pytest.raises(LeaseLost):
        await repo.read_owned(claimed[0])
    assert not await repo.renew(claimed[0])


async def test_real_graph_persists_versioned_final_report_and_is_idempotent(durable):
    db, _, _, calls, _, repo, service = durable
    await add_qa(db)
    job = await start(service)
    await service.execute(job["job_id"])
    stored = await service.get(job["job_id"], {"employee_id": "A"})
    assert stored["status"] == "FINALIZED" and stored["analysis_status"] == "COLLABORATIVE_ADVISORY"
    assert stored["schema_version"] == "pr-workflow-job-v1"
    assert stored["checkpoint"]["schema_version"] == "pr-workflow-checkpoint-v1"
    assert len(stored["step_results"]) == 2
    assert all(step["schema_version"] == "pr-workflow-step-v1" for step in stored["step_results"])
    report = stored["report"]
    assert report["schema_version"] == "pr-multi-agent-report-v2" and report["durable"] is True
    assert report["snapshot"]["snapshot_id"] == stored["snapshot_id"] and report["authoritative_score"] is None
    assert report["scope"]["owner_id"] == "A" and report["scope"]["head_sha"] == "a" * 40
    assert len(calls) == 2
    assert await repo.claim(job["job_id"], "another") is None
    await service.execute(job["job_id"])
    assert len(calls) == 2 and (await service.get(job["job_id"], {"employee_id": "A"}))["report"] == report
    assert await db.ai_runs.count_documents({}) == 0


async def test_restart_resumes_committed_code_step_without_reexecution(durable):
    db, _, manual, calls, clock, repo, service = durable
    await add_qa(db)
    job = await start(service)
    began = asyncio.Event()
    async def crash_window(view):
        began.set()
        await asyncio.Event().wait()
    manual.qa_specialist = crash_window
    task = asyncio.create_task(service.execute(job["job_id"]))
    await asyncio.wait_for(began.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    partial = await repo.collection.find_one({"_id": job["job_id"]})
    assert partial["status"] == "RUNNING" and "report" not in partial
    assert partial["checkpoint"]["outcomes"]["code_analysis"]["status"] == "SUCCEEDED"
    clock.advance()
    async def qa(view):
        assert view.prior_outcomes[0].status == "SUCCEEDED"
        calls.append(view)
        return reply(view)
    manual.qa_specialist = qa
    restarted = DurablePRWorkflowService(manual=manual, repository=PRWorkflowRepository(repo.collection, clock=clock))
    await restarted.run_ready()
    final = await restarted.get(job["job_id"], {"employee_id": "A"})
    assert final["status"] == "FINALIZED" and final["generation"] == 2
    assert [view.specialist for view in calls] == ["code_analysis", "qa_analysis"]
    assert len(final["step_results"]) == 2


async def test_late_response_after_takeover_cannot_write_or_publish(durable):
    _, _, manual, _, clock, repo, service = durable
    job = await start(service)
    async def late(view):
        clock.advance()
        assert await repo.claim(job["job_id"], "replacement") is not None
        return reply(view)
    manual.code_specialist = late
    await service.execute(job["job_id"])
    stored = await repo.collection.find_one({"_id": job["job_id"]})
    assert stored["generation"] == 2 and stored["step_results"] == [] and "report" not in stored


async def test_failed_inference_retries_are_bounded_and_explicit(durable):
    _, _, manual, calls, clock, _, service = durable
    async def unavailable(view):
        calls.append(view)
        raise ConnectionError("provider secret must not persist")
    manual.code_specialist = unavailable
    job = await start(service)
    for attempt in range(3):
        await service.execute(job["job_id"])
        clock.advance()
    stored = await service.get(job["job_id"], {"employee_id": "A"})
    assert len(calls) == 3 and len(stored["step_results"]) == 4
    assert [step["outcome"]["status"] for step in stored["step_results"]] == ["FAILED", "FAILED", "FAILED", "SKIPPED"]
    assert stored["analysis_status"] == "FAILED" and stored["report"]["status"] == "FAILED"
    assert "provider secret" not in str(stored)
    assert stored["attempts"] == 3


async def test_expired_last_attempt_is_failed_without_false_completion(durable):
    _, _, _, _, clock, repo, service = durable
    job = await start(service)
    for index in range(3):
        assert await repo.claim(job["job_id"], f"crashing-{index}") is not None
        clock.advance()
    await repo.ready_ids()
    stored = await service.get(job["job_id"], {"employee_id": "A"})
    assert stored["status"] == "FAILED" and stored["last_error"]["code"] == "RETRY_EXHAUSTED"
    assert "report" not in stored


@pytest.mark.parametrize("change", [{"role": "HR"}, {"org_id": "O2"}, {"project_ids": []}, {"is_active": False}])
async def test_revocation_prevents_sensitive_read_and_worker_publication(durable, change):
    db, _, _, calls, _, repo, service = durable
    job = await start(service)
    await db.users.update_one({"employee_id": "A"}, {"$set": change})
    with pytest.raises(HTTPException):
        await service.get(job["job_id"], {"employee_id": "A"})
    await service.execute(job["job_id"])
    stored = await repo.collection.find_one({"_id": job["job_id"]})
    assert stored["status"] == "FAILED" and "report" not in stored and not calls


async def test_cross_user_cannot_read_even_with_same_project_permissions(durable):
    db, _, _, _, _, _, service = durable
    job = await start(service)
    await db.users.insert_one({"employee_id": "B", "role": "LEAD", "org_id": "O1", "project_ids": ["P1"], "is_active": True})
    with pytest.raises(HTTPException):
        await service.get(job["job_id"], {"employee_id": "B"})
    other = await start(service, "B")
    assert other["job_id"] != job["job_id"]


async def test_renewal_uses_same_generation_and_extends_ownership(durable):
    _, _, _, _, clock, repo, service = durable
    job = await start(service)
    lease = await repo.claim(job["job_id"], "worker")
    clock.advance(80)
    assert await repo.renew(lease)
    clock.advance(20)
    row = await repo.read_owned(lease)
    assert row["generation"] == 1 and row["attempts"] == 1


async def test_expiry_without_a_replacement_still_rejects_all_writes(durable):
    _, _, _, _, clock, repo, service = durable
    job = await start(service)
    lease = await repo.claim(job["job_id"], "expired")
    clock.advance()
    assert not await repo.renew(lease)
    with pytest.raises(LeaseLost):
        await repo.fail(lease, "TRANSIENT", "LATE", retry=True)
    with pytest.raises(LeaseLost):
        await repo.publish(lease, None)


async def test_restart_after_all_steps_before_publication_requires_fenced_finalize(durable, monkeypatch):
    db, _, _, calls, clock, repo, service = durable
    await add_qa(db)
    job = await start(service)
    class ProcessCrash(BaseException):
        pass
    original = repo.publish
    async def crash(*args):
        raise ProcessCrash()
    monkeypatch.setattr(repo, "publish", crash)
    with pytest.raises(ProcessCrash):
        await service.execute(job["job_id"])
    stored = await repo.collection.find_one({"_id": job["job_id"]})
    assert stored["status"] == "RUNNING" and "report" not in stored and len(stored["step_results"]) == 2
    clock.advance()
    monkeypatch.setattr(repo, "publish", original)
    await service.execute(job["job_id"])
    final = await service.get(job["job_id"], {"employee_id": "A"})
    assert final["status"] == "FINALIZED" and final["generation"] == 2 and len(calls) == 2


@pytest.mark.parametrize("boundary", ["append_step", "publish"])
async def test_lost_mongo_write_ack_does_not_duplicate_committed_results(durable, monkeypatch, boundary):
    db, _, _, calls, clock, repo, service = durable
    await add_qa(db)
    job = await start(service)
    original = getattr(repo, boundary)
    async def uncertain(*args, **kwargs):
        await original(*args, **kwargs)
        raise AutoReconnect("simulated lost acknowledgement")
    monkeypatch.setattr(repo, boundary, uncertain)
    await service.execute(job["job_id"])
    monkeypatch.setattr(repo, boundary, original)
    clock.advance()
    await service.execute(job["job_id"])
    stored = await service.get(job["job_id"], {"employee_id": "A"})
    assert stored["status"] == "FINALIZED" and len(stored["step_results"]) == 2 and len(calls) == 2


async def test_revocation_after_code_completion_blocks_qa_and_publication(durable):
    db, _, manual, calls, _, repo, service = durable
    await add_qa(db)
    async def revoke(view):
        await db.users.update_one({"employee_id": "A"}, {"$set": {"role": "HR"}})
        return reply(view)
    manual.code_specialist = revoke
    job = await start(service)
    await service.execute(job["job_id"])
    row = await repo.collection.find_one({"_id": job["job_id"]})
    assert row["status"] == "FAILED" and not calls and "report" not in row and row["step_results"] == []


async def test_malformed_model_is_permanent_not_success_or_unbounded_retry(durable):
    _, _, manual, _, _, _, service = durable
    async def malformed(view):
        return '{"next_agent":"deploy","authoritative_score":100}'
    manual.code_specialist = malformed
    job = await start(service)
    await service.execute(job["job_id"])
    row = await service.get(job["job_id"], {"employee_id": "A"})
    assert row["attempts"] == 1 and row["analysis_status"] == "FAILED"
    assert row["report"]["outcomes"][0]["status"] == "FAILED"
    assert row["report"]["outcomes"][0]["error_code"] == "INVALID_MODEL_OUTPUT"


async def test_historical_report_is_immutable_and_new_revision_is_a_new_job(durable):
    db, api, _, _, _, _, service = durable
    await add_qa(db)
    job = await start(service)
    await service.execute(job["job_id"])
    old = await service.get(job["job_id"], {"employee_id": "A"})
    api.client.get_pull_request.return_value["head"]["sha"] = "f" * 40
    api.client.get_commit.return_value["sha"] = "f" * 40
    new = await start(service)
    assert new["job_id"] != job["job_id"]
    preserved = await service.get(job["job_id"], {"employee_id": "A"})
    assert old["report"] == preserved["report"] and old["snapshot"] == preserved["snapshot"]


@pytest.mark.parametrize("field", ["snapshot", "checkpoint", "step_results", "report"])
async def test_corrupted_persisted_evidence_is_never_reinterpreted_as_valid(durable, field):
    _, _, _, _, _, repo, service = durable
    job = await start(service)
    await service.execute(job["job_id"])
    row = await repo.collection.find_one({"_id": job["job_id"]})
    if field == "snapshot":
        row[field]["observations"][0]["value"] = 999
    elif field == "checkpoint":
        row[field]["outcomes"] = {}
    elif field == "step_results":
        row[field][0]["outcome"]["summary"] = "changed"
    else:
        row[field]["status"] = "COLLABORATIVE_ADVISORY"
    await repo.collection.update_one({"_id": job["job_id"]}, {"$set": {field: row[field]}})
    with pytest.raises(ValueError):
        await service.get(job["job_id"], {"employee_id": "A"})


async def test_backoff_and_disabled_flag_do_not_start_early_or_write(durable, monkeypatch):
    from core.config import settings
    db, _, manual, calls, clock, _, service = durable
    async def unavailable(view):
        calls.append(view)
        raise TimeoutError()
    manual.code_specialist = unavailable
    job = await start(service)
    await service.execute(job["job_id"])
    await service.execute(job["job_id"])
    assert len(calls) == 1
    clock.advance(2)
    monkeypatch.setattr(settings, "PR_MULTI_AGENT_INTERNAL_ENABLED", False)
    for operation in (service.execute(job["job_id"]), service.run_ready(), start(service)):
        with pytest.raises(HTTPException):
            await operation
    assert (await db.pr_multi_agent_jobs.find_one({"_id": job["job_id"]}))["attempts"] == 1


async def test_heartbeat_loss_cancels_inflight_model_and_never_commits_output(durable, monkeypatch):
    from domain.services import pr_workflow_durable
    _, _, manual, _, _, repo, service = durable
    started, cancelled = asyncio.Event(), asyncio.Event()
    async def stalled(view):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    async def lost(lease):
        # Force lease loss after inference really starts, rather than racing graph startup.
        await started.wait()
        return False
    manual.code_specialist = stalled
    monkeypatch.setattr(repo, "renew", lost)
    monkeypatch.setattr(pr_workflow_durable, "HEARTBEAT_SECONDS", 0.02)
    job = await start(service)
    await service.execute(job["job_id"])
    row = await repo.collection.find_one({"_id": job["job_id"]})
    assert cancelled.is_set() and row["step_results"] == [] and "report" not in row


@pytest.mark.parametrize("boundary", ["inference", "authorization"])
async def test_whole_attempt_deadline_is_a_bounded_retry(durable, monkeypatch, boundary):
    from domain.services import pr_workflow_durable
    _, _, manual, _, _, _, service = durable
    async def stalled(view):
        await asyncio.Event().wait()
    if boundary == "inference":
        manual.code_specialist = stalled
    monkeypatch.setattr(pr_workflow_durable, "EXECUTION_SECONDS", 0.02)
    job = await start(service)
    original_authorization = service.authorize_header
    if boundary == "authorization":
        async def stalled_authorization(*args):
            await asyncio.Event().wait()
        monkeypatch.setattr(service, "authorize_header", stalled_authorization)
    await asyncio.wait_for(service.execute(job["job_id"]), 5)
    monkeypatch.setattr(service, "authorize_header", original_authorization)
    row = await service.get(job["job_id"], {"employee_id": "A"})
    assert row["status"] == "RETRY_WAIT" and row["attempts"] == 1
    assert row["last_error"]["code"] == "EXECUTION_UNAVAILABLE" and "report" not in row


async def test_two_publication_attempts_under_same_generation_have_one_winner(durable, monkeypatch):
    db, _, _, _, _, repo, service = durable
    await add_qa(db)
    job = await start(service)
    captured = []
    original = repo.publish
    class ProcessCrash(BaseException):
        pass
    async def capture(lease, report):
        captured.extend((lease, report))
        raise ProcessCrash()
    monkeypatch.setattr(repo, "publish", capture)
    with pytest.raises(ProcessCrash):
        await service.execute(job["job_id"])
    results = await asyncio.gather(*(original(*captured) for _ in range(2)), return_exceptions=True)
    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, LeaseLost) for result in results) == 1
    with pytest.raises(LeaseLost):
        await repo.append_step(captured[0], captured[1].outcomes[0], advances=True)


async def test_ready_batch_is_bounded_and_incomplete_publication_rejected(durable):
    _, _, _, _, _, repo, service = durable
    job = await start(service)
    for limit in (0, 21, True):
        with pytest.raises(ValueError):
            await repo.ready_ids(limit)
    lease = await repo.claim(job["job_id"], "worker")
    with pytest.raises(ValueError):
        await repo.publish(lease, None)


async def test_no_payload_lookup_precedes_unauthorized_header_check(durable, monkeypatch):
    _, _, _, _, _, repo, service = durable
    job = await start(service)
    original = repo.collection.find_one
    lookups = []
    async def tracked(query, *args, **kwargs):
        lookups.append((query, args, kwargs))
        return await original(query, *args, **kwargs)
    monkeypatch.setattr(repo.collection, "find_one", tracked)
    with pytest.raises(HTTPException):
        await service.get(job["job_id"], {"employee_id": "foreign"})
    assert len(lookups) == 1 and lookups[0][1][0]["scope"] == 1
    assert "snapshot" not in lookups[0][1][0] and "report" not in lookups[0][1][0]


async def test_legacy_ephemeral_report_contract_remains_v1(durable):
    _, _, manual, _, _, _, _ = durable
    result = await manual.run({"project_id": "P1", "pr_number": 7}, {"employee_id": "A"})
    data = result.model_dump(mode="json")
    assert set(data) == {"schema_version", "workflow_type", "scope", "snapshot", "status", "collaboration",
        "eligible_specialists", "outcomes", "claims", "transitions", "limitations", "read_only", "authoritative_score", "durable"}
    assert data["schema_version"] == "pr-multi-agent-report-v1" and data["durable"] is False
    assert data["authoritative_score"] is None and data["read_only"] is True


async def test_durable_ledger_requires_majority_journaled_writes_and_primary_reads(durable):
    from pymongo import ReadPreference
    _, _, _, _, _, repo, _ = durable
    assert repo.collection.write_concern.document == {"w": "majority", "j": True, "wtimeout": 5000}
    assert repo.collection.read_concern.document == {"level": "majority"}
    assert repo.collection.read_preference == ReadPreference.PRIMARY
