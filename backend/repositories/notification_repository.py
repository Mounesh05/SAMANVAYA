"""
Notification repository — MongoDB operations for notifications collection.
"""

from core.database import col
from repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    """Repository for user notifications."""
    
    def __init__(self):
        super().__init__(col("notifications"))
    
    async def find_by_user(
        self, user_id: str, limit: int = 50, skip: int = 0
    ) -> list:
        """Get notifications for a user, newest first."""
        cursor = (
            self.col.find({"user_id": user_id}, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]
    
    async def find_unread(self, user_id: str) -> list:
        """Get unread notifications for a user."""
        cursor = (
            self.col.find(
                {"user_id": user_id, "read": False}, {"_id": 0}
            )
            .sort("created_at", -1)
        )
        return [doc async for doc in cursor]
    
    async def count_unread(self, user_id: str) -> int:
        """Count unread notifications."""
        return await self.count({"user_id": user_id, "read": False})
    
    async def mark_read(self, notification_id: str) -> bool:
        """Mark a single notification as read."""
        return await self.update({"id": notification_id}, {"read": True})
    
    async def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user. Returns count updated."""
        result = await self.col.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        return result.modified_count
