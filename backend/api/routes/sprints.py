"""
Sprint API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from domain.models.sprint import SprintCreate, Sprint
from domain.services.sprint_service import SprintService
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission

router = APIRouter()
sprint_service = SprintService()


@router.post("/", response_model=Sprint, status_code=201)
async def create_sprint(
    sprint_data: SprintCreate,
    user: dict = Depends(require_permission(Permission.CREATE_SPRINT)),
):
    """
    Create a new sprint.
    Requires CREATE_SPRINT permission (PM role by default).
    """
    try:
        sprint = await sprint_service.create_sprint(sprint_data)
        return sprint
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create sprint: {str(e)}")


@router.get("/{sprint_id}", response_model=Sprint)
async def get_sprint(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """Get sprint by ID."""
    sprint = await sprint_service.get_sprint(sprint_id)
    
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    
    return sprint


@router.get("/project/{project_id}", response_model=list[Sprint])
async def list_project_sprints(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """List all sprints in a project."""
    sprints = await sprint_service.get_project_sprints(project_id)
    return sprints


@router.get("/project/{project_id}/active", response_model=Sprint)
async def get_active_sprint(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the active sprint for a project."""
    sprint = await sprint_service.get_active_sprint(project_id)
    
    if not sprint:
        raise HTTPException(status_code=404, detail="No active sprint found")
    
    return sprint


@router.get("/{sprint_id}/health")
async def get_sprint_health(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get sprint health: Plan vs Reality.
    
    Returns objective metrics about sprint progress, completion,
    and risk factors calculated by the Intelligence Engine (Layer 5).
    """
    health = await sprint_service.calculate_sprint_health(sprint_id)
    
    if "error" in health:
        raise HTTPException(status_code=404, detail=health["error"])
    
    return health
