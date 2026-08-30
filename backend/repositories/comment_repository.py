"""
Comment repository — MongoDB operations for comments collection.
"""

from core.database import col
from repositories.base import BaseRepository


class CommentRepository(BaseRepository):
    """Repository for task/story/PR comments."""
    
    def __init__(self):
        super().__init__(col("comments"))
    
    async def find_by_parent(self, parent_type: str, parent_id: str) -> list:
        """Get all comments for a specific item, ordered by creation time."""
        cursor = self.col.find(
            {"parent_type": parent_type, "parent_id": parent_id},
            {"_id": 0}
        ).sort("created_at", 1)
        return [doc async for doc in cursor]
    
    async def find_by_id(self, comment_id: str) -> dict | None:
        """Find a single comment by ID."""
        return await self.find_one({"id": comment_id})
    
    async def count_by_parent(self, parent_type: str, parent_id: str) -> int:
        """Count comments on an item."""
        return await self.count({"parent_type": parent_type, "parent_id": parent_id})
