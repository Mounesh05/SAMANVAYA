"""Record human QA verification and release disposition for scoped task evidence."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError

from core.database import col
from core.permissions import Permission, get_user_permissions
from domain.models.performance_evidence import canonical_digest


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["verify_qa", "hold", "approve"]
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    decision_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=1000)


def _scope(status, user):
    org_id = status.get("organization_id")
    if not org_id or org_id != user.get("org_id") or not user.get("employee_id"):
        raise HTTPException(403, "Organization membership is required")
    return {"organization_id": org_id, "project_id": status["project_id"], "task_id": status["task_id"]}


def _evidence(status):
    snapshot = jsonable_encoder({
        key: status.get(key) for key in (
            "revision", "revision_kind", "implementation", "qa", "readiness", "requirement",
        )
    })
    # Transport retries can refresh a receipt timestamp without changing the
    # workflow attempt, artifact identity or recorded test result.
    for run in snapshot["qa"].get("runs", []):
        run.pop("received_at", None)
    # Two reads can enumerate the same source rows in different orders.
    for section, field in (("implementation", "pull_requests"), ("qa", "runs")):
        if field in snapshot[section]:
            snapshot[section][field].sort(key=canonical_digest)
    return snapshot


def _present(record, evidence_id):
    if not record:
        return None
    return {**record, "is_current": record["evidence_id"] == evidence_id}


def _permissions(user):
    return get_user_permissions(user.get("role") or user.get("organizational_role") or "",
                                user.get("is_admin", False), user.get("designation"))


def _ready_for_qa(status):
    return (status["qa"]["status"] == "passed" and bool(status["qa"]["runs"])
            and status["implementation"]["status"] == "merged"
            and status.get("revision_kind") == "merge_commit"
            and status["readiness"]["status"] == "awaiting_review")


def _context(status, user, latest, evidence_id):
    verification = _present(latest.get("qa_verification"), evidence_id)
    release = _present(latest.get("release_decision"), evidence_id)
    permissions = _permissions(user)
    has_reports = _ready_for_qa(status)
    has_revision = bool(status["revision"])
    verified = bool(verification and verification["is_current"])
    can_decide = has_revision and Permission.RECORD_RELEASE_DECISION in permissions
    return {
        "release_decision": release,
        "qa_verification": verification,
        "decision_version": canonical_digest([_scope(status, user), evidence_id, latest.get("_id")]),
        "can_decide": can_decide,
        "can_verify_qa": has_revision and Permission.SIGN_OFF_WORK in permissions and has_reports and not verified,
        "can_approve": can_decide and has_reports and verified and verification["actor_id"] != user["employee_id"],
    }


async def _latest(scope):
    return await col("release_decisions").find_one(scope, sort=[("sequence", -1)]) or {}


async def decision_context(status, user):
    """Decorate a delivery read that has already authorized access to this task."""
    latest = await _latest(_scope(status, user))
    return _context(status, user, latest, canonical_digest(_evidence(status)))


async def has_current_release_approval(status):
    """Read human decisions for the precise evidence now visible to the gate."""
    if not _ready_for_qa(status):
        return False
    scope = {key: status[key] for key in ("organization_id", "project_id", "task_id")}
    latest = await _latest(scope)
    evidence_id = canonical_digest(_evidence(status))
    actors = []
    for field, action in (("qa_verification", "verify_qa"), ("release_decision", "approve")):
        record = latest.get(field)
        if (not isinstance(record, dict) or record.get("decision") != action
                or record.get("revision") != status["revision"] or record.get("evidence_id") != evidence_id
                or not isinstance(record.get("actor_id"), str) or not record["actor_id"].strip()):
            return False
        actors.append(record["actor_id"])
    return actors[0] != actors[1]


async def record_decision(status, user, request: DecisionRequest):
    """Append exactly one decision against the revision and history the caller saw."""
    scope = _scope(status, user)
    required = Permission.SIGN_OFF_WORK if request.decision == "verify_qa" else Permission.RECORD_RELEASE_DECISION
    if required not in _permissions(user):
        raise HTTPException(403, "Your role cannot record this decision")
    if request.revision != status["revision"]:
        raise HTTPException(409, "The revision changed. Refresh the task evidence.")

    evidence = _evidence(status)
    evidence_id = canonical_digest(evidence)
    collection = col("release_decisions")
    await collection.create_index([("organization_id", 1), ("project_id", 1), ("task_id", 1), ("sequence", -1)])
    latest = await _latest(scope)
    context = _context(status, user, latest, evidence_id)
    event_key = canonical_digest([scope, user["employee_id"], request.model_dump(), evidence_id])
    if latest.get("event_key") == event_key:
        return context
    if context["decision_version"] != request.decision_version:
        raise HTTPException(409, "Evidence or a human decision changed. Review the latest record.")
    if request.decision == "verify_qa" and not context["can_verify_qa"]:
        raise HTTPException(409, "QA verification requires a merged revision with passing reports awaiting review.")
    if request.decision == "approve" and not context["can_approve"]:
        raise HTTPException(409, "Approval requires passing reports and independent QA verification for this evidence.")

    record = {
        "decision": request.decision,
        "reason": request.reason,
        "revision": request.revision,
        "evidence_id": evidence_id,
        "actor_id": user["employee_id"],
        "actor_name": user.get("name") or user["employee_id"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    sequence = latest.get("sequence", 0) + 1
    # The unique Mongo _id elects one successor for every observed decision version.
    entry = {
        **scope,
        "_id": canonical_digest([scope, sequence]),
        "sequence": sequence,
        "event_key": event_key,
        "record": record,
        "evidence": evidence,
        "release_decision": latest.get("release_decision"),
        "qa_verification": latest.get("qa_verification"),
    }
    field = "qa_verification" if request.decision == "verify_qa" else "release_decision"
    entry[field] = record
    try:
        await collection.insert_one(entry)
    except DuplicateKeyError:
        winner = await _latest(scope)
        if winner.get("event_key") == event_key:
            return _context(status, user, winner, evidence_id)
        raise HTTPException(409, "Another reviewer recorded a decision. Refresh before continuing.") from None
    return _context(status, user, entry, evidence_id)
