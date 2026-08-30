"""
Risk repository with entity and project queries.
"""

from .base import BaseRepository
from core.database import col


class RiskRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("risks"))

    async def find_open(self, project_id: str) -> list:
        """Find all open risks in a project."""
        return await self.find_all({"project_id": project_id, "status": "open"})

    async def find_by_entity(self, entity_type: str, entity_id: str):
        """Find risk for a specific entity."""
        return await self.find_one({"entity_type": entity_type, "entity_id": entity_id})

    async def find_by_level(self, project_id: str, risk_level: str) -> list:
        """Find all risks of a specific level (HIGH, CRITICAL, etc.)."""
        return await self.find_all({"project_id": project_id, "risk_level": risk_level})

    async def find_by_id(self, risk_id: str):
        """Find risk by ID."""
        return await self.find_one({"id": risk_id})
