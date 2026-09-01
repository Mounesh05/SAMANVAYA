"""
Task repository with project and assignee queries.
"""

from .base import BaseRepository
from core.database import col


class TaskRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("tasks"))

    async def find_by_project(self, project_id: str) -> list:
        """Find all tasks in a project."""
        return await self.find_all({"project_id": project_id})

    async def find_by_assignee(self, assignee_id: str) -> list:
        """Find all tasks assigned to a user."""
        return await self.find_all({"assignee_id": assignee_id})

    async def find_by_story(self, story_id: str) -> list:
        """Find all tasks belonging to a story."""
        return await self.find_all({"story_id": story_id})

    async def find_by_id(self, task_id: str):
        """Find task by ID."""
        return await self.find_one({"id": task_id})
    
    async def find_by_number(self, project_id: str, task_number: int):
        """
        Find task by number within a project.
        Assumes task IDs follow format: TASK-{number}
        """
        task_id = f"TASK-{task_number}"
        return await self.find_one({"id": task_id, "project_id": project_id})
