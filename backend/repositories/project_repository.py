"""
Project repository with organization and team queries.
"""

from .base import BaseRepository
from core.database import col


class ProjectRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("projects"))

    async def find_active(self, org_id: str) -> list:
        """Find all active projects in an organization."""
        return await self.find_all({"org_id": org_id, "status": "active"})

    async def find_by_team(self, team_id: str) -> list:
        """Find all projects assigned to a team."""
        return await self.find_all({"team_id": team_id})

    async def find_by_id(self, project_id: str):
        """Find project by ID."""
        return await self.find_one({"id": project_id})
