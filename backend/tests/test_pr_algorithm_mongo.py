"""Opt-in real MongoDB deduplication check; only owned temporary collections change."""

import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from domain.services.pr_algorithm_intelligence_service import PRAlgorithmIntelligenceService

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.environ.get("SAMANVAYA_MONGO_TESTS") != "1",
    reason="Requires an explicitly enabled local MongoDB integration test")]


async def test_real_mongo_duplicate_job_keys_coexist_with_function_snapshots():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=2000)
    prefix = "test_pr_algorithm_" + uuid.uuid4().hex
    names = ["projects", "github_project_configs", "pull_requests", "code_quality_runs", "algorithm_function_contracts", "algorithm_benchmark_runs", "algorithm_requirement_sources", "recommendations"]
    collections = {name: client["samanvaya_test"][prefix + "_" + name] for name in names}
    try:
        await client.admin.command("ping")
        await collections["projects"].insert_one({"id": "P", "org_id": "O"})
        await collections["github_project_configs"].insert_one({"project_id": "P", "repository_owner": "o", "repository_name": "r"})
        await collections["pull_requests"].insert_one({"id": "PR", "project_id": "P", "head_sha": "head"})
        await collections["code_quality_runs"].insert_many([{"run_id": "previous-snapshot"}, {"run_id": "current-snapshot"}])
        service = PRAlgorithmIntelligenceService(None, collections)
        pr = {"number": 1, "state": "open", "base": {"sha": "base"}, "head": {"sha": "head"}}
        first, second = await asyncio.gather(*[service.enqueue("P", "o/r", pr, [{"filename": "module.py"}], "PR", launch=False) for _ in range(2)])
        assert first["run_id"] == second["run_id"]
        assert first.get("duplicate") or second.get("duplicate")
        again = await service.enqueue("P", "o/r", pr, [{"filename": "module.py"}], "PR", launch=False)
        assert again["duplicate"]
        assert await collections["code_quality_runs"].count_documents({"kind": "pr_algorithm_intelligence"}) == 1
    finally:
        for name, collection in collections.items():
            assert collection.name == prefix + "_" + name and collection.name.startswith("test_pr_algorithm_")
            await collection.drop()
        client.close()

async def test_approval_outbox_survives_database_restart_and_dispatch_race(tmp_path, monkeypatch):
    """Restart a test-owned loopback mongod only, using independent GitHub/worker adapters."""
    import copy
    import shutil
    import socket
    import subprocess
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from pymongo.errors import AutoReconnect
    from domain.services.algorithm_approval_recovery import dispatch_page
    from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
    from domain.services.requirement_discovery_service import RequirementDiscoveryService
    from test_behavioral_compatibility import passing_evidence
    from test_pr_algorithm_intelligence import BASE, HEAD, run, contract

    binary = shutil.which("mongod") or os.environ.get("SAMANVAYA_TEST_MONGOD")
    if not binary:
        pytest.fail("Set SAMANVAYA_TEST_MONGOD to a local mongod binary for restart verification")
    with socket.socket() as port_probe:
        port_probe.bind(("127.0.0.1", 0))
        port = port_probe.getsockname()[1]
    data = tmp_path / "owned-db"
    data.mkdir()
    def start():
        return subprocess.Popen([str(Path(binary)), "--dbpath", str(data), "--port", str(port),
                                 "--bind_ip", "127.0.0.1", "--logpath", str(tmp_path / "mongo.log"), "--logappend"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    process = start()
    client = AsyncIOMotorClient(f"mongodb://127.0.0.1:{port}", serverSelectionTimeoutMS=15000)
    db = client["approval_recovery"]
    async def stop():
        try:
            await client.admin.command("shutdown", force=True)
        except AutoReconnect:
            pass
        await asyncio.to_thread(process.wait, 30)
    try:
        await client.admin.command("ping")
        await db.projects.insert_one({"id": "P1", "org_id": "org"})
        await db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "o", "repository_name": "r"})
        await db.pull_requests.insert_one({"id": "PR1", "project_id": "P1", "status": "open", "head_sha": "head"})
        pr = {"number": 7, "state": "open", "base": {"sha": "base"}, "head": {"sha": "head"}}
        snapshots = {"base": {"module.py": BASE}, "head": {"module.py": HEAD}}
        api = SimpleNamespace(client=SimpleNamespace(get_pull_request=AsyncMock(return_value=pr)),
            fetch_analysis_sources=AsyncMock(side_effect=lambda o, r, files, rev, **kw: (copy.deepcopy(snapshots[rev]), [])))
        worker = SimpleNamespace(run=AsyncMock(side_effect=passing_evidence))
        def workflow():
            benchmarks = AlgorithmBenchmarkService(db.algorithm_benchmark_runs, worker, RequirementDiscoveryService(db))
            return PRAlgorithmIntelligenceService(api, db, benchmarks, enabled=True)
        from agents import algorithm_agent
        monkeypatch.setattr(algorithm_agent, "infer", AsyncMock(side_effect=ValueError("independent model test")))
        context = SimpleNamespace(service=workflow(), pr=pr)
        original = await run(context)
        approved = await contract(context)
        assert approved["continuation"]["status"] == "pending"
        await stop()
        client.close()
        process = start()
        client = AsyncIOMotorClient(f"mongodb://127.0.0.1:{port}", serverSelectionTimeoutMS=15000)
        db = client["approval_recovery"]
        await client.admin.command("ping")
        await asyncio.gather(*(dispatch_page(workflow(), db.algorithm_function_contracts) for _ in range(2)))
        revision = await db.algorithm_function_contracts.find_one({"contract_id": approved["contract_id"]})
        assert revision["continuation"]["status"] == "completed"
        for _ in range(100):
            latest = await db.code_quality_runs.find_one({"approval_continuation": True})
            if latest and latest["status"] == "completed":
                break
            await asyncio.sleep(.1)
        assert latest["status"] == "completed"
        assert original["run_id"] != latest["run_id"]
        assert await db.algorithm_benchmark_runs.count_documents({}) == 1
        worker.run.assert_awaited_once()
    finally:
        if process.poll() is None:
            try:
                await stop()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        client.close()
