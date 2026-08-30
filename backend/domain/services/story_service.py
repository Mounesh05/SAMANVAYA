"""
Story service for user story management.
"""

from datetime import datetime
from typing import Optional, List
import uuid
from repositories.story_repository import StoryRepository
from domain.models.story import StoryCreate, Story


class StoryService:
    """Service for story operations."""

    def __init__(self):
        self.story_repo = StoryRepository()

    async def create_story(self, story_data: StoryCreate) -> Story:
        """
        Create a new user story.
        
        Args:
            story_data: Story creation data
        
        Returns:
            Created story
        """
        story_doc = {
            "id": f"STY-{uuid.uuid4().hex[:8].upper()}",
            "title": story_data.title,
            "description": story_data.description,
            "sprint_id": story_data.sprint_id,
            "project_id": story_data.project_id,
            "assignee_id": story_data.assignee_id,
            "points": story_data.points,
            "priority": story_data.priority,
            "status": "todo",
            "risk": "low",
            "alignment_score": None,
            "created_at": datetime.utcnow().isoformat(),
        }

        await self.story_repo.insert(story_doc)
        return Story(**story_doc)

    async def get_story(self, story_id: str) -> Optional[Story]:
        """Get story by ID."""
        story = await self.story_repo.find_by_id(story_id)
        return Story(**story) if story else None

    async def get_sprint_stories(self, sprint_id: str) -> List[Story]:
        """Get all stories in a sprint."""
        stories = await self.story_repo.find_by_sprint(sprint_id)
        return [Story(**s) for s in stories]

    async def get_assignee_stories(self, assignee_id: str) -> List[Story]:
        """Get all stories assigned to a developer."""
        stories = await self.story_repo.find_by_assignee(assignee_id)
        return [Story(**s) for s in stories]

    async def update_story_status(self, story_id: str, status: str) -> bool:
        """Update story status (todo|in_progress|review|done)."""
        return await self.story_repo.update({"id": story_id}, {"status": status})

    async def update_story(self, story_id: str, updates: dict) -> bool:
        """Update story fields."""
        return await self.story_repo.update({"id": story_id}, updates)
