"""
Tech Lead / Scrum Master role-specific dashboard endpoints.
Shows: Team health, sprint progress, PR queue, blockers.
"""

from fastapi import APIRouter, Depends
from core.dependencies import require_roles
from repositories.user_repository import UserRepository
from repositories.sprint_repository import SprintRepository
from repositories.story_repository import StoryRepository
from repositories.pr_repository import PRRepository
from repositories.task_repository import TaskRepository

router = APIRouter()


@router.get("/dashboard")
async def lead_dashboard(user: dict = Depends(require_roles("LEAD"))):
    """
    Team Lead dashboard - Team engineering health.
    
    Returns:
        - Team members
        - Active sprint progress
        - PR review queue
        - Blocked work items
        - Team workload
    """
    team_id = user.get("team_id")
    
    if not team_id:
        return {"error": "User not assigned to a team"}
    
    user_repo = UserRepository()
    sprint_repo = SprintRepository()
    story_repo = StoryRepository()
    pr_repo = PRRepository()
    task_repo = TaskRepository()
    
    # Team members
    team_members = await user_repo.find_by_team(team_id)
    
    # Active sprints (assuming one active sprint per project)
    # For simplicity, we'll get all sprints - in production, filter by team's projects
    # This would require project_repository and cross-referencing
    
    # PR review queue - all open PRs from team
    all_prs = []
    for member in team_members:
        member_prs = await pr_repo.find_by_author(member["employee_id"])
        all_prs.extend(member_prs)
    
    open_prs = [pr for pr in all_prs if pr.get("status") == "open"]
    high_risk_prs = [pr for pr in open_prs if pr.get("risk_level") in ["HIGH", "CRITICAL"]]
    
    # Blocked items
    all_tasks = []
    for member in team_members:
        member_tasks = await task_repo.find_by_assignee(member["employee_id"])
        all_tasks.extend(member_tasks)
    
    blocked_tasks = [t for t in all_tasks if t.get("status") == "blocked"]
    
    return {
        "role": "LEAD",
        "team_id": team_id,
        "name": user["name"],
        "summary": {
            "team_size": len(team_members),
            "open_prs": len(open_prs),
            "high_risk_prs": len(high_risk_prs),
            "blocked_tasks": len(blocked_tasks),
            "total_active_tasks": len([t for t in all_tasks if t.get("status") in ["in_progress", "todo"]]),
        },
        "team_members": team_members,
        "pr_review_queue": open_prs[:15],  # Top 15
        "high_risk_prs": high_risk_prs,
        "blockers": blocked_tasks,
    }


@router.get("/team")
async def team_overview(user: dict = Depends(require_roles("LEAD"))):
    """Get team members and their workload."""
    team_id = user.get("team_id")
    
    if not team_id:
        return {"error": "User not assigned to a team"}
    
    user_repo = UserRepository()
    task_repo = TaskRepository()
    
    team_members = await user_repo.find_by_team(team_id)
    
    # Calculate workload for each member
    team_workload = []
    for member in team_members:
        tasks = await task_repo.find_by_assignee(member["employee_id"])
        workload = {
            "employee_id": member["employee_id"],
            "name": member["name"],
            "total_tasks": len(tasks),
            "in_progress": len([t for t in tasks if t.get("status") == "in_progress"]),
            "blocked": len([t for t in tasks if t.get("status") == "blocked"]),
        }
        team_workload.append(workload)
    
    return {
        "team_id": team_id,
        "team_members": team_workload,
    }


@router.get("/review-queue")
async def review_queue(user: dict = Depends(require_roles("LEAD"))):
    """Get PRs waiting for review from team."""
    team_id = user.get("team_id")
    
    if not team_id:
        return {"error": "User not assigned to a team"}
    
    user_repo = UserRepository()
    pr_repo = PRRepository()
    
    team_members = await user_repo.find_by_team(team_id)
    
    all_prs = []
    for member in team_members:
        member_prs = await pr_repo.find_by_author(member["employee_id"])
        all_prs.extend(member_prs)
    
    pending_review = [
        pr for pr in all_prs
        if pr.get("status") == "open" and pr.get("review_status") == "pending"
    ]
    
    return {
        "team_id": team_id,
        "pending_review": pending_review,
        "total": len(pending_review),
    }
