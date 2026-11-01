"""
Task API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from domain.models.task import TaskCreate, Task
from domain.models.workflow import TransitionRequest, AvailableTransitions
from domain.services.task_service import TaskService
from domain.services.workflow_service import WorkflowService
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import (
    verify_task_access,
    verify_project_access,
    verify_story_access,
    verify_can_view_user_tasks,
)

router = APIRouter()
task_service = TaskService()
workflow_service = WorkflowService()


@router.post("/", response_model=Task, status_code=201)
async def create_task(
    task_data: TaskCreate,
    user: dict = Depends(require_permission(Permission.CREATE_TASK)),
):
    """
    Create a new task.
    Requires CREATE_TASK permission (LEAD, PM roles by default).
    User must have write access to the target project.
    """
    # Verify user has write access to the target project
    await verify_project_access(user, task_data.project_id, require_write=True)
    
    try:
        task = await task_service.create_task(task_data)
        return task
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Get task by ID. User must have access to the task's project."""
    # Verify user has access to this task's project
    await verify_task_access(user, task_id)
    
    task = await task_service.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task


@router.get("/project/{project_id}", response_model=list[Task])
async def list_project_tasks(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """List all tasks in a project. User must have access to the project."""
    # Verify user has access to this project
    await verify_project_access(user, project_id)
    
    tasks = await task_service.get_project_tasks(project_id)
    return tasks


@router.get("/assignee/{assignee_id}", response_model=list[Task])
async def list_assignee_tasks(
    assignee_id: str,
    user: dict = Depends(get_current_user),
):
    """List all tasks assigned to a user. Users can only see their own tasks unless they're PM/CEO."""
    # Verify user can view this assignee's tasks
    await verify_can_view_user_tasks(user, assignee_id)
    
    tasks = await task_service.get_assignee_tasks(assignee_id)
    return tasks


@router.get("/story/{story_id}", response_model=list[Task])
async def list_story_tasks(
    story_id: str,
    user: dict = Depends(get_current_user),
):
    """List all tasks for a story. User must have access to the story's project."""
    # Verify user has access to this story's project
    await verify_story_access(user, story_id)
    
    tasks = await task_service.get_story_tasks(story_id)
    return tasks


@router.patch("/{task_id}/status")
async def update_task_status(
    task_id: str,
    status: str = Query(..., regex="^(todo|in_progress|review|done|blocked)$"),
    user: dict = Depends(require_permission(Permission.MOVE_TASK)),
):
    """
    Update task status (no workflow enforcement — use /transition for enforced moves).
    Requires MOVE_TASK permission (LEAD, PM roles by default).
    User must have access to the task's project.
    """
    # Verify user has write access to this task
    await verify_task_access(user, task_id, require_write=True)
    
    success = await task_service.update_task_status(task_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Status updated", "task_id": task_id, "status": status}


@router.patch("/{task_id}/transition", response_model=Task)
async def transition_task(
    task_id: str,
    body: TransitionRequest,
    user: dict = Depends(require_permission(Permission.TRANSITION_TASK)),
):
    """
    Move a task to a new status via the workflow engine.
    Enforces valid transitions — returns 400 if the move is not allowed.
    Requires TRANSITION_TASK permission (LEAD, PM roles by default).
    User must have access to the task's project.
    """
    # Verify user has write access to this task
    await verify_task_access(user, task_id, require_write=True)
    
    user_id = user.get("employee_id", user.get("id", ""))
    user_name = user.get("name", "Unknown")
    try:
        updated = await workflow_service.transition_task(
            task_id=task_id,
            new_status=body.status,
            user_id=user_id,
            user_name=user_name,
            reason=body.reason,
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/transitions", response_model=AvailableTransitions)
async def get_available_transitions(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the list of valid status transitions for a task from its current status."""
    # Verify user has access to this task
    await verify_task_access(user, task_id)
    
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    current = task.get("status", "todo") if isinstance(task, dict) else task.status
    allowed = workflow_service.get_allowed_transitions(current, "task")
    return AvailableTransitions(
        item_id=task_id, current_status=current, allowed_statuses=allowed
    )


@router.get("/{task_id}/history")
async def get_task_history(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the full transition history for a task."""
    # Verify user has access to this task
    await verify_task_access(user, task_id)
    
    history = await workflow_service.get_transition_history(task_id, "task")
    return {"task_id": task_id, "history": history}
