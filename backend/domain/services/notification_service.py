"""
Notification Service — creates and manages in-app notifications.
Called by other services (workflow, webhook, comments) to alert users.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from repositories.notification_repository import NotificationRepository


class NotificationService:
    """Creates and manages user notifications."""
    
    def __init__(self):
        self.repo = NotificationRepository()
    
    async def notify(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str,
        link: Optional[str] = None,
    ) -> dict:
        """
        Create a notification for a user.
        
        Args:
            user_id: Recipient user ID
            notification_type: e.g. task_assigned, pr_review_requested
            title: Short notification title
            body: Detailed message
            link: Optional deep link
        
        Returns:
            Created notification dict
        """
        notification = {
            "id": f"NOTIF-{uuid.uuid4().hex[:8].upper()}",
            "user_id": user_id,
            "type": notification_type,
            "title": title,
            "body": body,
            "link": link,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.repo.insert(notification)
        return notification
    
    async def notify_team(
        self,
        user_ids: list[str],
        notification_type: str,
        title: str,
        body: str,
        link: Optional[str] = None,
    ) -> int:
        """
        Send a notification to multiple users.
        
        Returns:
            Number of notifications created
        """
        count = 0
        for user_id in user_ids:
            await self.notify(user_id, notification_type, title, body, link)
            count += 1
        return count
    
    async def get_user_notifications(
        self, user_id: str, limit: int = 50, skip: int = 0
    ) -> list[dict]:
        """Get paginated notifications for a user."""
        return await self.repo.find_by_user(user_id, limit, skip)
    
    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications."""
        return await self.repo.count_unread(user_id)
    
    async def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        return await self.repo.mark_read(notification_id)
    
    async def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read. Returns count updated."""
        return await self.repo.mark_all_read(user_id)
