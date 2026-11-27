"""Persist in-app notifications and apply preferences to optional deliveries."""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from domain.services.notification_template_engine import (
    NotificationTemplateEngine, NotificationTemplate, NotificationPriority
)
from domain.models.notification_preferences import NotificationPreferences
from repositories.notification_preferences_repository import NotificationPreferencesRepository
from repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class EnhancedNotificationService:
    """Render notifications and manage their inbox state."""
    
    def __init__(self):
        self.repo = NotificationRepository()
        self.template_engine = NotificationTemplateEngine()
        self.preferences = NotificationPreferencesRepository()
    
    async def notify_with_template(
        self,
        user_id: str,
        template: NotificationTemplate,
        role: str,
        context: Dict[str, Any],
        link: Optional[str] = None,
        recommendations: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Send notification using template system.
        
        Args:
            user_id: Recipient user ID
            template: Template to use
            role: User's role for role-specific rendering
            context: Data for template rendering
            link: Optional deep link
            recommendations: Optional list of recommendation IDs to include
        
        Returns:
            Notification ID if sent, None if blocked by preferences
        """
        rendered = self.template_engine.render(template, role, context)
        if not await self.allows_optional_notification(user_id, template.value, rendered["priority"]):
            return None

        # The inbox is durable and immediate. Digest scheduling is a separate delivery mechanism.
        return await self._send_notification(
            user_id, template.value, rendered, link, recommendations
        )
    
    async def _send_notification(
        self,
        user_id: str,
        notification_type: str,
        rendered: Dict[str, Any],
        link: Optional[str],
        recommendations: Optional[List[str]]
    ) -> str:
        """Send notification immediately."""
        notification = {
            "id": f"NOTIF-{uuid.uuid4().hex[:8].upper()}",
            "user_id": user_id,
            "type": notification_type,
            "title": rendered["title"],
            "body": rendered["body"],
            "link": link,
            "priority": rendered["priority"].value,
            "channels": [ch.value for ch in rendered["channels"]],
            "recommendations": recommendations or [],
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        await self.repo.insert(notification)
        logger.info(f"Sent notification {notification['id']} to {user_id}")
        
        return notification["id"]
    
    async def allows_optional_notification(
        self, user_id: str, category: str, priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        stored = await self.preferences.find_by_user(user_id)
        prefs = NotificationPreferences.model_validate(stored or {"user_id": user_id})
        priorities = {"urgent": 4, "high": 3, "normal": 2, "low": 1}
        if not prefs.enable_in_app or category in prefs.mute_categories:
            return False
        if priorities[priority.value] < priorities.get(prefs.min_priority, priorities["normal"]):
            return False
        return priority == NotificationPriority.URGENT or not self._is_dnd_time(prefs)

    @staticmethod
    def _is_dnd_time(prefs: NotificationPreferences) -> bool:
        if not prefs.dnd_enabled or not prefs.dnd_start_utc or not prefs.dnd_end_utc:
            return False
        try:
            start = datetime.strptime(prefs.dnd_start_utc, "%H:%M").time()
            end = datetime.strptime(prefs.dnd_end_utc, "%H:%M").time()
        except ValueError:
            # Older preferences allowed arbitrary strings. An invalid window cannot suppress an alert.
            return False
        now = datetime.now(timezone.utc).time()
        if start > end:
            return now >= start or now < end
        return start <= now < end

    async def notify(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str,
        link: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a notification immediately and return its persisted identity."""
        notification = {
            "id": f"NOTIF-{uuid.uuid4().hex[:8].upper()}",
            "user_id": user_id,
            "type": notification_type,
            "title": title,
            "body": body,
            "link": link,
            "priority": "normal",
            "channels": ["in_app"],
            "recommendations": [],
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.repo.insert(notification)
        return notification
    
    async def notify_team(
        self,
        user_ids: List[str],
        notification_type: str,
        title: str,
        body: str,
        link: Optional[str] = None
    ) -> int:
        """Legacy notify_team method for backward compatibility."""
        count = 0
        for user_id in user_ids:
            await self.notify(user_id, notification_type, title, body, link)
            count += 1
        return count
    
    async def get_user_notifications(
        self, user_id: str, limit: int = 50, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get paginated notifications for a user."""
        return await self.repo.find_by_user(user_id, limit, skip)
    
    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications."""
        return await self.repo.count_unread(user_id)
    
    async def mark_read(self, notification_id: str, user_id: Optional[str] = None) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of the notification to mark as read
            user_id: Optional user ID for ownership verification
        
        Returns:
            True if marked as read, False if not found or ownership mismatch
        """
        if user_id:
            # Verify ownership
            notification = await self.repo.find_by_id(notification_id)
            if not notification:
                return False
            if notification.get("user_id") != user_id:
                return False
        
        return await self.repo.mark_read(notification_id)
    
    async def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read. Returns count updated."""
        return await self.repo.mark_all_read(user_id)
