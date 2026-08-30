"""
Workflow domain models.
Defines configurable status transitions for tasks and stories,
enforcing valid state changes (like Jira workflows).
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone


# ── Default Workflow Definitions ────────────────────────────────────────────

TASK_WORKFLOW = {
    "todo": ["in_progress"],
    "in_progress": ["review", "blocked", "todo"],
    "review": ["done", "in_progress"],
    "blocked": ["in_progress", "todo"],
    "done": ["in_progress"],  # reopen
}

STORY_WORKFLOW = {
    "todo": ["in_progress"],
    "in_progress": ["review", "blocked", "todo"],
    "review": ["done", "in_progress"],
    "blocked": ["in_progress", "todo"],
    "done": ["in_progress"],  # reopen
}

# Map of workflow type → transitions
WORKFLOWS = {
    "task": TASK_WORKFLOW,
    "story": STORY_WORKFLOW,
}

ALL_TASK_STATUSES = list(TASK_WORKFLOW.keys())
ALL_STORY_STATUSES = list(STORY_WORKFLOW.keys())


# ── Models ──────────────────────────────────────────────────────────────────

class StatusTransition(BaseModel):
    """Records a single status change."""
    
    id: str
    item_id: str                        # task or story ID
    item_type: str                      # "task" | "story"
    from_status: str
    to_status: str
    changed_by: str                     # user ID
    changed_by_name: str                # user display name
    reason: Optional[str] = None        # optional reason for transition
    created_at: str = ""


class TransitionRequest(BaseModel):
    """API request to transition an item's status."""
    
    status: str                         # target status
    reason: Optional[str] = None        # optional reason


class AvailableTransitions(BaseModel):
    """Response showing which transitions are valid from current status."""
    
    item_id: str
    current_status: str
    allowed_statuses: list[str]
