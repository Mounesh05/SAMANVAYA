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
        """Update task status. Triggers agent score update if task is completed."""
        from intelligence.task_scoring_trigger import is_completion_status, on_task_completed
        updates = {"status": status}
        if is_completion_status(status):
            updates["completed_at"] = datetime.utcnow().isoformat()

        updated = await self.task_repo.update({"id": task_id}, updates)
        if updated and is_completion_status(status):
            await on_task_completed(task_id, run_in_background=True)
        return updated

    async def update_task(self, task_id: str, updates: dict) -> bool:
        """Update task fields. Triggers agent score update if task is completed."""
        from intelligence.task_scoring_trigger import is_completion_status, on_task_completed
        status = updates.get("status")
        if is_completion_status(status) and "completed_at" not in updates:
            updates["completed_at"] = datetime.utcnow().isoformat()

        updated = await self.task_repo.update({"id": task_id}, updates)
        if updated and is_completion_status(status):
            await on_task_completed(task_id, run_in_background=True)
        return updated

    async def get_all_tasks(self, filter_query: dict = None, limit: int = 100) -> List[Task]:
        """Get tasks matching optional filter."""
        tasks = await self.task_repo.find_all(filter_query or {}, limit=limit)
        return [Task(**t) for t in tasks]

    async def delete_task(self, task_id: str) -> bool:
        """Delete task by id."""
        return await self.task_repo.delete({"id": task_id})

