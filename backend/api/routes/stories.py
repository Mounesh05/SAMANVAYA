"""
Story API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from domain.models.story import StoryCreate, Story
from domain.services.story_service import StoryService
from core.dependencies import get_current_user, require_roles

router = APIRouter()
story_service = StoryService()


from typing import Optional, List
from fastapi import Body

@router.post("", response_model=Story, status_code=201)
@router.post("/", response_model=Story, status_code=201, include_in_schema=False)
async def create_story(
    story_data: StoryCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new user story."""
    try:
        story = await story_service.create_story(story_data)
        return story
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create story: {str(e)}")


@router.get("", response_model=List[Story])
@router.get("/", response_model=List[Story], include_in_schema=False)
async def list_stories(
    sprint_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(get_current_user),
):
    """List all stories with optional filters."""
    filter_q = {}
    if sprint_id:
        filter_q["sprint_id"] = sprint_id
    if assignee_id:
        filter_q["assignee_id"] = assignee_id
    if project_id:
        filter_q["project_id"] = project_id
    if status:
        filter_q["status"] = status
    return await story_service.get_all_stories(filter_q, limit=limit)


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


@router.put("/{story_id}")
async def update_story(
    story_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    """Update story fields."""
    await story_service.update_story(story_id, data)
    story = await story_service.get_story(story_id)
    return story or {"message": "Updated", "story_id": story_id}


@router.delete("/{story_id}")
async def delete_story(
    story_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete story by ID."""
    await story_service.delete_story(story_id)
    return {"message": "Deleted", "story_id": story_id}


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

