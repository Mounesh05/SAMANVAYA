"""
Comment and Activity Feed domain models.
Supports comments on tasks, stories, and PRs, plus a unified activity feed.
"""

from pydantic import BaseModel
from typing import Optional, Any


# ── Comment Models ──────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    """Request model for creating a comment."""
    
    parent_type: str            # "task" | "story" | "pr"
    parent_id: str              # ID of the task/story/PR
    body: str                   # markdown-supported comment body


class CommentUpdate(BaseModel):
    """Request model for editing a comment."""
    
    body: str


class Comment(BaseModel):
    """Complete comment model."""
    
    id: str
    parent_type: str
    parent_id: str
    author_id: str
    author_name: str
    body: str
    created_at: str = ""
    edited_at: Optional[str] = None


# ── Activity Feed Models ────────────────────────────────────────────────────

class ActivityEvent(BaseModel):
    """
    A single activity event in the feed.
    
    Types:
        comment_added, status_changed, task_created, task_assigned,
        story_created, pr_synced, pr_reviewed, evaluation_completed,
        sprint_started, sprint_completed
    """
    
    id: str
    event_type: str
    project_id: Optional[str] = None
    item_type: Optional[str] = None     # "task" | "story" | "pr" | "sprint"
    item_id: Optional[str] = None
    actor_id: str                       # who did it
    actor_name: str
    summary: str                        # human-readable: "John moved TASK-42 to Review"
    details: Optional[dict[str, Any]] = None   # extra payload
    created_at: str = ""
