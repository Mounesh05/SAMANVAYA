"""Opt-in real Mongo server-clock, concurrency and abrupt-process recovery checks."""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import test_pr_multi_agent as workflow_tests
from test_pr_multi_agent import add_qa
from domain.services.pr_workflow_durable import DurablePRWorkflowService
from repositories.pr_workflow_repository import PRWorkflowRepository, LeaseLost

setup = workflow_tests.setup
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.getenv("SAMANVAYA_MONGO_TESTS") != "1",
                                                  reason="Opt-in real MongoDB durability tests")]


@pytest.fixture
async def real(setup):
    db, _, manual, calls = setup
    client = AsyncIOMotorClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=3000)
    name = "test_pr_workflow_" + uuid4().hex
    collection = client["samanvaya_test"][name]
    try:
        await client.admin.command("ping")
        repo = PRWorkflowRepository(collection)
        service = DurablePRWorkflowService(manual=manual, repository=repo)
        yield db, manual, calls, repo, service, client
    finally:
        assert collection.name == name and name.startswith("test_pr_workflow_")
        await collection.drop()
        client.close()


async def start(service):
    return await service.start({"project_id": "P1", "pr_number": 7}, {"employee_id": "A"})


async def expire(repo, job_id):
    # Deliberate failure injection in this test's exclusively owned temporary collection.
    await repo.collection.update_one({"_id": job_id}, {"$set": {
        "lease_expires_at": datetime.now(timezone.utc) - timedelta(seconds=5)}})


async def test_real_mongo_duplicate_starts_atomic_claims_server_time_and_fencing(real):
    _, _, _, repo, service, client = real
    jobs = await asyncio.gather(*(start(service) for _ in range(12)))
    key = jobs[0]["job_id"]
    assert len({row["job_id"] for row in jobs}) == 1 and await repo.collection.count_documents({}) == 1
    claims = await asyncio.gather(*(repo.claim(key, str(i)) for i in range(16)))
    lease = next(claim for claim in claims if claim is not None)
    assert sum(claim is not None for claim in claims) == 1 and lease.generation == 1
    before = (await repo.collection.find_one({"_id": key}))["lease_expires_at"]
    assert await repo.renew(lease)
    after = (await repo.collection.find_one({"_id": key}))["lease_expires_at"]
    server_time = (await client.admin.command("hello"))["localTime"]
    assert after >= before and 0 < (after - server_time).total_seconds() <= 91
    await expire(repo, key)
    assert not await repo.renew(lease)
    with pytest.raises(LeaseLost):
        await repo.fail(lease, "LATE", "AFTER_EXPIRY")
    replacement = await repo.claim(key, "replacement")
    assert replacement.generation == 2
    with pytest.raises(LeaseLost):
        await repo.read_owned(lease)


CRASH_AFTER_CODE = '''
import asyncio, os, sys
from motor.motor_asyncio import AsyncIOMotorClient
from domain.models.pr_multi_agent import AgentOutcome, ClaimDraft
from repositories.pr_workflow_repository import PRWorkflowRepository

async def main():
    client = AsyncIOMotorClient(sys.argv[1], serverSelectionTimeoutMS=3000)
    repo = PRWorkflowRepository(client[sys.argv[2]][sys.argv[3]])
    lease = await repo.claim(sys.argv[4], "separate-process")
    row = await repo.read_owned(lease)
    fact = next(item for item in row["snapshot"]["observations"] if item["metric"] == "function_count")
    claim = ClaimDraft(kind="OBSERVATION", statement="Controlled observation", topic="function_count",
        evidence_refs=(fact["evidence_id"],), observation_id=fact["observation_id"], asserted_value=fact["value"])
    await repo.append_step(lease, AgentOutcome(specialist="code_analysis", status="SUCCEEDED",
        summary="Controlled subprocess result", claims=(claim,)), advances=True)
    os._exit(23)

asyncio.run(main())
'''


async def test_real_mongo_abrupt_process_exit_after_step_resumes_without_rerunning_code(real):
    db, manual, calls, repo, service, _ = real
    await add_qa(db)
    job = await start(service)
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", CRASH_AFTER_CODE, os.environ["MONGO_URI"],
        repo.collection.database.name, repo.collection.name, job["job_id"],
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
        assert process.returncode == 23, (stdout.decode(), stderr.decode())
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    partial = await repo.collection.find_one({"_id": job["job_id"]})
    assert partial["status"] == "RUNNING" and "report" not in partial and len(partial["step_results"]) == 1
    await expire(repo, job["job_id"])
    restarted = DurablePRWorkflowService(manual=manual, repository=PRWorkflowRepository(repo.collection))
    await restarted.run_ready()
    final = await restarted.get(job["job_id"], {"employee_id": "A"})
    assert final["status"] == "FINALIZED" and final["generation"] == 2
    assert [view.specialist for view in calls] == ["qa_analysis"]
    assert len(final["step_results"]) == 2 and final["report"]["durable"] is True


async def test_real_mongo_competing_workers_publish_one_immutable_report(real):
    db, manual, calls, repo, service, _ = real
    await add_qa(db)
    job = await start(service)
    workers = [DurablePRWorkflowService(manual=manual, repository=PRWorkflowRepository(repo.collection)) for _ in range(8)]
    await asyncio.gather(*(worker.execute(job["job_id"]) for worker in workers))
    final = await service.get(job["job_id"], {"employee_id": "A"})
    assert final["status"] == "FINALIZED" and final["generation"] == 1 and len(calls) == 2
    assert len(final["step_results"]) == 2
    assert await repo.collection.count_documents({"report": {"$exists": True}}) == 1
    report = final["report"]
    await service.run_ready()
    assert (await service.get(job["job_id"], {"employee_id": "A"}))["report"] == report
