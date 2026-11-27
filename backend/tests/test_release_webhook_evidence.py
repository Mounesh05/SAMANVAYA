"""Release evidence survives duplicate deliveries and stays within its revision and tenant."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import webhooks
from core import database
from core.config import settings
from domain.models.webhook_event import WebhookEvent
from domain.services.github_sync_service import GitHubSyncService
from domain.services.production_evidence import production_evidence
from domain.services.webhook_event_processor import WebhookEventProcessor
from integrations.github.normalizer import GitHubNormalizer


HEAD = "a" * 40
MERGE = "b" * 40
SECRET = "local-webhook-fixture"


def pull_request():
    return {
        "id": 3, "number": 3, "state": "closed", "merged": True, "title": "Implement search",
        "created_at": "2026-11-01T10:00:00Z", "merged_at": "2026-11-03T10:00:00Z",
        "updated_at": "2026-11-03T10:00:02Z", "head": {"ref": "search", "sha": HEAD},
        "base": {"ref": "main", "sha": "c" * 40}, "merge_commit_sha": MERGE,
        "user": {"login": "dev"}, "html_url": "https://github.com/org/repo/pull/3",
    }


def test_only_a_merged_pr_has_a_release_revision():
    raw = pull_request()
    merged = GitHubNormalizer.normalize_pull_request(raw, "P", "org/repo")
    assert merged["head_sha"] == HEAD and merged["merge_commit_sha"] == MERGE
    for state in ("open", "closed"):
        preview = {**raw, "state": state, "merged": False, "merged_at": None}
        assert GitHubNormalizer.normalize_pull_request(preview, "P", "org/repo")["merge_commit_sha"] is None


@pytest.mark.anyio
async def test_close_refresh_uses_current_pr_before_any_task_transition(mock_db, monkeypatch):
    from domain.services import github_sync_service, webhook_event_processor

    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    raw = pull_request()
    processor = WebhookEventProcessor()
    service = processor.github_service
    assert isinstance(service, GitHubSyncService)
    service.api_service.fetch_pull_request_data = AsyncMock(return_value={
        "pr": raw, "files": [], "commits": [], "check_runs": {"check_runs": []},
    })
    service.analysis_service.analyze_risk = AsyncMock(return_value={"risk_score": 0, "risk_level": "low"})
    # The provider corrected the merge identity while the first fetch was being processed.
    service.api_service.client.get_pull_request = AsyncMock(return_value={**raw, "merge_commit_sha": "d" * 40})
    stale_move = AsyncMock()
    monkeypatch.setattr(github_sync_service, "apply_task_progress", stale_move)
    monkeypatch.setattr(webhook_event_processor, "apply_task_progress", stale_move)
    event = WebhookEvent(id="WH", event_type="pull_request", event_action="closed",
        repository="org/repo", project_id="P", payload={"repository": {"full_name": "org/repo"}, "pull_request": raw})
    await processor._handle_pull_request_event(event)
    stale_move.assert_not_awaited()
    assert await mock_db.pull_requests.count_documents({}) == 0
    service.api_service.client.get_pull_request.return_value = raw
    service.api_service.fetch_analysis_sources = AsyncMock(return_value=({}, []))
    monkeypatch.setattr("domain.services.pr_algorithm_intelligence_service.PRAlgorithmIntelligenceService.enqueue",
                        AsyncMock(return_value=None))
    await processor._handle_pull_request_event(event)
    stale_move.assert_awaited_once_with("P", raw, None)
    stored = await mock_db.pull_requests.find_one({"project_id": "P", "pr_number": 3})
    assert stored["status"] == "merged" and stored["merge_commit_sha"] == MERGE and stored["head_sha"] == HEAD


@pytest.fixture
async def webhook_client(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", SECRET)
    worker = WebhookEventProcessor()
    monkeypatch.setattr(worker, "_schedule_event", lambda _: None)
    monkeypatch.setattr(webhooks, "event_processor", worker)
    await mock_db.projects.insert_one({"id": "P", "org_id": "A"})
    await mock_db.github_project_configs.insert_one({
        "project_id": "P", "org_id": "A", "repository_owner": "Org", "repository_name": "Repo",
    })
    app = FastAPI()
    app.include_router(webhooks.router, prefix="/api/webhooks")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


def deployment(state="success", event_id=12, hour=13, environment="production"):
    return {"action": "created", "repository": {"full_name": "org/repo"},
            "deployment": {"id": 7, "sha": MERGE, "environment": environment},
            "deployment_status": {"id": event_id, "state": state, "environment": environment,
                                  "created_at": f"2026-11-03T{hour}:00:00Z"}}


async def send_event(client, payload, secret=SECRET):
    body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return await client.post("/api/webhooks/github", content=body, headers={
        "X-GitHub-Event": "deployment_status", "X-Hub-Signature-256": "sha256=" + signature,
    })


@pytest.mark.anyio
async def test_signed_status_is_scoped_to_merged_commit_tenant_and_provider_time(webhook_client, mock_db):
    unsigned = await send_event(webhook_client, deployment(), secret="incorrect")
    assert unsigned.status_code == 401 and await mock_db.webhook_events.count_documents({}) == 0
    reply = await send_event(webhook_client, deployment())
    assert reply.status_code == 200
    duplicate = await send_event(webhook_client, deployment())
    assert duplicate.json()["duplicate"] and duplicate.json()["event_id"] == reply.json()["event_id"]
    assert await mock_db.webhook_events.count_documents({}) == 1
    # A late failure, then a separate staging failure, cannot replace a newer production result.
    assert (await send_event(webhook_client, deployment("failure", 10, 12))).status_code == 200
    assert (await send_event(webhook_client, deployment("failure", 14, 15, "staging"))).status_code == 200
    result = await production_evidence("P", "Org/Repo", MERGE, "A")
    assert result["status"] == "deployed" and result["deployment_id"] == 7
    assert (await production_evidence("P", "org/repo", HEAD, "A"))["status"] == "unknown"
    assert (await production_evidence("P", "org/repo", MERGE, "B"))["status"] == "unknown"
    assert (await send_event(webhook_client, deployment("failure", 16, 16))).status_code == 200
    assert (await production_evidence("P", "org/repo", MERGE, "A"))["status"] == "failed"


@pytest.mark.anyio
async def test_ambiguous_repo_mapping_or_foreign_config_cannot_establish_production(webhook_client, mock_db):
    await mock_db.github_project_configs.update_one({"project_id": "P"}, {"$set": {"org_id": "B"}})
    assert (await send_event(webhook_client, deployment())).status_code == 200
    await mock_db.github_project_configs.update_one({"project_id": "P"}, {"$set": {"org_id": "A"}})
    await mock_db.github_project_configs.insert_one({
        "project_id": "Q", "org_id": "B", "repository_owner": "org", "repository_name": "repo",
    })
    assert (await send_event(webhook_client, deployment(event_id=13))).status_code == 200
    assert await mock_db.webhook_events.count_documents({"production": {"$exists": True}}) == 0
