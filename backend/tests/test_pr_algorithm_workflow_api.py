"""Signed webhook dispatch, tenant-bound mapped views and PR sync races."""

import asyncio
import copy
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import algorithms, webhooks, github
from core.dependencies import get_current_user
from domain.models.webhook_event import WebhookEvent
from domain.services.webhook_event_processor import WebhookEventProcessor
from repositories.webhook_event_repository import WebhookEventRepository
from repositories.recommendation_repository import RecommendationRepository
from test_pr_algorithm_intelligence import workflow, contract, run

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_supported_event_uses_existing_sync_and_algorithm_result_even_for_low_risk(action):
    processor = WebhookEventProcessor.__new__(WebhookEventProcessor)
    processor.github_service = SimpleNamespace(sync_pull_request=AsyncMock(return_value={"pr": {"id": "PR1"},
        "risk_analysis": {"risk_score": 0, "risk_level": "low"}, "algorithm_intelligence": {"run_id": "PRI-1"}}))
    processor.traceability_service = SimpleNamespace(link_pr_to_tasks=AsyncMock(return_value=[]), link_pr_to_files=AsyncMock(return_value=[]),
        calculate_blast_radius=AsyncMock(return_value=SimpleNamespace(total_affected_entities=0)))
    processor.recommendation_engine = SimpleNamespace(generate_pr_recommendations=AsyncMock())
    processor._notify_pr_opened = AsyncMock(return_value=[])
    result = await processor._handle_pull_request_event(WebhookEvent(id="WH", event_type="pull_request", event_action=action,
        project_id="P1", repository="o/r", payload={"pull_request": {"number": 7}, "repository": {"full_name": "o/r"}}))
    assert "algorithm_intelligence" in result["triggers_executed"]
    processor.github_service.sync_pull_request.assert_awaited_once()
    processor.recommendation_engine.generate_pr_recommendations.assert_not_awaited()


async def test_webhook_acknowledges_without_waiting_for_processing_and_deduplicates(mock_db):
    processor = WebhookEventProcessor.__new__(WebhookEventProcessor)
    processor.event_repo = WebhookEventRepository.__new__(WebhookEventRepository)
    processor.event_repo.collection = mock_db.webhook_events
    processor._match_repository_to_project = AsyncMock(return_value="P1")
    gate = asyncio.Event()
    async def pending(*args):
        await gate.wait()
    processor._process_event_async = AsyncMock(side_effect=pending)
    payload = {"action": "opened", "repository": {"full_name": "o/r"}, "pull_request": {"number": 7}}
    first = await asyncio.wait_for(processor.process_github_event("pull_request", payload, "verified"), 1)
    second = await asyncio.wait_for(processor.process_github_event("pull_request", copy.deepcopy(payload), "verified"), 1)
    assert first["event_id"] == second["event_id"] and second["duplicate"]
    assert await mock_db.webhook_events.count_documents({}) == 1
    gate.set()
    await asyncio.sleep(0)
    processor._process_event_async.assert_awaited_once()


async def test_webhook_signature_gate_stays_fail_closed_and_nonobject_is_rejected(monkeypatch):
    monkeypatch.setattr(webhooks.webhook_service, "verify_signature", lambda body, sig: sig == "valid")
    processor = SimpleNamespace(process_github_event=AsyncMock(return_value={"status": "accepted"}))
    monkeypatch.setattr(webhooks, "event_processor", processor)
    app = FastAPI()
    app.include_router(webhooks.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/github", json={}, headers={"X-GitHub-Event": "pull_request"})
        assert response.status_code == 401
        response = await client.post("/github", json=[], headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "valid"})
        assert response.status_code == 400
    processor.process_github_event.assert_not_awaited()


async def test_exact_mapping_does_not_match_a_repository_name_substring(mock_db, monkeypatch):
    import core.database as database
    monkeypatch.setattr(database, "col", lambda name: mock_db[name])
    processor = WebhookEventProcessor.__new__(WebhookEventProcessor)
    processor.project_repo = SimpleNamespace(find_all=AsyncMock(return_value=[{"id": "P1", "code_repo_url": "https://github.com/o/replica"}]))
    assert await processor._match_repository_to_project("o/rep") is None
    await mock_db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "o", "repository_name": "rep"})
    assert await processor._match_repository_to_project("o/rep") == "P1"


async def test_mapped_algorithm_history_needs_no_manual_project_id_and_stays_tenant_scoped(workflow, monkeypatch):
    await run(workflow)
    monkeypatch.setattr(algorithms, "col", lambda name: workflow.db[name])
    monkeypatch.setattr(algorithms.ProjectRepository, "find_by_id", AsyncMock(side_effect=lambda key: {"id": key, "org_id": "org"}))
    user = {"employee_id": "dev", "role": "DEVELOPER", "org_id": "org", "project_ids": ["P1"]}
    app = FastAPI()
    app.include_router(algorithms.router)
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/pr-intelligence")
        assert response.status_code == 200 and len(response.json()["analyses"]) == 1
        response = await client.get("/pr-intelligence", params={"pr_id": "PR1"})
        assert response.status_code == 200 and not response.json()["analyses"][0]["historical_only"]
        user["org_id"] = "foreign"
        response = await client.get("/pr-intelligence", params={"pr_id": "PR1"})
        assert response.status_code == 403


async def test_stale_recommendations_are_not_returned_as_pending(workflow, monkeypatch):
    await contract(workflow)
    result = await run(workflow)
    import repositories.recommendation_repository as module
    monkeypatch.setattr(module, "db", workflow.db)
    repository = RecommendationRepository()
    assert await repository.find_by_entity("pr", "PR1", "pending")
    await workflow.db.pull_requests.update_one({"id": "PR1"}, {"$set": {"head_sha": "newer"}})
    assert await repository.find_by_entity("pr", "PR1", "pending") == []
    record = await repository.find_by_id(result["recommendation_ids"][0])
    assert record["status"] == "obsolete" and record["historical_only"]
    assert not await repository.update_status(record["id"], "accepted", "dev")


async def test_manual_pr_sync_resolves_existing_mapping_instead_of_requiring_project_id(workflow, monkeypatch):
    monkeypatch.setattr(github, "col", lambda name: workflow.db[name])
    monkeypatch.setattr(github, "verify_project_access", AsyncMock())
    sync = AsyncMock(return_value={"pr": {"id": "PR1", "risk_level": "low", "risk_score": 0}})
    monkeypatch.setattr(github, "GitHubSyncService", lambda: SimpleNamespace(sync_pull_request=sync))
    result = await github.sync_pull_request(github.PRSyncRequest(owner="o", repo="r", pr_number=7),
        {"employee_id": "dev", "role": "DEVELOPER", "org_id": "org"})
    assert result["pr_id"] == "PR1" and sync.call_args.kwargs["project_id"] == "P1"


async def test_real_sync_path_queues_algorithm_analysis_without_ai_or_high_risk(workflow, monkeypatch):
    import domain.services.github_sync_service as sync_module
    import domain.services.pr_algorithm_intelligence_service as automatic_module
    import repositories.pr_repository as pr_module
    import repositories.code_quality_repository as quality_module
    monkeypatch.setattr(pr_module, "col", lambda name: workflow.db[name])
    monkeypatch.setattr(quality_module, "col", lambda name: workflow.db[name])
    monkeypatch.setattr(sync_module, "AIRunRepository", lambda: SimpleNamespace(create=AsyncMock()))
    monkeypatch.setattr(automatic_module, "PRAlgorithmIntelligenceService", lambda api: workflow.service)
    await contract(workflow)
    sync = sync_module.GitHubSyncService()
    sync.api_service = workflow.api
    raw_pr = {**copy.deepcopy(workflow.pr), "id": 7, "title": "Change operation", "user": {"login": "developer"},
        "head": {"sha": "head", "ref": "feature"}, "base": {"sha": "base", "ref": "testing"},
        "created_at": "2026-11-01T10:00:00Z", "updated_at": "2026-11-10T10:00:00Z", "html_url": "https://github.com/o/r/pull/7"}
    workflow.api.fetch_pull_request_data = AsyncMock(return_value={"pr": raw_pr, "files": [{"filename": "module.py", "status": "modified"}], "commits": [], "check_runs": {"check_runs": []}})
    sync.analysis_service.analyze_risk = AsyncMock(return_value={"risk_score": 0, "risk_level": "low"})
    sync.analysis_service.analyze_with_ai = AsyncMock(side_effect=AssertionError("AI is disabled"))
    result = await sync.sync_pull_request("o", "r", 7, "P1", use_ai=False)
    assert result["algorithm_intelligence"]["run_id"]
    await asyncio.wait_for(asyncio.gather(*list(automatic_module._TASKS)), 10)
    stored = await workflow.service.get(result["algorithm_intelligence"]["run_id"])
    assert stored["status"] == "completed", stored.get("error")
    workflow.runner.run.assert_awaited_once()
    sync.analysis_service.analyze_with_ai.assert_not_awaited()
    duplicate = await sync.sync_pull_request("o", "r", 7, "P1", use_ai=False)
    assert duplicate["algorithm_intelligence"]["duplicate"]
    workflow.runner.run.assert_awaited_once()
