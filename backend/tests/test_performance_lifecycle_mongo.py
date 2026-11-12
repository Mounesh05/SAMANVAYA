"""Opt-in real Mongo primary-key arbitration; owns and drops one UUID collection."""

import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.getenv("SAMANVAYA_MONGO_TESTS") != "1", reason="Opt-in real Mongo check")]


async def test_native_mongo_arbitrates_two_writers_at_the_same_revision(monkeypatch):
    from domain.models.performance_evidence import canonical_digest
    from domain.models.performance_lifecycle import AssessmentActionRequest
    from domain.services import performance_artifact_store as store
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    client = AsyncIOMotorClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=4000)
    database = client[os.environ["DB_NAME"]]
    collection_name = "test_scoring_phase5_" + uuid.uuid4().hex
    collection = database[collection_name]
    try:
        await client.admin.command("ping")
        monkeypatch.setattr(store, "col", lambda name: collection)
        identity = "PA-" + uuid.uuid4().hex
        root = await store._write("performance_assessment_event", dict(assessment_id=identity,
            revision=1, predecessor_digest=None, state="DRAFT", request_id="create", request_digest="0" * 64,
            reason="Synthetic native Mongo race", run_id="synthetic", measurement=None),
            {"organization_id": "synthetic-org", "project_id": "synthetic-project", "employee_id": "synthetic-subject"},
            "synthetic-manager", identity + ":000001")
        bodies = [AssessmentActionRequest(expected_digest=canonical_digest(root), request_id=action.lower(),
            action=action, reason="Two writers saw the same immutable predecessor") for action in ("COLLECT", "CANCEL")]
        results = await asyncio.gather(*(AssessmentLifecycleService()._append([root], body,
            {"employee_id": "synthetic-manager"}, state) for body, state in zip(bodies, ("EVIDENCE_COLLECTING", "CANCELLED"))),
            return_exceptions=True)
        assert len([r for r in results if isinstance(r, dict)]) == 1
        assert len([r for r in results if isinstance(r, HTTPException) and r.status_code == 409]) == 1
        assert await collection.count_documents({}) == 2
        second = await collection.find_one({"id": identity + ":000002"})
        assert store._verify(second, "performance_assessment_event")["payload"]["predecessor_digest"] == canonical_digest(root)
    finally:
        await database.drop_collection(collection_name)
        client.close()
