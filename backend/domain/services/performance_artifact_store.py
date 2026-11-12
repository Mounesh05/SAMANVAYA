"""Shared server-HMAC artifact envelope in existing ai_runs; not personal signatures."""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from core.config import settings
from core.database import col
from domain.models.performance_evidence import canonical_digest


def _signature(record):
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), canonical_digest(record).encode("ascii"), hashlib.sha256).hexdigest()


def _context(scope):
    return {"organization_id": scope.organization_id, "project_id": scope.project_id, "employee_id": scope.employee_id}


async def _write(kind, payload, context, actor, artifact_id=None):
    key = artifact_id or "PC-" + uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    record = {"schema_version": "performance-claim-artifact-v1", "signature_method": "HMAC-SHA256-v1",
              "id": key, "kind": kind, "context": context, "payload": payload,
              "created_by": actor, "created_at": now}
    document = {"_id": key, "id": key, "agent_type": kind, "input_data": {"context": context},
        "output_data": record, "signature": _signature(record), "status": "completed", "model_name": "advisory",
        "triggered_by": actor, "created_at": now, "updated_at": now}
    try:
        await col("ai_runs").insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(409, "A concurrent review already created this revision") from None
    return record


def _verify(document, kind):
    record = (document or {}).get("output_data")
    signature = (document or {}).get("signature")
    if (not isinstance(record, dict) or record.get("schema_version") != "performance-claim-artifact-v1"
            or record.get("signature_method") != "HMAC-SHA256-v1"
            or record.get("kind") != kind or record.get("id") != document.get("id")
            or document.get("agent_type") != kind or not isinstance(signature, str)
            or not hmac.compare_digest(signature, _signature(record))):
        raise HTTPException(409, "Performance artifact integrity or server authority could not be verified")
    return record


async def _read(key, kind):
    doc = await col("ai_runs").find_one({"id": key, "agent_type": kind}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Performance artifact not found")
    return _verify(doc, kind)
