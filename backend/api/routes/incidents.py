"""
Incident API (CR-001).

- Report: anyone holding CREATE_INCIDENT (Developer, DevOps, CEO), for a project
  they can access. Reporting does not assign or triage the incident.
- Read: VIEW_INCIDENTS holders (DevOps, Lead, CEO) see incidents in the
  projects they can access; reporters without it see only their own reports.

Triage and resolution (status changes, assignment) are DevOps work and are
specified in CR-003.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.authorization import get_accessible_project_ids, has_global_access, verify_project_access
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission, get_user_permissions
from domain.models.incident import Incident, IncidentCreate
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
    }
    await IncidentRepository().insert(dict(document))
    return Incident(**document)


@router.get("/", response_model=List[Incident])
async def list_incidents(
    project_id: Optional[str] = Query(None, max_length=100),
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
    rows = await IncidentRepository().list_for(query)
    return [Incident(**row) for row in rows]
