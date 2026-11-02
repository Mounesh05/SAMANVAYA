"""
Sprint API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from domain.models.sprint import SprintCreate, Sprint
from domain.services.sprint_service import SprintService
from core.dependencies import get_current_user, require_roles

router = APIRouter()
sprint_service = SprintService()


from typing import Optional, List
from fastapi import Query, Body
from domain.services.story_service import StoryService
from domain.models.story import Story

story_service = StoryService()

@router.post("", response_model=Sprint, status_code=201)
@router.post("/", response_model=Sprint, status_code=201, include_in_schema=False)
async def create_sprint(
    sprint_data: SprintCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new sprint."""
    try:
        sprint = await sprint_service.create_sprint(sprint_data)
        return sprint
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create sprint: {str(e)}")


@router.get("", response_model=List[Sprint])
@router.get("/", response_model=List[Sprint], include_in_schema=False)
async def list_sprints(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(get_current_user),
):
    """List all sprints with optional filters."""
    filter_q = {}
    if project_id:
        filter_q["project_id"] = project_id
    if status:
        filter_q["status"] = status
    return await sprint_service.get_all_sprints(filter_q, limit=limit)


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


@router.get("/{sprint_id}/stories", response_model=List[Story])
async def get_sprint_stories(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all stories in a sprint."""
    return await story_service.get_sprint_stories(sprint_id)


@router.put("/{sprint_id}")
async def update_sprint(
    sprint_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    """Update sprint fields."""
    await sprint_service.update_sprint(sprint_id, data)
    sprint = await sprint_service.get_sprint(sprint_id)
    return sprint or {"message": "Updated", "sprint_id": sprint_id}


@router.delete("/{sprint_id}")
async def delete_sprint(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete sprint by ID."""
    await sprint_service.delete_sprint(sprint_id)
    return {"message": "Deleted", "sprint_id": sprint_id}

