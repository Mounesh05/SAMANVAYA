"""
Task service for task management.
"""

from datetime import datetime
from typing import Optional, List
import uuid
from repositories.task_repository import TaskRepository
from domain.models.task import TaskCreate, Task


class TaskService:
    """Service for task operations."""

    def __init__(self):
        self.task_repo = TaskRepository()

    async def create_task(self, task_data: TaskCreate) -> Task:
        """
        Create a new task.
        
        Args:
            task_data: Task creation data
        
        Returns:
            Created task
        """
        task_doc = {
            "id": f"TSK-{uuid.uuid4().hex[:8].upper()}",
            "title": task_data.title,
            "project_id": task_data.project_id,
            "assignee_id": task_data.assignee_id,
            "story_id": task_data.story_id,
            "sprint_id": task_data.sprint_id,
            "type": task_data.type,
            "priority": task_data.priority,
            "due_date": task_data.due_date,
            "status": "todo",
            "created_at": datetime.utcnow().isoformat(),
        }

        await self.task_repo.insert(task_doc)
        return Task(**task_doc)

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        task = await self.task_repo.find_by_id(task_id)
        return Task(**task) if task else None

    async def get_project_tasks(self, project_id: str) -> List[Task]:
        """Get all tasks in a project."""
        tasks = await self.task_repo.find_by_project(project_id)
        return [Task(**t) for t in tasks]

    async def get_assignee_tasks(self, assignee_id: str) -> List[Task]:
        """Get all tasks assigned to a user."""
        tasks = await self.task_repo.find_by_assignee(assignee_id)
        return [Task(**t) for t in tasks]

    async def get_story_tasks(self, story_id: str) -> List[Task]:
        """Get all tasks for a story."""
        tasks = await self.task_repo.find_by_story(story_id)
        return [Task(**t) for t in tasks]

    async def update_task_status(self, task_id: str, status: str) -> bool:
        """Update task status."""
        return await self.task_repo.update({"id": task_id}, {"status": status})

    async def update_task(self, task_id: str, updates: dict) -> bool:
        """Update task fields."""
        return await self.task_repo.update({"id": task_id}, updates)
