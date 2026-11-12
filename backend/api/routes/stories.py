"""
Story API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from domain.models.story import StoryCreate, Story
from domain.services.story_service import StoryService
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import (
    verify_story_access,
    verify_project_access,
    verify_can_view_user_tasks,
    verify_story_status_update_access,
    verify_work_item_creation,
)
from repositories.sprint_repository import SprintRepository

router = APIRouter()
story_service = StoryService()
sprint_repo = SprintRepository()


@router.post("/", response_model=Story, status_code=201)
async def create_story(
    story_data: StoryCreate,
    user: dict = Depends(require_permission(Permission.CREATE_STORY)),
):
    """
    Create a new user story.
    Requires CREATE_STORY permission (DEVELOPER, LEAD, PM roles by default).

    Project managers (write access) add the story straight to the backlog.
    Contributors (e.g. DEVELOPER) can only propose a DRAFT story assigned to
    themselves in an assigned project; a Lead/PM accepts it (ACCEPT_STORY).
    """
    is_manager = await verify_work_item_creation(user, story_data.project_id, story_data.assignee_id)

    try:
        return await story_service.create_story(
            story_data,
            draft=not is_manager,
            proposed_by=None if is_manager else user.get("employee_id"),
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{story_id}", response_model=Story)
async def get_story(
    story_id: str,
    user: dict = Depends(get_current_user),
):
    """Get story by ID. User must have access to the story's project."""
    # Verify user has access to this story's project
    await verify_story_access(user, story_id)
    
    story = await story_service.get_story(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    return story


@router.get("/sprint/{sprint_id}", response_model=list[Story])
async def list_sprint_stories(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """List all stories in a sprint. User must have access to the sprint's project."""
    # Fetch sprint to get project_id
    sprint = await sprint_repo.find_by_id(sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    
    # Verify user has access to the sprint's project
    await verify_project_access(user, sprint.get("project_id"))
    
    stories = await story_service.get_sprint_stories(sprint_id)
    return stories


@router.get("/assignee/{assignee_id}", response_model=list[Story])
async def list_assignee_stories(
    assignee_id: str,
    user: dict = Depends(get_current_user),
):
    """List all stories assigned to a developer. Users can only see their own stories unless they're PM/CEO."""
    # Verify user can view this assignee's stories
    await verify_can_view_user_tasks(user, assignee_id)
    
    stories = await story_service.get_assignee_stories(assignee_id)
    return stories


@router.patch("/{story_id}/status")
async def update_story_status(
    story_id: str,
    status: str = Query(..., pattern="^(todo|in_progress|review|done)$"),
    user: dict = Depends(get_current_user),
):
    """
    Update story status. User must have access to the story's project.

    - A DRAFT story can only be accepted (moved to todo) by a backlog owner:
      ACCEPT_STORY permission plus write access to the project.
    - Developers can move only stories assigned to them.
    """
    await verify_story_status_update_access(user, story_id, status)

    success = await story_service.update_story_status(story_id, status)
    
    if not success:
        raise HTTPException(status_code=404, detail="Story not found")
    
    return {"message": "Status updated", "story_id": story_id, "status": status}
