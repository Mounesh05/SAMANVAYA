"""
Sprint domain models.
Sprints represent time-boxed iterations with goals and stories.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class SprintCreate(BaseModel):
    """Request model for creating a new sprint."""
    
    name: str
    project_id: str
    goal: Optional[str] = None
    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_date_range(self) -> "SprintCreate":
        """Ensure a sprint ends on or after its start date."""
        try:
            start = datetime.fromisoformat(
                self.start_date.replace("Z", "+00:00")
            ).date()
            end = datetime.fromisoformat(
                self.end_date.replace("Z", "+00:00")
            ).date()
        except ValueError as exc:
            raise ValueError(
                "Sprint dates must be valid ISO dates or datetimes"
            ) from exc

        if end < start:
            raise ValueError("Sprint end date must be on or after its start date")

        return self


class Sprint(SprintCreate):
    """Complete sprint model with calculated fields."""
    
    id: str
    status: str = "planning"  # planning|active|completed
    velocity: Optional[int] = None
    completion_pct: Optional[float] = None
    created_at: str = ""
    # Set by SprintFlowService when the sprint is started / completed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    committed_points: Optional[float] = None       # scope snapshot at start
    committed_item_ids: Optional[list] = None
    completed_points: Optional[float] = None       # velocity, in points
