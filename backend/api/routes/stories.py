"""
Story API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from domain.models.story import StoryCreate, Story
from domain.services.story_service import StoryService
from core.dependencies import get_current_user, require_roles

router = APIRouter()
story_service = StoryService()


@router.post("/", response_model=Story, status_code=201)
async def create_story(
    story_data: StoryCreate,
    user: dict = Depends(require_roles("PM", "LEAD")),
):
    """
    Create a new user story.
    Only PM and LEAD can create stories.
    """
    try:
        story = await story_service.create_story(story_data)
        return story
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create story: {str(e)}")


@router.get("/{story_id}", response_model=Story)
async def get_story(
    story_id: str,
    user: dict = Depends(get_current_user),
):
    """Get story by ID."""
    story = await story_service.get_story(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    return story


@router.get("/sprint/{sprint_id}", response_model=list[Story])
async def list_sprint_stories(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """List all stories in a sprint."""
    stories = await story_service.get_sprint_stories(sprint_id)
    return stories


@router.get("/assignee/{assignee_id}", response_model=list[Story])
async def list_assignee_stories(
    assignee_id: str,
    user: dict = Depends(get_current_user),
):
    """List all stories assigned to a developer."""
    stories = await story_service.get_assignee_stories(assignee_id)
    return stories


@router.patch("/{story_id}/status")
async def update_story_status(
    story_id: str,
    status: str = Query(..., regex="^(todo|in_progress|review|done)$"),
    user: dict = Depends(get_current_user),
):
    """Update story status."""
    success = await story_service.update_story_status(story_id, status)
    
    if not success:
        raise HTTPException(status_code=404, detail="Story not found")
    
    return {"message": "Status updated", "story_id": story_id, "status": status}
