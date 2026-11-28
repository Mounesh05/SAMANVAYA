"""Recover approval continuations from the immutable reviewed revision in MongoDB."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

logger = logging.getLogger(__name__)


async def dispatch_page(workflow, collection, revision_id=None):
    now = datetime.now(timezone.utc)
    query = {"status": "APPROVED", "continuation.status": {"$in": ["pending", "running"]},
             "continuation.ready_at": {"$lte": now.isoformat()}}
    if revision_id:
        query.update(revision_id)
    token = uuid.uuid4().hex
    doc = await collection.find_one_and_update(query, {"$set": {
        "continuation.status": "running", "continuation.claim": token,
        "continuation.ready_at": (now + timedelta(minutes=3)).isoformat()}},
        sort=[("continuation.ready_at", 1)], return_document=ReturnDocument.AFTER)
    if not doc:
        return
    key = "contract_id" if "contract_id" in doc else "source_id"
    identity = {key: doc[key], "status": "APPROVED", "continuation.claim": token,
                "organization_id": doc["organization_id"], "project_id": doc["project_id"]}
    try:
        cursor, _ = await asyncio.wait_for(workflow.continuation_page(doc, doc["continuation"]["cursor"]), 120)
        update = {"continuation.status": "completed" if cursor is None else "pending",
                  "continuation.cursor": cursor or "", "continuation.ready_at": now.isoformat()}
    except Exception as error:
        update = {"continuation.status": "pending", "continuation.error": type(error).__name__,
                  "continuation.ready_at": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()}
        logger.warning("Approval continuation deferred for %s (%s)", doc[key], type(error).__name__)
    await collection.update_one(identity, {"$set": update, "$unset": {"continuation.claim": ""}})


async def recover(workflow):
    """A pending job has never claimed execution. Running workers are never replayed."""
    for name in ("algorithm_function_contracts", "algorithm_requirement_sources"):
        await dispatch_page(workflow, workflow.collection(name))
    runs = workflow.collection("code_quality_runs")
    pending = await runs.find({"kind": "pr_algorithm_intelligence", "approval_continuation": True,
                               "status": "pending"}).sort("created_at", 1).limit(8).to_list(8)
    for doc in pending:
        current = await workflow.collection("pull_requests").find_one({"id": doc["pr_id"],
            "project_id": doc["project_id"], "head_sha": doc["head_sha"], "status": "open",
            "algorithm_intelligence_run_id": doc["run_id"]})
        if current:
            await runs.update_one({"run_id": doc["run_id"], "status": "pending"},
                {"$set": {"lease_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=8)).isoformat()}})
            await workflow.execute(doc["run_id"])


async def run_recovery():
    from domain.services.github_api_service import GitHubAPIService
    from domain.services.pr_algorithm_intelligence_service import PRAlgorithmIntelligenceService
    while True:
        try:
            await recover(PRAlgorithmIntelligenceService(GitHubAPIService()))
        except Exception as error:
            logger.warning("Algorithm approval recovery deferred (%s)", type(error).__name__)
        await asyncio.sleep(10)
