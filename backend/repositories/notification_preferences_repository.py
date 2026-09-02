"""
Notification Preferences Repository 
"""

from typing import Optional, Dict, Any
from core.database import db


class NotificationPreferencesRepository:
    def __init__(self):
        self.collection = db["notification_preferences"]
    
    async def find_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's notification preferences."""
        return await self.collection.find_one({"user_id": user_id})
    
    async def upsert(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """Create or update preferences."""
        result = await self.collection.update_one(
            {"user_id": user_id},
            {"$set": preferences},
            upsert=True
        )
        return True
    
    async def delete(self, user_id: str) -> bool:
        """Delete preferences (reset to defaults)."""
        result = await self.collection.delete_one({"user_id": user_id})
        return result.deleted_count > 0
