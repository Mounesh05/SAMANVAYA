"""
Story (User Story) domain models.
Stories represent units of work assigned to developers within sprints.
"""

from pydantic import BaseModel
from typing import Optional


class StoryCreate(BaseModel):
    """Request model for creating a new story."""
    
    title: str
    description: Optional[str] = None
    sprint_id: Optional[str] = None
    project_id: Optional[str] = None
    assignee_id: Optional[str] = None
    points: int = 3
    priority: str = "medium"  # low|medium|high|critical


class Story(StoryCreate):
    """Complete story model with status and AI-calculated fields."""
    
    id: str
    status: str = "todo"  # todo|in_progress|review|done
    risk: str = "low"  # low|medium|high|critical
    alignment_score: Optional[int] = None  # 0-100, AI-calculated
    created_at: Optional[str] = ""
