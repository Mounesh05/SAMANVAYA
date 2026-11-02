"""
Project domain models.
Projects represent software projects with teams and GitHub integration.
"""

from pydantic import BaseModel
from typing import Optional


class ProjectCreate(BaseModel):
    """Request model for creating a new project."""
    
    name: str
    description: Optional[str] = None
    org_id: Optional[str] = "ORG-001"
    team_id: Optional[str] = None
    team_ids: Optional[list[str]] = []
    key: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    main_module: Optional[str] = None  # expected GitHub module path


class Project(ProjectCreate):
    """Complete project model with system fields."""
    
    id: str
    status: str = "active"  # active|paused|completed|archived
    created_by: Optional[str] = ""
    created_at: Optional[str] = ""
