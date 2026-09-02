"""
Notification Preferences API - Phase 1.4
"""

from fastapi import APIRouter, HTTPException
from domain.models.notification_preferences import NotificationPreferences
from repositories.notification_preferences_repository import NotificationPreferencesRepository

router = APIRouter()
repo = NotificationPreferencesRepository()


@router.get("/preferences/{user_id}")
async def get_preferences(user_id: str):
    """Get user notification preferences."""
    prefs = await repo.find_by_user(user_id)
    if not prefs:
        # Return defaults
        return NotificationPreferences(user_id=user_id).dict()
    return prefs


@router.put("/preferences/{user_id}")
async def update_preferences(user_id: str, preferences: NotificationPreferences):
    """Update user notification preferences."""
    await repo.upsert(user_id, preferences.dict())
    return {"success": True, "user_id": user_id}


@router.delete("/preferences/{user_id}")
async def reset_preferences(user_id: str):
    """Reset to default preferences."""
    await repo.delete(user_id)
    return {"success": True, "message": "Preferences reset to defaults"}
