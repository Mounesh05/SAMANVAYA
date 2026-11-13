"""
Incident API (CR-001).

- Report: anyone holding CREATE_INCIDENT (Developer, DevOps, CEO), for a project
  they can access. Reporting does not assign or triage the incident.
- Read: VIEW_INCIDENTS holders (DevOps, Lead, CEO) see incidents in the
  projects they can access; reporters without it see only their own reports.

- Triage (CR-014): TRIAGE_INCIDENT holders (DevOps, Lead, PM) acknowledge,
  assign, re-grade, resolve and close incidents in projects they can access.
  The CEO watches; reporters follow their own reports.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.audit import AuditAction, log_audit
from core.authorization import (get_accessible_project_ids, has_global_access, project_member_ids,
                                verify_project_access)
from core.database import col
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission, get_user_permissions
from domain.models.incident import (NEEDS_POSTMORTEM, OWNER_ROLES, TRANSITIONS, Incident, IncidentCreate,
                                    IncidentUpdate)
from repositories.incident_repository import IncidentRepository

router = APIRouter()


def _permissions(user: dict):
    return get_user_permissions(
        user.get("role", user.get("organizational_role", "")),
        user.get("is_admin", False),
        user.get("designation"),
    )


@router.post("/", response_model=Incident, status_code=201)
async def report_incident(
    incident: IncidentCreate,
    user: dict = Depends(require_permission(Permission.CREATE_INCIDENT)),
):
    """Report an incident in a project the reporter can access."""
    await verify_project_access(user, incident.project_id)
    document = {
        **incident.model_dump(),
        "id": f"INC-{uuid.uuid4().hex[:8].upper()}",
        "status": "open",
        "reporter_id": user["employee_id"],
        "reporter_name": user.get("name", user["employee_id"]),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "timeline": [],
    }
    document["timeline"] = [{"at": document["created_at"], "by": user["employee_id"],
                             "by_name": document["reporter_name"], "action": "reported", "changes": {}}]
    await IncidentRepository().insert(dict(document))
    return Incident(**document)


@router.get("/", response_model=List[Incident])
async def list_incidents(
    project_id: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None, pattern="^(open|investigating|resolved|closed)$"),
    user: dict = Depends(get_current_user),
):
    """List incidents the caller may see, newest first."""
    permissions = _permissions(user)
    query: dict = {}
    if Permission.VIEW_INCIDENTS in permissions:
        if project_id:
            await verify_project_access(user, project_id)
            query["project_id"] = project_id
        elif not has_global_access(user):
            query["project_id"] = {"$in": await get_accessible_project_ids(user)}
    elif Permission.CREATE_INCIDENT in permissions:
        query["reporter_id"] = user["employee_id"]
        if project_id:
            query["project_id"] = project_id
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions to view incidents")
    if isinstance(status, str) and status:  # also safe when called directly
        query["status"] = status
    rows = await IncidentRepository().list_for(query)
    return [Incident(**row) for row in rows]


# ── CR-014: one incident, and triage ────────────────────────────────────────

async def _visible_incident(user: dict, incident_id: str) -> dict:
    incident = await IncidentRepository().find_one({"id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if Permission.VIEW_INCIDENTS in _permissions(user):
        await verify_project_access(user, incident["project_id"])
        return incident
    if incident.get("reporter_id") == user.get("employee_id"):
        return incident
    raise HTTPException(status_code=403, detail="You can't view this incident")


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, user: dict = Depends(get_current_user)):
    """One incident with its owner, timeline and resolution."""
    return Incident(**await _visible_incident(user, incident_id))


async def _owner(incident: dict, assignee_id: str) -> dict:
    person = await col("users").find_one({"employee_id": assignee_id}, {"_id": 0})
    if not person or person.get("is_active", True) is False:
        raise HTTPException(status_code=422, detail="The owner must be an active employee")
    if (person.get("role") or "").upper() not in OWNER_ROLES:
        raise HTTPException(status_code=422, detail="The owner must be a Developer, DevOps, Lead or QA")
    if assignee_id not in await project_member_ids([incident["project_id"]]):
        raise HTTPException(status_code=422, detail="The owner must be a member of the incident's project")
    return person


@router.patch("/{incident_id}", response_model=Incident)
async def triage_incident(
    incident_id: str,
    update: IncidentUpdate,
    user: dict = Depends(require_permission(Permission.TRIAGE_INCIDENT)),
):
    """Acknowledge, assign, re-grade, resolve, close or reopen an incident."""
    incident = await IncidentRepository().find_one({"id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    await verify_project_access(user, incident["project_id"])
    if incident.get("status") == "closed":
        raise HTTPException(status_code=409, detail="A closed incident can't be changed")

    now = datetime.now(timezone.utc).isoformat()
    fields = update.model_fields_set
    changes, data = {}, {}

    def change(name, new):
        old = incident.get(name)
        if new != old:
            changes[name] = [old, new]
            data[name] = new

    if "severity" in fields and update.severity:
        change("severity", update.severity)
    if "assignee_id" in fields:
        if update.assignee_id:
            owner = await _owner(incident, update.assignee_id)
            change("assignee_id", update.assignee_id)
            data["assignee_name"] = owner.get("name")
        else:
            change("assignee_id", None)
            data["assignee_name"] = None
    if "resolution_summary" in fields and update.resolution_summary is not None:
        change("resolution_summary", update.resolution_summary.strip() or None)
    if "postmortem" in fields and update.postmortem is not None:
        change("postmortem", update.postmortem.strip() or None)

    if update.status and update.status != incident.get("status"):
        current = incident.get("status", "open")
        if update.status not in TRANSITIONS.get(current, set()):
            raise HTTPException(status_code=409, detail=f"An incident can't move from {current} to {update.status}")
        merged = {**incident, **data}
        if update.status == "resolved" and not merged.get("resolution_summary"):
            raise HTTPException(status_code=422, detail="Add a resolution summary to resolve the incident")
        if update.status == "closed" and merged.get("severity") in NEEDS_POSTMORTEM and not merged.get("postmortem"):
            raise HTTPException(status_code=422, detail="High and critical incidents need a post-incident review before closing")
        change("status", update.status)
        stamp = {"investigating": "acknowledged_at", "resolved": "resolved_at", "closed": "closed_at"}[update.status]
        if update.status == "investigating" and current == "resolved":
            data["resolved_at"] = None  # reopened
        elif stamp != "acknowledged_at" or not incident.get("acknowledged_at"):
            data[stamp] = now

    note = (update.note or "").strip() or None
    if not changes and not note:
        raise HTTPException(status_code=400, detail="Nothing to change")
    action = ("reopened" if changes.get("status") == ["resolved", "investigating"] else
              {"investigating": "acknowledged", "resolved": "resolved", "closed": "closed"}.get(
                  (changes.get("status") or [None, None])[1], "updated" if changes else "noted"))
    entry = {"at": now, "by": user["employee_id"], "by_name": user.get("name", user["employee_id"]),
             "action": action, "changes": changes, "note": note}
    await col("incidents").update_one({"id": incident_id}, {"$set": data, "$push": {"timeline": entry}})
    await log_audit(action=AuditAction.INCIDENT_UPDATED, actor=user, resource_type="incident",
                    resource_id=incident_id, details={"action": action, "changes": changes, "note": note,
                                                      "project_id": incident["project_id"]})
    return Incident(**await IncidentRepository().find_one({"id": incident_id}))
