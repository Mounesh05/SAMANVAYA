"""
Project service for project management operations.
"""

from datetime import datetime
from typing import Optional
import uuid
from repositories.project_repository import ProjectRepository
from domain.models.project import ProjectCreate, Project


class ProjectService:
    """Service for project operations."""

    def __init__(self):
        self.project_repo = ProjectRepository()

    async def create_project(
        self, project_data: ProjectCreate, created_by: str
    ) -> Project:
        """
        Create a new project.
        
        Args:
            project_data: Project creation data
            created_by: Employee ID of creator
        
        Returns:
            Created project
        """
        project_doc = {
            "id": f"PRJ-{uuid.uuid4().hex[:8].upper()}",
            "name": project_data.name,
            "description": project_data.description,
            "org_id": project_data.org_id,
            "team_id": project_data.team_id,
            "start_date": project_data.start_date,
            "end_date": project_data.end_date,
            "main_module": project_data.main_module,
            "status": "active",
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
        }

        await self.project_repo.insert(project_doc)

        return Project(**project_doc)

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID."""
        project = await self.project_repo.find_by_id(project_id)
        return Project(**project) if project else None

    async def get_active_projects(self, org_id: str) -> list[Project]:
        """Get all active projects in an organization."""
        projects = await self.project_repo.find_active(org_id)
        return [Project(**p) for p in projects]

    async def get_team_projects(self, team_id: str) -> list[Project]:
        """Get all projects assigned to a team."""
        projects = await self.project_repo.find_by_team(team_id)
        return [Project(**p) for p in projects]

    async def update_project(self, project_id: str, updates: dict) -> bool:
        """Update project fields."""
        return await self.project_repo.update({"id": project_id}, updates)
