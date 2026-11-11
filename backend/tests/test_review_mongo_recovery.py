"""Opt-in real process-exit checks; only uniquely owned collections are written."""

import asyncio
import os
import sys
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from core import database, security
from domain.services.webhook_event_processor import WebhookEventProcessor
from repositories.webhook_event_repository import WebhookEventRepository

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(
    os.environ.get("SAMANVAYA_MONGO_TESTS") != "1", reason="Opt-in MongoDB process recovery check")]

CHILD = '''
import asyncio, os
from datetime import datetime, timezone, timedelta
from core import database
from core.security import revoke_token
from domain.models.webhook_event import WebhookEvent
from repositories.webhook_event_repository import WebhookEventRepository

async def main():
    actual_db = database.get_db()
    class Scoped:
        def __getitem__(self, name):
            return actual_db[os.environ["REVIEW_COLLECTION_PREFIX"] + name]
    database.get_db = lambda: Scoped()
    repo = WebhookEventRepository()
    await repo.insert(WebhookEvent(id="WH-RESTART", repository="o/r", event_type="push").model_dump())
    if os.environ["REVIEW_EVENT_STATE"] == "processing":
        assert await repo.claim("WH-RESTART", datetime.now(timezone.utc), lease_seconds=0.1)
    await revoke_token("RESTART-JTI", datetime.now(timezone.utc) + timedelta(minutes=5))
    # Abrupt process exit: no worker shutdown hook and no in-memory state survives.
    os._exit(0)
asyncio.run(main())
'''


@pytest.mark.parametrize("state", ["pending", "processing"])
async def test_process_exit_preserves_revocation_and_recovers_event(monkeypatch, state):
    prefix = "review_recovery_" + uuid.uuid4().hex + "_"
    client = AsyncIOMotorClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=2000)
    db = client[os.environ["DB_NAME"]]
    class Scoped:
        def __getitem__(self, name):
            return db[prefix + name]
    monkeypatch.setattr(database, "get_db", lambda: Scoped())
    try:
        await client.admin.command("ping")
        process = await asyncio.create_subprocess_exec(sys.executable, "-c", CHILD,
            env={**os.environ, "REVIEW_COLLECTION_PREFIX": prefix, "REVIEW_EVENT_STATE": state},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 20)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        assert process.returncode == 0, (stdout + stderr).decode(errors="replace")
        assert await security.is_token_revoked("RESTART-JTI")
        calls = []
        async def handle(event):
            calls.append(event.id)
            return {"triggers_executed": ["after_restart"]}
        worker = WebhookEventProcessor.__new__(WebhookEventProcessor)
        worker.event_repo = WebhookEventRepository()
        worker._get_event_handler = lambda _: handle
        await worker.start()
        try:
            for _ in range(200):
                saved = await worker.event_repo.find_by_id("WH-RESTART")
                if saved["status"] == "completed":
                    break
                await worker.recover_once()
                await asyncio.sleep(0.01)
            assert saved["status"] == "completed"
            assert saved["triggers_executed"] == ["after_restart"]
            assert calls == ["WH-RESTART"]
        finally:
            await worker.stop()
    finally:
        for name in ["webhook_events", "revoked_tokens"]:
            await db.drop_collection(prefix + name)
        client.close()
