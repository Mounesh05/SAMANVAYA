"""
Tech Lead / Scrum Master role-specific dashboard endpoints.
Shows: Team health, sprint progress, PR queue, blockers.
"""

from fastapi import APIRouter, Depends
from core.permissions import Permission
from core.dependencies import require_permission, require_roles
from repositories.user_repository import UserRepository
from repositories.pr_repository import PRRepository
from repositories.task_repository import TaskRepository
from domain.schemas.hr_views import EmployeeHRView

router = APIRouter()


async def _team_members(user_repo: UserRepository, user: dict) -> list[dict]:
    scope = {"org_id": user["org_id"]} if user.get("org_id") else {"employee_id": user["employee_id"]}
    return await user_repo.find_all({"team_id": user.get("team_id"), "is_active": True, **scope})


def _team_member_view(member: dict) -> dict:
    # Reuse the existing employee allowlist, with the engineering identity that
    # leads legitimately need. Credentials and unknown nested fields never leave.
    return {**EmployeeHRView.from_employee(member).model_dump(mode="json"),
            "github_username": member.get("github_username")}


async def _team_pull_requests(user: dict) -> list[dict]:
    return await PRRepository().find_for_member(user)


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
    task_repo = TaskRepository()
    
    # Team members
    team_members = await _team_members(user_repo, user)
    
    # Active sprints (assuming one active sprint per project)
    # For simplicity, we'll get all sprints - in production, filter by team's projects
    # This would require project_repository and cross-referencing
    
    # PR review queue - all open PRs from team
    all_prs = await _team_pull_requests(user)
    
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
        "team_members": [_team_member_view(member) for member in team_members],
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
    
    team_members = await _team_members(user_repo, user)
    
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
async def review_queue(user: dict = Depends(require_permission(Permission.VIEW_TEAM_DATA))):  # team PRs (Leads)
    """Get PRs waiting for review from team."""
    team_id = user.get("team_id")
    
    if not team_id and not user.get("project_ids"):
        return {"error": "User not assigned to a team or project"}

    all_prs = await _team_pull_requests(user)
    
    pending_review = [
        pr for pr in all_prs
        if pr.get("status") == "open" and pr.get("review_status") == "pending"
    ]
    
    return {
        "team_id": team_id,
        "pending_review": pending_review,
        "total": len(pending_review),
    }
