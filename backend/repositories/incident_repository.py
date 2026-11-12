"""
Incident repository — MongoDB operations for the incidents collection.
"""

from core.database import col
from repositories.base import BaseRepository


class IncidentRepository(BaseRepository):
    """Repository for reported production incidents."""

    def __init__(self):
        super().__init__(col("incidents"))

    async def list_for(self, query: dict, limit: int = 200) -> list:
        cursor = self.col.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [doc async for doc in cursor]
