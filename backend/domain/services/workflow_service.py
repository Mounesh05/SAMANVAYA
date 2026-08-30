"""
Workflow Service — enforces status transitions for tasks and stories.
Records transition history for audit trail.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from domain.models.workflow import (
    WORKFLOWS, StatusTransition, ALL_TASK_STATUSES, ALL_STORY_STATUSES
)
from repositories.task_repository import TaskRepository
from repositories.story_repository import StoryRepository
from repositories.activity_repository import ActivityRepository
from core.database import col


class WorkflowService:
    """Enforces valid status transitions and records history."""
    
    def __init__(self):
        self.task_repo = TaskRepository()
        self.story_repo = StoryRepository()
        self.activity_repo = ActivityRepository()
        self.transition_col = col("transitions")
    
    def get_allowed_transitions(
        self, current_status: str, workflow_type: str = "task"
    ) -> list[str]:
        """
        Get list of valid next statuses from current status.
        
        Args:
            current_status: Current item status
            workflow_type: "task" or "story"
        
        Returns:
            List of allowed target statuses
        """
        workflow = WORKFLOWS.get(workflow_type, {})
        return workflow.get(current_status, [])
    
    def validate_transition(
        self, current_status: str, new_status: str, workflow_type: str = "task"
    ) -> bool:
        """Check if a status transition is allowed."""
        allowed = self.get_allowed_transitions(current_status, workflow_type)
        return new_status in allowed
    
    async def transition_task(
        self,
        task_id: str,
        new_status: str,
        user_id: str,
        user_name: str,
        reason: Optional[str] = None,
    ) -> dict:
        """
        Execute a validated status transition on a task.
        
        Raises ValueError if transition is invalid.
        Returns the updated task.
        """
        task = await self.task_repo.find_one({"id": task_id})
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        current_status = task.get("status", "todo")
        
        if not self.validate_transition(current_status, new_status, "task"):
            allowed = self.get_allowed_transitions(current_status, "task")
            raise ValueError(
                f"Cannot transition from '{current_status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )
        
        # Update status
        await self.task_repo.update({"id": task_id}, {"status": new_status})
        
        # Record transition
        now = datetime.now(timezone.utc).isoformat()
        transition = StatusTransition(
            id=f"TR-{uuid.uuid4().hex[:8].upper()}",
            item_id=task_id,
            item_type="task",
            from_status=current_status,
            to_status=new_status,
            changed_by=user_id,
            changed_by_name=user_name,
            reason=reason,
            created_at=now,
        )
        await self.transition_col.insert_one(transition.model_dump())
        
        # Record activity
        await self.activity_repo.insert({
            "id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
            "event_type": "status_changed",
            "project_id": task.get("project_id"),
            "item_type": "task",
            "item_id": task_id,
            "actor_id": user_id,
            "actor_name": user_name,
            "summary": f"{user_name} moved task {task_id} from {current_status} to {new_status}",
            "details": {
                "from_status": current_status,
                "to_status": new_status,
                "reason": reason,
            },
            "created_at": now,
        })
        
        return {**task, "status": new_status}
    
    async def transition_story(
        self,
        story_id: str,
        new_status: str,
        user_id: str,
        user_name: str,
        reason: Optional[str] = None,
    ) -> dict:
        """
        Execute a validated status transition on a story.
        
        Raises ValueError if transition is invalid.
        Returns the updated story.
        """
        story = await self.story_repo.find_one({"id": story_id})
        if not story:
            raise ValueError(f"Story {story_id} not found")
        
        current_status = story.get("status", "todo")
        
        if not self.validate_transition(current_status, new_status, "story"):
            allowed = self.get_allowed_transitions(current_status, "story")
            raise ValueError(
                f"Cannot transition from '{current_status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )
        
        # Update status
        await self.story_repo.update({"id": story_id}, {"status": new_status})
        
        # Record transition
        now = datetime.now(timezone.utc).isoformat()
        transition = StatusTransition(
            id=f"TR-{uuid.uuid4().hex[:8].upper()}",
            item_id=story_id,
            item_type="story",
            from_status=current_status,
            to_status=new_status,
            changed_by=user_id,
            changed_by_name=user_name,
            reason=reason,
            created_at=now,
        )
        await self.transition_col.insert_one(transition.model_dump())
        
        # Record activity
        await self.activity_repo.insert({
            "id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
            "event_type": "status_changed",
            "project_id": story.get("project_id"),
            "item_type": "story",
            "item_id": story_id,
            "actor_id": user_id,
            "actor_name": user_name,
            "summary": f"{user_name} moved story {story_id} from {current_status} to {new_status}",
            "details": {
                "from_status": current_status,
                "to_status": new_status,
                "reason": reason,
            },
            "created_at": now,
        })
        
        return {**story, "status": new_status}
    
    async def get_transition_history(
        self, item_id: str, item_type: str = "task"
    ) -> list[dict]:
        """Get all transitions for an item, ordered chronologically."""
        cursor = (
            self.transition_col.find(
                {"item_id": item_id, "item_type": item_type}, {"_id": 0}
            )
            .sort("created_at", 1)
        )
        return [doc async for doc in cursor]
