"""
Sprint API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from domain.models.sprint import SprintCreate, Sprint
from domain.services.sprint_service import SprintService
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import verify_project_access
from repositories.sprint_repository import SprintRepository

router = APIRouter()
sprint_service = SprintService()
sprint_repo = SprintRepository()


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
    """Get sprint by ID. User must have access to the sprint's project."""
    # Fetch sprint to get project_id
    sprint = await sprint_repo.find_by_id(sprint_id)
    
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    
    # Verify user has access to the sprint's project
    await verify_project_access(user, sprint.get("project_id"))
    
    return sprint


@router.get("/project/{project_id}", response_model=list[Sprint])
async def list_project_sprints(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """List all sprints in a project. User must have access to the project."""
    # Verify user has access to this project
    await verify_project_access(user, project_id)
    
    sprints = await sprint_service.get_project_sprints(project_id)
    return sprints


@router.get("/project/{project_id}/active", response_model=Sprint)
async def get_active_sprint(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the active sprint for a project. User must have access to the project."""
    # Verify user has access to this project
    await verify_project_access(user, project_id)
    
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
    User must have access to the sprint's project.
    """
    # Fetch sprint to get project_id
    sprint = await sprint_repo.find_by_id(sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    
    # Verify user has access to the sprint's project
    await verify_project_access(user, sprint.get("project_id"))
    
    health = await sprint_service.calculate_sprint_health(sprint_id)
    
    if "error" in health:
        raise HTTPException(status_code=404, detail=health["error"])
    
    return health
