"""Durable webhook acceptance, restart recovery, and lease ownership."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from domain.models.webhook_event import WebhookEvent
from domain.services.webhook_event_processor import WebhookEventProcessor
from repositories.webhook_event_repository import WebhookEventRepository

pytestmark = pytest.mark.anyio


async def drain(worker):
    await asyncio.gather(*tuple(getattr(worker, "_tasks", ())))


def processor(db, handler):
    instance = WebhookEventProcessor.__new__(WebhookEventProcessor)
    instance.event_repo = WebhookEventRepository.__new__(WebhookEventRepository)
    instance.event_repo.collection = db.webhook_events
    instance._get_event_handler = lambda _: handler
    instance._match_repository_to_project = AsyncMock(return_value="P1")
    return instance


async def event(db, event_id="WH-1", **kwargs):
    await db.webhook_events.insert_one(WebhookEvent(
        id=event_id, event_type="push", repository="o/r", **kwargs).model_dump())


async def test_restart_recovers_accepted_event_before_task_started(mock_db, monkeypatch):
    first = processor(mock_db, AsyncMock(return_value={}))
    # Model process termination immediately after durable acceptance.
    monkeypatch.setattr(first, "_schedule_event", lambda _: None, raising=False)
    accepted = await first.process_github_event("push", {"repository": {"full_name": "o/r"}}, "verified")
    second = processor(mock_db, AsyncMock(return_value={"triggers_executed": ["recovered"]}))
    await second.recover_once()
    await drain(second)
    saved = await second.event_repo.find_by_id(accepted["event_id"])
    assert saved["status"] == "completed" and saved["triggers_executed"] == ["recovered"]


async def test_expired_processing_is_reclaimed_but_live_worker_is_not(mock_db):
    await event(mock_db)
    worker = processor(mock_db, AsyncMock(return_value={}))
    now = datetime.now(timezone.utc)
    old = await worker.event_repo.claim("WH-1", now, lease_seconds=60)
    assert old
    assert await worker.event_repo.claim("WH-1", now, lease_seconds=60) is None
    replacement = await worker.event_repo.claim("WH-1", now + timedelta(seconds=61), lease_seconds=60)
    assert replacement and replacement["lease_id"] != old["lease_id"]
    # A stale owner cannot overwrite a new owner's result.
    assert not await worker.event_repo.mark_completed("WH-1", now.isoformat(), [], [], [], [], lease_id=old["lease_id"])
    assert (await worker.event_repo.find_by_id("WH-1"))["status"] == "processing"


async def test_two_recovery_workers_process_once(mock_db):
    await event(mock_db)
    calls = []
    async def handler(value):
        calls.append(value.id)
        await asyncio.sleep(0)
        return {}
    workers = [processor(mock_db, handler), processor(mock_db, handler)]
    await asyncio.gather(*(p.recover_once() for p in workers))
    await asyncio.gather(*(drain(p) for p in workers))
    assert calls == ["WH-1"]


async def test_failed_events_have_bounded_retries_and_backoff(mock_db):
    await event(mock_db)
    worker = processor(mock_db, AsyncMock(side_effect=RuntimeError("unavailable")))
    for attempt in range(1, 4):
        await worker._process_event_async("WH-1")
        saved = await worker.event_repo.find_by_id("WH-1")
        assert saved["status"] == "failed" and saved["retry_count"] == attempt
        assert saved["next_attempt_at"].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
        await mock_db.webhook_events.update_one({"id": "WH-1"}, {"$set": {"next_attempt_at": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    await worker.recover_once()
    await drain(worker)
    assert (await worker.event_repo.find_by_id("WH-1"))["retry_count"] == 3


async def test_shutdown_cancels_owned_work_and_leaves_retryable_event(mock_db):
    await event(mock_db)
    entered = asyncio.Event()
    async def handler(_):
        entered.set()
        await asyncio.Event().wait()
    worker = processor(mock_db, handler)
    await worker.recover_once()
    await asyncio.wait_for(entered.wait(), 1)
    await worker.stop()
    assert (await worker.event_repo.find_by_id("WH-1"))["status"] == "failed"


async def test_recovery_covers_legacy_processing_and_limits_inflight_work(mock_db):
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await event(mock_db, status="processing", processing_started_at=old)
    worker = processor(mock_db, AsyncMock(return_value={}))
    worker.max_inflight = 2
    for index in range(10):
        await event(mock_db, event_id=f"WH-{index + 2}")
    await worker.recover_once()
    assert len(worker._tasks) <= 2
    await drain(worker)
    assert (await worker.event_repo.find_by_id("WH-1"))["status"] == "completed"


async def test_heartbeat_keeps_slow_work_owned(mock_db):
    await event(mock_db)
    entered = asyncio.Event()
    release = asyncio.Event()
    async def handler(_):
        entered.set()
        await release.wait()
        return {}
    worker = processor(mock_db, handler)
    worker.lease_seconds = 0.3
    task = asyncio.create_task(worker._process_event_async("WH-1"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        initial = (await worker.event_repo.find_by_id("WH-1"))["lease_expires_at"]
        for _ in range(100):
            current = (await worker.event_repo.find_by_id("WH-1"))["lease_expires_at"]
            if current > initial:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("No lease heartbeat observed")
        release.set()
        await asyncio.wait_for(task, 1)
        assert (await worker.event_repo.find_by_id("WH-1"))["status"] == "completed"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_lost_lease_cancels_stale_work_without_overwriting_new_owner(mock_db):
    await event(mock_db)
    entered, canceled = asyncio.Event(), asyncio.Event()
    async def handler(_):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            canceled.set()
    worker = processor(mock_db, handler)
    worker.lease_seconds = 0.03
    task = asyncio.create_task(worker._process_event_async("WH-1"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await mock_db.webhook_events.update_one({"id": "WH-1"}, {"$set": {"lease_id": "replacement"}})
        await asyncio.wait_for(canceled.wait(), 1)
        with pytest.raises(asyncio.CancelledError):
            await task
        saved = await worker.event_repo.find_by_id("WH-1")
        assert saved["status"] == "processing" and saved["lease_id"] == "replacement"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
