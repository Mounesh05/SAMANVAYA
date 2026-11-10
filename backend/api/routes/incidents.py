"""
Incident endpoints (production problems).

Create / update need the CREATE_INCIDENT permission (DevOps and CEO by default)
plus write access to the project; reading needs project access.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.authorization import get_accessible_project_ids, verify_project_access
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from domain.models.incident import Incident, IncidentCreate, IncidentUpdate
from domain.services.incident_service import IncidentError, IncidentService

router = APIRouter()
incident_service = IncidentService()

STATUS_PATTERN = "^(open|investigating|resolved|closed)$"


@router.post("/", response_model=Incident, status_code=201)
async def create_incident(
    data: IncidentCreate,
    user: dict = Depends(require_permission(Permission.CREATE_INCIDENT)),
):
    """Report an incident. Link `caused_by_deployment_id` when a deployment caused it."""
    await verify_project_access(user, data.project_id, require_write=True)
    try:
        return await incident_service.create(data, created_by=user.get("employee_id"))
    except IncidentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/")
async def list_incidents(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern=STATUS_PATTERN),
    user: dict = Depends(get_current_user),
):
    """Incidents of one project, or of every project the user can access."""
    if project_id:
        await verify_project_access(user, project_id)
        project_ids = [project_id]
    else:
        project_ids = await get_accessible_project_ids(user)
    incidents = await incident_service.list_for_projects(project_ids, status)
    return {"incidents": incidents, "total": len(incidents)}


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, user: dict = Depends(get_current_user)):
    incident = await incident_service.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    await verify_project_access(user, incident["project_id"])
    return incident


@router.patch("/{incident_id}", response_model=Incident)
async def update_incident(
    incident_id: str,
    data: IncidentUpdate,
    user: dict = Depends(require_permission(Permission.CREATE_INCIDENT)),
):
    """Update an incident; status moves open -> investigating -> resolved -> closed."""
    incident = await incident_service.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    await verify_project_access(user, incident["project_id"], require_write=True)
    try:
        return await incident_service.update(incident_id, data)
    except IncidentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError:
        raise HTTPException(status_code=404, detail="Incident not found")
