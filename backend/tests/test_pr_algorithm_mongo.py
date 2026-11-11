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
    names = ["projects", "github_project_configs", "pull_requests", "code_quality_runs", "algorithm_function_contracts", "algorithm_benchmark_runs", "recommendations"]
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
