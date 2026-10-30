"""
Activity Feed API endpoints.
Project-wide, user, and item-level activity history.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from core.dependencies import get_current_user
from core.authorization import (
    verify_project_access,
    verify_can_view_user_tasks,
    verify_task_access,
    verify_story_access,
)
from repositories.activity_repository import ActivityRepository
from repositories.sprint_repository import SprintRepository

router = APIRouter()
activity_repo = ActivityRepository()
sprint_repo = SprintRepository()


@router.get("/project/{project_id}")
async def get_project_feed(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get paginated activity feed for a project. User must have access to the project."""
    # Verify user has access to this project
    await verify_project_access(user, project_id)
    
    events = await activity_repo.get_project_feed(project_id, limit, skip)
    return {"project_id": project_id, "events": events, "count": len(events)}


@router.get("/user/{user_id}")
async def get_user_feed(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get paginated activity feed for a specific user. Users can only see their own feed unless they're PM/CEO."""
    # Verify user can view this user's feed
    await verify_can_view_user_tasks(user, user_id)
    
    events = await activity_repo.get_user_feed(user_id, limit, skip)
    return {"user_id": user_id, "events": events, "count": len(events)}


@router.get("/me")
async def get_my_feed(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get activity feed for the currently logged-in user."""
    user_id = user.get("employee_id", user.get("id", ""))
    events = await activity_repo.get_user_feed(user_id, limit, skip)
    return {"user_id": user_id, "events": events, "count": len(events)}


@router.get("/item/{item_type}/{item_id}")
async def get_item_history(
    item_type: str,
    item_id: str,
    user: dict = Depends(get_current_user),
):
    """Get full activity history for a specific task, story, PR, or sprint. User must have access to the item."""
    # Verify user has access based on item type
    if item_type == "task":
        await verify_task_access(user, item_id)
    elif item_type == "story":
        await verify_story_access(user, item_id)
    elif item_type == "sprint":
        sprint = await sprint_repo.find_by_id(item_id)
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
        await verify_project_access(user, sprint.get("project_id"))
    # For other types (PR, etc.), currently no specific verification
    # TODO: Add PR and other resource type verification when available
    
    events = await activity_repo.get_item_history(item_type, item_id)
    return {
        "item_type": item_type,
        "item_id": item_id,
        "history": events,
        "count": len(events),
    }
