"""
Sprint repository with project and status queries.
"""

from .base import BaseRepository
from core.database import col


class SprintRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("sprints"))

    async def find_active(self, project_id: str):
        """Find the active sprint for a project."""
        return await self.find_one({"project_id": project_id, "status": "active"})

    async def find_by_project(self, project_id: str) -> list:
        """Find all sprints in a project."""
        return await self.find_all({"project_id": project_id})

    async def find_by_id(self, sprint_id: str):
        """Find sprint by ID."""
        return await self.find_one({"id": sprint_id})
