"""Project-scoped lifecycle of read-only production release gate credentials."""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError

from core.audit import AuditAction, log_audit
from core.authorization import verify_project_access
from core.database import col
from core.dependencies import require_permission
from core.permissions import Permission
from domain.services.ai_evidence_service import _repository

router = APIRouter()
manage_gate = require_permission(Permission.RECORD_RELEASE_DECISION)


class GateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["issue", "revoke"]
    version: int = Field(ge=0, strict=True)
    repository: str = Field(min_length=3, max_length=201)


async def _scope(project_id, user):
    org = user.get("org_id")
    if not isinstance(org, str) or not org or user.get("organization_id", org) != org:
        raise HTTPException(403, "Current organization required")
    await verify_project_access(user, project_id)
    projects = await col("projects").find({"id": project_id},
        {"id": 1, "org_id": 1, "organization_id": 1, "status": 1}).limit(2).to_list(2)
    owned = [p for p in projects if p.get("id") == project_id and p.get("org_id") == org
             and p.get("organization_id", org) == org]
    if len(owned) != 1:
        raise HTTPException(403, "Project outside current organization")
    active = len(projects) == 1 and owned[0].get("status", "active") == "active"
    return {"_id": project_id, "organization_id": org}, active


def _public(row):
    return {field: row.get(field) for field in ("repository", "environment", "enabled", "version", "updated_at", "updated_by")}


@router.get("/{project_id}/release-gate")
async def gate_settings(project_id: str, response: Response, user: dict = Depends(manage_gate)):
    response.headers["Cache-Control"] = "no-store"
    scope, active = await _scope(project_id, user)
    row = await col("project_release_gates").find_one(scope, {"token_sha256": 0})
    try:
        owner, name = await _repository(project_id, scope["organization_id"])
        linked_repository = f"{owner}/{name}".casefold()
    except HTTPException as error:
        if error.status_code != 409:
            raise
        linked_repository = None
    return {**_public(row or {"environment": "production", "enabled": False, "version": 0}),
            "linked_repository": linked_repository if active else None}


@router.post("/{project_id}/release-gate")
async def change_gate(project_id: str, change: GateChange, response: Response, user: dict = Depends(manage_gate)):
    response.headers["Cache-Control"] = "no-store"
    scope, active = await _scope(project_id, user)
    issue = change.action == "issue"
    repository = change.repository.casefold()
    if issue:
        if not active:
            raise HTTPException(409, "Only an active, unambiguous project can issue credentials.")
        owner, name = await _repository(project_id, scope["organization_id"])
        if f"{owner}/{name}".casefold() != repository:
            raise HTTPException(409, "Linked repository changed. Refresh the configuration.")
    token = secrets.token_urlsafe(48) if issue else None
    updates = {"enabled": issue, "repository": repository, "environment": "production",
               "version": change.version + 1, "updated_by": user["employee_id"],
               "updated_at": datetime.now(timezone.utc).isoformat()}
    changes = {"$set": updates}
    query = {**scope, "version": change.version}
    if issue:
        changes["$set"] = {**updates, "token_sha256": hashlib.sha256(token.encode()).hexdigest()}
    else:
        query.update(enabled=True, repository=repository)
        changes["$unset"] = {"token_sha256": ""}
    try:
        result = await col("project_release_gates").update_one(query, changes, upsert=issue and change.version == 0)
    except DuplicateKeyError:
        raise HTTPException(409, "Credential changed. Refresh before trying again.") from None
    if not result.matched_count and result.upserted_id is None:
        raise HTTPException(409, "Credential changed. Refresh before trying again.")
    await log_audit(AuditAction.SETTINGS_CHANGED, user, resource_type="release_gate", resource_id=project_id,
                    details={"action": change.action, "repository": repository, "version": updates["version"],
                             "organization_id": scope["organization_id"]})
    return {**_public(updates), **({"token": token} if issue else {})}
