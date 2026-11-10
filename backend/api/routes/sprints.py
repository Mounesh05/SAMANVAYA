"""
Sprint API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from domain.models.sprint import SprintCreate, Sprint
from domain.services.sprint_service import SprintService
from domain.services.sprint_flow_service import SprintFlowService, SprintTransitionError
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import verify_project_access
from repositories.sprint_repository import SprintRepository

router = APIRouter()
sprint_service = SprintService()
sprint_repo = SprintRepository()
sprint_flow_service = SprintFlowService()


async def _writable_sprint(sprint_id: str, user: dict) -> dict:
    sprint = await sprint_repo.find_by_id(sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await verify_project_access(user, sprint.get("project_id"), require_write=True)
    return sprint


@router.post("/{sprint_id}/start", response_model=Sprint)
async def start_sprint(
    sprint_id: str,
    user: dict = Depends(require_permission(Permission.CREATE_SPRINT)),
):
    """Start a planning sprint: snapshots the committed scope (points and items)
    so scope creep and say/do ratio can be measured. One active sprint per project."""
    await _writable_sprint(sprint_id, user)
    try:
        return await sprint_flow_service.start_sprint(sprint_id)
    except SprintTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{sprint_id}/complete", response_model=Sprint)
async def complete_sprint(
    sprint_id: str,
    user: dict = Depends(require_permission(Permission.CREATE_SPRINT)),
):
    """Complete an active sprint: stores completed points (velocity) and completion %."""
    await _writable_sprint(sprint_id, user)
    try:
        return await sprint_flow_service.complete_sprint(sprint_id)
    except SprintTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{sprint_id}/flow")
async def get_sprint_flow(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """Flow metrics: completion, scope creep, velocity, cycle/lead time, blocked
    time, Little's Law, burndown and a Monte Carlo completion forecast."""
    sprint = await sprint_repo.find_by_id(sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await verify_project_access(user, sprint.get("project_id"))
    return await sprint_flow_service.flow_report(sprint_id)


@router.post("/", response_model=Sprint, status_code=201)
async def create_sprint(
    sprint_data: SprintCreate,
    user: dict = Depends(require_permission(Permission.CREATE_SPRINT)),
):
    """
    Create a new sprint.
    Requires CREATE_SPRINT permission (PM role by default).
    """
    # Authorization: verify user has write access to the project
    await verify_project_access(user, sprint_data.project_id, require_write=True)
    
    try:
        sprint = await sprint_service.create_sprint(sprint_data)
        return sprint
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


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
