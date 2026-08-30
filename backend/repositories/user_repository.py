"""
User repository with employee-specific queries.
"""

from .base import BaseRepository
from core.database import col


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("users"))

    async def find_by_employee_id(self, employee_id: str):
        """Find user by employee ID."""
        return await self.find_one({"employee_id": employee_id})

    async def find_by_email(self, email: str):
        """Find user by email address."""
        return await self.find_one({"email": email})

    async def find_active_by_role(self, role: str) -> list:
        """Find all active users with a specific role."""
        return await self.find_all({"role": role, "is_active": True})

    async def find_by_team(self, team_id: str) -> list:
        """Find all active users in a team."""
        return await self.find_all({"team_id": team_id, "is_active": True})

    async def ensure_indexes(self):
        """Create unique indexes on employee_id and email."""
        await self.col.create_index("employee_id", unique=True)
        await self.col.create_index("email", unique=True)
