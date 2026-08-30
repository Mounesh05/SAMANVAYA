"""
Sprint domain models.
Sprints represent time-boxed iterations with goals and stories.
"""

from pydantic import BaseModel
from typing import Optional


class SprintCreate(BaseModel):
    """Request model for creating a new sprint."""
    
    name: str
    project_id: str
    goal: Optional[str] = None
    start_date: str
    end_date: str


class Sprint(SprintCreate):
    """Complete sprint model with calculated fields."""
    
    id: str
    status: str = "planning"  # planning|active|completed
    velocity: Optional[int] = None
    completion_pct: Optional[float] = None
    created_at: str = ""
