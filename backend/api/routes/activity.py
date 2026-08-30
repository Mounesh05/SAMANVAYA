"""
Activity Feed API endpoints.
Project-wide, user, and item-level activity history.
"""

from fastapi import APIRouter, Depends, Query
from core.dependencies import get_current_user
from repositories.activity_repository import ActivityRepository

router = APIRouter()
activity_repo = ActivityRepository()


@router.get("/project/{project_id}")
async def get_project_feed(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get paginated activity feed for a project."""
    events = await activity_repo.get_project_feed(project_id, limit, skip)
    return {"project_id": project_id, "events": events, "count": len(events)}


@router.get("/user/{user_id}")
async def get_user_feed(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get paginated activity feed for a specific user."""
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
    """Get full activity history for a specific task, story, PR, or sprint."""
    events = await activity_repo.get_item_history(item_type, item_id)
    return {
        "item_type": item_type,
        "item_id": item_id,
        "history": events,
        "count": len(events),
    }
