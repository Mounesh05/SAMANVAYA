"""
Task domain models.
Tasks represent specific work items that may or may not be part of a story.
"""

from pydantic import BaseModel
from typing import Optional


class TaskCreate(BaseModel):
    """Request model for creating a new task."""
    
    title: str
    project_id: str
    assignee_id: str
    story_id: Optional[str] = None
    sprint_id: Optional[str] = None
    type: str = "feature"  # feature|bug|chore|research
    priority: str = "medium"  # low|medium|high|critical
    due_date: Optional[str] = None


class Task(TaskCreate):
    """Complete task model with status."""
    
    id: str
    status: str = "todo"  # todo|in_progress|review|done|blocked
    created_at: str = ""
