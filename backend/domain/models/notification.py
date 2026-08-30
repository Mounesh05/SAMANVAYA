"""
Notification domain models.
In-app notification system for user alerts.
"""

from pydantic import BaseModel
from typing import Optional


class Notification(BaseModel):
    """
    In-app notification for a user.
    
    Types:
        task_assigned, pr_review_requested, comment_mention,
        evaluation_complete, sprint_ending, status_changed,
        pr_merged, build_failed
    """
    
    id: str
    user_id: str                        # recipient
    type: str                           # notification type
    title: str                          # short title
    body: str                           # detailed message
    link: Optional[str] = None          # deep link (e.g., "/tasks/TASK-42")
    read: bool = False
    created_at: str = ""


class NotificationCount(BaseModel):
    """Unread notification count response."""
    
    unread: int
