"""
Task API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from domain.models.task import TaskCreate, Task
from domain.models.workflow import TransitionRequest, AvailableTransitions
from domain.services.task_service import TaskService
from domain.services.workflow_service import WorkflowService
from core.dependencies import get_current_user

router = APIRouter()
task_service = TaskService()
workflow_service = WorkflowService()


from typing import Optional, List, Any

@router.post("", response_model=Task, status_code=201)
@router.post("/", response_model=Task, status_code=201, include_in_schema=False)
async def create_task(
    task_data: TaskCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new task."""
    try:
        task = await task_service.create_task(task_data)
        return task
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@router.get("", response_model=List[Task])
@router.get("/", response_model=List[Task], include_in_schema=False)
async def list_tasks(
    project_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    story_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(get_current_user),
):
    """List all tasks with optional filters."""
    filter_q = {}
    if project_id:
        filter_q["project_id"] = project_id
    if assignee_id:
        filter_q["assignee_id"] = assignee_id
    if story_id:
        filter_q["story_id"] = story_id
    if status:
        filter_q["status"] = status
    return await task_service.get_all_tasks(filter_q, limit=limit)


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Get task by ID."""
    task = await task_service.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task


@router.get("/project/{project_id}", response_model=list[Task])
async def list_project_tasks(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """List all tasks in a project."""
    tasks = await task_service.get_project_tasks(project_id)
    return tasks


@router.get("/assignee/{assignee_id}", response_model=list[Task])
async def list_assignee_tasks(
    assignee_id: str,
    user: dict = Depends(get_current_user),
):
    """List all tasks assigned to a user."""
    tasks = await task_service.get_assignee_tasks(assignee_id)
    return tasks


@router.get("/story/{story_id}", response_model=list[Task])
async def list_story_tasks(
    story_id: str,
    user: dict = Depends(get_current_user),
):
    """List all tasks for a story."""
    tasks = await task_service.get_story_tasks(story_id)
    return tasks


@router.patch("/{task_id}/status")
async def update_task_status(
    task_id: str,
    status: str = Query(..., regex="^(todo|in_progress|review|done|blocked)$"),
    user: dict = Depends(get_current_user),
):
    """Update task status (no workflow enforcement — use /transition for enforced moves)."""
    success = await task_service.update_task_status(task_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Status updated", "task_id": task_id, "status": status}


@router.patch("/{task_id}/transition", response_model=Task)
async def transition_task(
    task_id: str,
    body: TransitionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Move a task to a new status via the workflow engine.
    Enforces valid transitions — returns 400 if the move is not allowed.
    """
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
    history = await workflow_service.get_transition_history(task_id, "task")
    return {"task_id": task_id, "history": history}


from fastapi import Body

@router.put("/{task_id}")
async def update_task(
    task_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    """Update task fields."""
    success = await task_service.update_task(task_id, data)
    if not success:
        # If task does not exist, return 404
        task = await task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    task = await task_service.get_task(task_id)
    return task or {"message": "Updated", "task_id": task_id}


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete task."""
    await task_service.delete_task(task_id)
    return {"message": "Deleted", "task_id": task_id}


@router.patch("/{task_id}/assign")
async def assign_task(
    task_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    """Assign task to an employee."""
    assignee_id = data.get("assignee_id")
    await task_service.update_task(task_id, {"assignee_id": assignee_id})
    return {"message": "Assigned", "task_id": task_id, "assignee_id": assignee_id}


@router.post("/{task_id}/mark-done")
async def mark_task_done(
    task_id: str,
    data: dict = Body(default={}),
    user: dict = Depends(get_current_user),
):
    """Mark task as done / submit for review."""
    await task_service.update_task_status(task_id, "review")
    return {"message": "Submitted for review", "task_id": task_id, "status": "review"}


@router.post("/{task_id}/approve")
async def approve_task(
    task_id: str,
    data: dict = Body(default={}),
    user: dict = Depends(get_current_user),
):
    """Approve task and mark done."""
    await task_service.update_task_status(task_id, "done")
    return {"message": "Approved", "task_id": task_id, "status": "done"}


@router.post("/{task_id}/reject")
async def reject_task(
    task_id: str,
    data: dict = Body(default={}),
    user: dict = Depends(get_current_user),
):
    """Reject task back to in_progress."""
    await task_service.update_task_status(task_id, "in_progress")
    return {"message": "Rejected back to in_progress", "task_id": task_id, "status": "in_progress"}

