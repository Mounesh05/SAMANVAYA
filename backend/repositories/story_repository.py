"""
Story repository with sprint and assignee queries.
"""

from .base import BaseRepository
from core.database import col


class StoryRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("stories"))

    async def find_by_sprint(self, sprint_id: str) -> list:
        """Find all stories in a sprint."""
        return await self.find_all({"sprint_id": sprint_id})

    async def find_by_assignee(self, assignee_id: str) -> list:
        """Find all stories assigned to a developer."""
        return await self.find_all({"assignee_id": assignee_id})

    async def find_by_id(self, story_id: str):
        """Find story by ID."""
        return await self.find_one({"id": story_id})
