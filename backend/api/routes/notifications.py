"""
Notifications API endpoints.
In-app notification management for users.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from core.dependencies import get_current_user
from domain.services.enhanced_notification_service import EnhancedNotificationService as NotificationService

router = APIRouter()
notification_service = NotificationService()


@router.get("/")
async def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get paginated notifications for the current user."""
    user_id = user.get("employee_id", user.get("id", ""))
    notifications = await notification_service.get_user_notifications(
        user_id, limit, skip
    )
    unread_count = await notification_service.get_unread_count(user_id)
    return {
        "notifications": notifications,
        "count": len(notifications),
        "unread": unread_count,
    }


@router.get("/unread/count")
async def unread_count(user: dict = Depends(get_current_user)):
    """Get count of unread notifications — for badge display."""
    user_id = user.get("employee_id", user.get("id", ""))
    count = await notification_service.get_unread_count(user_id)
    return {"unread": count}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: dict = Depends(get_current_user),
):
    """Mark a single notification as read."""
    user_id = user.get("employee_id", user.get("id", ""))
    success = await notification_service.mark_read(notification_id, user_id)
    if not success:
        # Fetch notification to determine if it's 404 or 403
        notification = await notification_service.repo.find_by_id(notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        # Notification exists but user doesn't own it
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to mark this notification as read"
        )
    return {"message": "Marked as read", "notification_id": notification_id}


@router.patch("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read for the current user."""
    user_id = user.get("employee_id", user.get("id", ""))
    count = await notification_service.mark_all_read(user_id)
    return {"message": f"Marked {count} notifications as read", "updated": count}
