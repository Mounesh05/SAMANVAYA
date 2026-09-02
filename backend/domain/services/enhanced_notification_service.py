"""
Enhanced Notification Service - Phase 1.4

Advanced notification service with:
- Template rendering
- User preferences
- Aggregation/digests
- Multi-channel delivery
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict

from domain.services.notification_template_engine import (
    NotificationTemplateEngine, NotificationTemplate, NotificationPriority
)
from domain.models.notification_preferences import NotificationPreferences, DigestFrequency
from repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class EnhancedNotificationService:
    """
    Enhanced notification service with templates, preferences, and aggregation.
    """
    
    def __init__(self):
        self.repo = NotificationRepository()
        self.template_engine = NotificationTemplateEngine()
        # In-memory pending notifications for aggregation
        self._pending_digests: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
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
        # Load user preferences
        prefs = await self._load_preferences(user_id)
        
        # Render template
        rendered = self.template_engine.render(template, role, context)
        
        # Check if notification should be sent
        if not await self._should_send(prefs, rendered, template):
            logger.debug(f"Notification blocked by preferences for user {user_id}")
            return None
        
        # Check if should aggregate
        if prefs.digest_frequency != DigestFrequency.IMMEDIATE:
            return await self._queue_for_digest(
                user_id, template, rendered, link, recommendations, prefs
            )
        
        # Send immediately
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
    
    async def _queue_for_digest(
        self,
        user_id: str,
        template: NotificationTemplate,
        rendered: Dict[str, Any],
        link: Optional[str],
        recommendations: Optional[List[str]],
        prefs: NotificationPreferences
    ) -> str:
        """Queue notification for digest delivery."""
        digest_id = f"DIGEST-{user_id}-{prefs.digest_frequency.value}"
        
        self._pending_digests[digest_id].append({
            "template": template,
            "rendered": rendered,
            "link": link,
            "recommendations": recommendations,
            "queued_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.debug(f"Queued notification for digest {digest_id}")
        return digest_id
    
    async def send_digests(self, frequency: DigestFrequency) -> int:
        """
        Send all pending digests for a specific frequency.
        
        Called by scheduled task (hourly/daily/weekly).
        
        Returns:
            Number of digests sent
        """
        sent_count = 0
        
        for digest_id, notifications in list(self._pending_digests.items()):
            if frequency.value not in digest_id:
                continue
            
            user_id = digest_id.split("-")[1]
            
            # Aggregate notifications
            digest_body = self._create_digest_body(notifications, frequency)
            
            notification = {
                "id": f"NOTIF-{uuid.uuid4().hex[:8].upper()}",
                "user_id": user_id,
                "type": f"digest_{frequency.value}",
                "title": f"ðŸ“Š Your {frequency.value} digest ({len(notifications)} updates)",
                "body": digest_body,
                "link": "/notifications",
                "priority": "normal",
                "channels": ["in_app"],
                "recommendations": [],
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            await self.repo.insert(notification)
            sent_count += 1
            
            # Clear processed notifications
            del self._pending_digests[digest_id]
        
        logger.info(f"Sent {sent_count} {frequency.value} digests")
        return sent_count
    
    def _create_digest_body(
        self,
        notifications: List[Dict[str, Any]],
        frequency: DigestFrequency
    ) -> str:
        """Create aggregated digest body."""
        # Group by priority
        by_priority = defaultdict(list)
        for notif in notifications:
            priority = notif["rendered"]["priority"].value
            by_priority[priority].append(notif)
        
        lines = []
        lines.append(f"Summary of your {frequency.value} activity:\n")
        
        # Urgent first
        if "urgent" in by_priority:
            lines.append(f"\nðŸš¨ URGENT ({len(by_priority['urgent'])}):")
            for notif in by_priority["urgent"][:5]:  # Top 5
                lines.append(f"  â€¢ {notif['rendered']['title']}")
        
        # High priority
        if "high" in by_priority:
            lines.append(f"\nðŸ”´ HIGH PRIORITY ({len(by_priority['high'])}):")
            for notif in by_priority["high"][:5]:
                lines.append(f"  â€¢ {notif['rendered']['title']}")
        
        # Normal
        if "normal" in by_priority:
            lines.append(f"\nðŸ“‹ UPDATES ({len(by_priority['normal'])}):")
            for notif in by_priority["normal"][:10]:
                lines.append(f"  â€¢ {notif['rendered']['title']}")
        
        if len(notifications) > 20:
            lines.append(f"\n... and {len(notifications) - 20} more")
        
        return "\n".join(lines)
    
    async def _load_preferences(self, user_id: str) -> NotificationPreferences:
        """Load user notification preferences."""
        # TODO: Load from database
        # For now, return defaults
        return NotificationPreferences(user_id=user_id)
    
    async def _should_send(
        self,
        prefs: NotificationPreferences,
        rendered: Dict[str, Any],
        template: NotificationTemplate
    ) -> bool:
        """Check if notification should be sent based on preferences."""
        
        # Check priority filter
        priority_order = {"urgent": 4, "high": 3, "normal": 2, "low": 1}
        min_priority_val = priority_order.get(prefs.min_priority, 2)
        notif_priority_val = priority_order.get(rendered["priority"].value, 2)
        
        if notif_priority_val < min_priority_val:
            return False
        
        # Check muted categories
        if template.value in prefs.mute_categories:
            return False
        
        # Check DND
        if prefs.dnd_enabled and self._is_dnd_time(prefs):
            # Allow urgent notifications during DND
            if rendered["priority"] != NotificationPriority.URGENT:
                return False
        
        return True
    
    def _is_dnd_time(self, prefs: NotificationPreferences) -> bool:
        """Check if current time is within DND period."""
        # TODO: Implement proper timezone-aware DND checking
        # For now, always allow
        return False
    
    # Backward compatibility methods
    
    async def notify(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str,
        link: Optional[str] = None
    ) -> Dict[str, Any]:
        """Legacy notify method for backward compatibility."""
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
