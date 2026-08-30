"""
Developer role-specific dashboard endpoints.
Shows: My tasks, PRs, AI feedback, progress.
"""

from fastapi import APIRouter, Depends
from core.dependencies import require_roles
from repositories.task_repository import TaskRepository
from repositories.story_repository import StoryRepository
from repositories.pr_repository import PRRepository

router = APIRouter()


@router.get("/dashboard")
async def developer_dashboard(user: dict = Depends(require_roles("DEVELOPER"))):
    """
    Developer dashboard - My work overview.
    
    Returns:
        - My active tasks
        - My stories
        - My open PRs
        - Task completion stats
    """
    employee_id = user["employee_id"]
    
    task_repo = TaskRepository()
    story_repo = StoryRepository()
    pr_repo = PRRepository()
    
    # My tasks
    my_tasks = await task_repo.find_by_assignee(employee_id)
    
    # Task statistics
    total_tasks = len(my_tasks)
    completed_tasks = len([t for t in my_tasks if t.get("status") == "done"])
    in_progress_tasks = len([t for t in my_tasks if t.get("status") == "in_progress"])
    blocked_tasks = len([t for t in my_tasks if t.get("status") == "blocked"])
    
    # My stories
    my_stories = await story_repo.find_by_assignee(employee_id)
    
    # My PRs
    my_prs = await pr_repo.find_by_author(employee_id)
    open_prs = [pr for pr in my_prs if pr.get("status") == "open"]
    
    return {
        "role": "DEVELOPER",
        "employee_id": employee_id,
        "name": user["name"],
        "summary": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "in_progress_tasks": in_progress_tasks,
            "blocked_tasks": blocked_tasks,
            "active_stories": len(my_stories),
            "open_prs": len(open_prs),
        },
        "my_tasks": my_tasks[:10],  # Recent 10
        "my_stories": my_stories,
        "my_prs": open_prs,
    }


@router.get("/my-tasks")
async def my_tasks(user: dict = Depends(require_roles("DEVELOPER"))):
    """Get all my tasks with details."""
    task_repo = TaskRepository()
    tasks = await task_repo.find_by_assignee(user["employee_id"])
    
    return {
        "employee_id": user["employee_id"],
        "tasks": tasks,
        "total": len(tasks),
    }


@router.get("/my-prs")
async def my_pull_requests(user: dict = Depends(require_roles("DEVELOPER"))):
    """Get all my pull requests."""
    pr_repo = PRRepository()
    prs = await pr_repo.find_by_author(user["employee_id"])
    
    return {
        "employee_id": user["employee_id"],
        "pull_requests": prs,
        "total": len(prs),
    }
