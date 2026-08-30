"""
Activity repository — MongoDB operations for activity feed.
"""

from core.database import col
from repositories.base import BaseRepository


class ActivityRepository(BaseRepository):
    """Repository for activity feed events."""
    
    def __init__(self):
        super().__init__(col("activities"))
    
    async def get_project_feed(
        self, project_id: str, limit: int = 50, skip: int = 0
    ) -> list:
        """Get activity feed for a project, newest first."""
        cursor = (
            self.col.find({"project_id": project_id}, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]
    
    async def get_user_feed(
        self, user_id: str, limit: int = 50, skip: int = 0
    ) -> list:
        """Get activity feed for a specific user, newest first."""
        cursor = (
            self.col.find({"actor_id": user_id}, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]
    
    async def get_item_history(
        self, item_type: str, item_id: str, limit: int = 100
    ) -> list:
        """Get full activity history for a specific item."""
        cursor = (
            self.col.find(
                {"item_type": item_type, "item_id": item_id}, {"_id": 0}
            )
            .sort("created_at", 1)
            .limit(limit)
        )
        return [doc async for doc in cursor]
