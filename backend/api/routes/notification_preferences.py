"""
Notification Preferences API - Phase 1.4

All endpoints require JWT authentication.
Users can only access their own notification preferences.
"""

from fastapi import APIRouter, HTTPException, Depends
from domain.models.notification_preferences import NotificationPreferences
from repositories.notification_preferences_repository import NotificationPreferencesRepository
from core.dependencies import get_current_user

router = APIRouter()
repo = NotificationPreferencesRepository()


@router.get("/preferences")
async def get_preferences(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's notification preferences."""
    user_id = current_user["employee_id"]
    prefs = await repo.find_by_user(user_id)
    if not prefs:
        # Return defaults
        return NotificationPreferences(user_id=user_id).dict()
    return prefs


@router.put("/preferences")
async def update_preferences(
    preferences: NotificationPreferences,
    current_user: dict = Depends(get_current_user),
):
    """Update current user's notification preferences."""
    user_id = current_user["employee_id"]
    await repo.upsert(user_id, preferences.dict())
    return {"success": True, "user_id": user_id}


@router.delete("/preferences")
async def reset_preferences(
    current_user: dict = Depends(get_current_user),
):
    """Reset current user's preferences to defaults."""
    user_id = current_user["employee_id"]
    await repo.delete(user_id)
    return {"success": True, "message": "Preferences reset to defaults"}
