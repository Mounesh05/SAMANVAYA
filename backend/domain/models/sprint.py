"""
Sprint domain models.
Sprints represent time-boxed iterations with goals and stories.
"""

from pydantic import BaseModel
from typing import Optional


class SprintCreate(BaseModel):
    """Request model for creating a new sprint."""
    
    name: str
    project_id: Optional[str] = None
    goal: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Sprint(SprintCreate):
    """Complete sprint model with calculated fields."""
    
    id: str
    status: str = "planning"  # planning|active|completed
    velocity: Optional[int] = None
    completion_pct: Optional[float] = None
    created_at: Optional[str] = ""
