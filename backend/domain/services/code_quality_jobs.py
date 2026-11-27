"""CQ-05: durable intake and recovery for code-quality analysis runs.

The run document in MongoDB is the queue; FastAPI background tasks are only a
fast path. A run executes only after an atomic claim (pending -> running) that
records this process and a lease. A heartbeat renews the lease while the run
works, and every result write is fenced on that claim.

Recovery (at startup and every RECOVERY_INTERVAL_SECONDS):
  * pending runs that no process claimed (e.g. the server stopped right after
    accepting the request) are started again from their stored request;
  * running runs whose lease expired (the process died mid-run) are marked
    failed and NOT replayed, because tools may have stored partial findings;
  * pending/running runs past their work deadline are marked failed.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.config import settings

logger = logging.getLogger(__name__)

INSTANCE_ID = uuid4().hex
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 30
RECOVERY_INTERVAL_SECONDS = 60
PENDING_GRACE_SECONDS = 30
RECOVERY_BATCH = 10
INTERRUPTED = "Analysis was interrupted (server restart or crash) and was not replayed. Start a new analysis."
DEADLINE = "Worker deadline expired before a result was recorded."

_slots: asyncio.Semaphore | None = None
_queued: set[str] = set()


def _now():
    return datetime.now(timezone.utc)


def _iso(value=None):
    return (value or _now()).isoformat()


def slots() -> asyncio.Semaphore:
    """Per-process bound on concurrently executing analyses."""
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(settings.CODE_QUALITY_MAX_CONCURRENT_RUNS)
    return _slots


def owned(run_id):
    """Filter that matches a run only while this process still owns its claim."""
    return {"run_id": run_id, "claimed_by": INSTANCE_ID, "status": "running"}


def active_filter(org_id):
    return {"org_id": org_id, "kind": {"$exists": False}, "status": {"$in": ["pending", "running"]},
            "work_deadline": {"$gt": _iso()}}


async def claim(collection, run_id) -> bool:
    """Atomically take a pending run within its deadline. Exactly one process wins."""
    now = _now()
    result = await collection.update_one(
        {"run_id": run_id, "status": {"$in": ["pending", None]},
         "$or": [{"work_deadline": {"$gt": _iso(now)}}, {"work_deadline": {"$exists": False}}]},
        {"$set": {"status": "running", "claimed_by": INSTANCE_ID, "claimed_at": _iso(now),
                  "lease_expires_at": _iso(now + timedelta(seconds=LEASE_SECONDS))},
         "$inc": {"claim_count": 1}})
    return result.matched_count == 1


async def renew(collection, run_id) -> bool:
    result = await collection.update_one(owned(run_id), {"$set": {
        "lease_expires_at": _iso(_now() + timedelta(seconds=LEASE_SECONDS))}})
    return result.matched_count == 1


async def run_with_lease(collection, run_id, work):
    """Run ``work()`` while renewing the lease; cancel it if ownership is lost."""
    task = asyncio.create_task(work())

    async def heartbeat():
        while not task.done():
            await asyncio.sleep(HEARTBEAT_SECONDS)
            if not task.done() and not await renew(collection, run_id):
                logger.warning("Code-quality run %s lost its lease; stopping", run_id)
                task.cancel()
                return

    beat = asyncio.create_task(heartbeat())
    try:
        return await task
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)


def stored_request(body, actor_id, pinned_revision, expected_org):
    """What recovery needs to start a never-claimed run again."""
    return {"body": body.model_dump(mode="json"), "actor_id": actor_id,
            "pinned_revision": pinned_revision, "expected_org": expected_org}


async def recover_once(collection, dispatch):
    """One recovery pass. ``dispatch(run)`` starts a stored, never-claimed run."""
    now = _now()
    failed = {"status": "failed", "quality_analysis_status": "failed", "completed_at": _iso(now)}
    interrupted = await collection.update_many(
        {"kind": {"$exists": False}, "status": "running", "claimed_by": {"$exists": True},
         "lease_expires_at": {"$lt": _iso(now)}},
        {"$set": {**failed, "error": INTERRUPTED}})
    expired = await collection.update_many(
        {"kind": {"$exists": False}, "status": {"$in": ["pending", "running"]}, "work_deadline": {"$lte": _iso(now)}},
        {"$set": {**failed, "error": DEADLINE}})
    rows = await collection.find(
        {"kind": {"$exists": False}, "status": "pending", "request": {"$exists": True},
         "created_at": {"$lt": _iso(now - timedelta(seconds=PENDING_GRACE_SECONDS))},
         "work_deadline": {"$gt": _iso(now)}},
        {"_id": 0}).sort("created_at", 1).limit(RECOVERY_BATCH).to_list(RECOVERY_BATCH)
    started = 0
    for run in rows:
        if run["run_id"] in _queued:
            continue
        dispatch(run)
        started += 1
    if interrupted.modified_count or expired.modified_count or started:
        logger.info("Code-quality recovery: %d interrupted, %d expired, %d restarted",
                    interrupted.modified_count, expired.modified_count, started)
    return {"interrupted": interrupted.modified_count, "expired": expired.modified_count, "restarted": started}


class RecoveryLoop:
    def __init__(self, collection_factory, dispatch, interval=RECOVERY_INTERVAL_SECONDS):
        self._collection_factory = collection_factory
        self._dispatch = dispatch
        self._interval = interval
        self._task = None

    async def _loop(self):
        while True:
            try:
                await recover_once(self._collection_factory(), self._dispatch)
            except Exception as error:  # keep recovering after transient database errors
                logger.warning("Code-quality recovery pass failed (%s)", type(error).__name__)
            await asyncio.sleep(self._interval)

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="code-quality-recovery")

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None


def mark_queued(run_id):
    _queued.add(run_id)


def mark_done(run_id):
    _queued.discard(run_id)
