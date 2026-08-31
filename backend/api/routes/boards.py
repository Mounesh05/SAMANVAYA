"""
Board / Kanban API endpoints.
Returns sprint/project items grouped into status columns.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from core.dependencies import get_current_user, require_roles
from repositories.task_repository import TaskRepository
from repositories.story_repository import StoryRepository
from repositories.sprint_repository import SprintRepository
from domain.services.workflow_service import WorkflowService

router = APIRouter()
task_repo = TaskRepository()
story_repo = StoryRepository()
sprint_repo = SprintRepository()
workflow_service = WorkflowService()

# Column order for boards
TASK_COLUMNS = ["todo", "in_progress", "review", "done", "blocked"]
STORY_COLUMNS = ["todo", "in_progress", "review", "done", "blocked"]


class MoveItemRequest(BaseModel):
    """Request to move an item to a new column."""
    item_id: str
    item_type: str          # "task" | "story"
    target_status: str
    reason: str | None = None


def _build_columns(items: list, columns: list) -> list:
    """Group items into board columns."""
    grouped = {col: [] for col in columns}
    for item in items:
        status = item.get("status", "todo")
        if status in grouped:
            grouped[status].append(item)
        else:
            grouped.setdefault("todo", []).append(item)

    return [
        {
            "id": col_id,
            "title": col_id.replace("_", " ").title(),
            "count": len(grouped[col_id]),
            "items": grouped[col_id],
        }
        for col_id in columns
    ]


@router.get("/sprint/{sprint_id}")
async def get_sprint_board(
    sprint_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get Kanban board for a sprint.
    Returns stories and tasks grouped by status columns.
    """
    sprint = await sprint_repo.find_one({"id": sprint_id})
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")

    stories = await story_repo.find_all({"sprint_id": sprint_id})
    tasks = await task_repo.find_all({"sprint_id": sprint_id})

    return {
        "sprint_id": sprint_id,
        "sprint_name": sprint.get("name", ""),
        "stories": {
            "columns": _build_columns(stories, STORY_COLUMNS),
            "total": len(stories),
        },
        "tasks": {
            "columns": _build_columns(tasks, TASK_COLUMNS),
            "total": len(tasks),
        },
    }


@router.get("/project/{project_id}")
async def get_project_board(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get Kanban board for an entire project.
    Returns all tasks grouped by status columns.
    """
    tasks = await task_repo.find_all({"project_id": project_id})
    stories = await story_repo.find_all({"project_id": project_id})

    return {
        "project_id": project_id,
        "stories": {
            "columns": _build_columns(stories, STORY_COLUMNS),
            "total": len(stories),
        },
        "tasks": {
            "columns": _build_columns(tasks, TASK_COLUMNS),
            "total": len(tasks),
        },
    }


@router.patch("/move")
async def move_item(
    body: MoveItemRequest,
    user: dict = Depends(require_roles("DEVELOPER", "LEAD", "PM", "QA", "DEVOPS")),
):
    """
    Move a task or story to a new status column.
    Enforced through the workflow engine — invalid transitions are rejected.
    """
    user_id = user.get("employee_id", user.get("id", ""))
    user_name = user.get("name", "Unknown")

    try:
        if body.item_type == "task":
            updated = await workflow_service.transition_task(
                task_id=body.item_id,
                new_status=body.target_status,
                user_id=user_id,
                user_name=user_name,
                reason=body.reason,
            )
        elif body.item_type == "story":
            updated = await workflow_service.transition_story(
                story_id=body.item_id,
                new_status=body.target_status,
                user_id=user_id,
                user_name=user_name,
                reason=body.reason,
            )
        else:
            raise HTTPException(
                status_code=400, detail="item_type must be 'task' or 'story'"
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "Moved successfully",
        "item_id": body.item_id,
        "item_type": body.item_type,
        "new_status": body.target_status,
        "item": updated,
    }
