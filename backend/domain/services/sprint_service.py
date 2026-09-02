"""
Sprint service for sprint management and Plan vs Reality logic.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid
from repositories.sprint_repository import SprintRepository
from repositories.story_repository import StoryRepository
from domain.models.sprint import SprintCreate, Sprint


class SprintService:
    """Service for sprint operations."""

    def __init__(self):
        self.sprint_repo = SprintRepository()
        self.story_repo = StoryRepository()

    async def create_sprint(self, sprint_data: SprintCreate) -> Sprint:
        """
        Create a new sprint.
        
        Args:
            sprint_data: Sprint creation data
        
        Returns:
            Created sprint
        """
        sprint_doc = {
            "id": f"SPR-{uuid.uuid4().hex[:8].upper()}",
            "name": sprint_data.name,
            "project_id": sprint_data.project_id,
            "goal": sprint_data.goal,
            "start_date": sprint_data.start_date,
            "end_date": sprint_data.end_date,
            "status": "planning",
            "velocity": None,
            "completion_pct": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.sprint_repo.insert(sprint_doc)

        return Sprint(**sprint_doc)

    async def get_sprint(self, sprint_id: str) -> Optional[Sprint]:
        """Get sprint by ID."""
        sprint = await self.sprint_repo.find_by_id(sprint_id)
        return Sprint(**sprint) if sprint else None

    async def get_active_sprint(self, project_id: str) -> Optional[Sprint]:
        """Get the active sprint for a project."""
        sprint = await self.sprint_repo.find_active(project_id)
        return Sprint(**sprint) if sprint else None

    async def get_project_sprints(self, project_id: str) -> list[Sprint]:
        """Get all sprints in a project."""
        sprints = await self.sprint_repo.find_by_project(project_id)
        return [Sprint(**s) for s in sprints]

    async def calculate_sprint_health(self, sprint_id: str) -> dict:
        """
        Calculate sprint health: Plan vs Reality.
        
        This is the core "Plan vs Reality" intelligence loop.
        Returns objective metrics about sprint progress.
        """
        sprint = await self.get_sprint(sprint_id)
        if not sprint:
            return {"error": "Sprint not found"}

        # Get all stories in this sprint
        stories = await self.story_repo.find_by_sprint(sprint_id)

        total_stories = len(stories)
        total_points = sum(s.get("points", 0) for s in stories)

        completed_stories = [s for s in stories if s.get("status") == "done"]
        completed_points = sum(s.get("points", 0) for s in completed_stories)

        in_progress = [s for s in stories if s.get("status") == "in_progress"]
        blocked = [s for s in stories if s.get("status") == "blocked"]
        
        completion_pct = (
            (completed_points / total_points * 100) if total_points > 0 else 0
        )

        # Risk assessment (Layer 5 Intelligence - rule-based)
        risk_score = 0
        risk_factors = []

        if completion_pct < 30 and sprint.status == "active":
            risk_score += 25
            risk_factors.append("Low completion percentage")

        if len(blocked) > 0:
            risk_score += 15 * len(blocked)
            risk_factors.append(f"{len(blocked)} stories blocked")

        if len(in_progress) > 5:
            risk_score += 10
            risk_factors.append("Too many stories in progress simultaneously")

        risk_level = "LOW"
        if risk_score > 70:
            risk_level = "CRITICAL"
        elif risk_score > 50:
            risk_level = "HIGH"
        elif risk_score > 30:
            risk_level = "MEDIUM"

        return {
            "sprint_id": sprint_id,
            "sprint_name": sprint.name,
            "status": sprint.status,
            "total_stories": total_stories,
            "total_points": total_points,
            "completed_stories": len(completed_stories),
            "completed_points": completed_points,
            "completion_pct": round(completion_pct, 2),
            "in_progress": len(in_progress),
            "blocked": len(blocked),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
        }

    async def update_sprint_status(self, sprint_id: str, status: str) -> bool:
        """Update sprint status (planning|active|completed)."""
        return await self.sprint_repo.update({"id": sprint_id}, {"status": status})
