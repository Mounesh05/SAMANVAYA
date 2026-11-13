"""
Project API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from core.audit import AuditAction, log_audit
from core.database import col
from core.permissions import get_user_permissions
from domain.models.project import ProjectCreate, Project
from domain.services.project_service import ProjectService
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import (
    verify_project_access,
    verify_team_access,
    has_global_access,
    managed_project_ids,
)

router = APIRouter()
project_service = ProjectService()


@router.post("/", response_model=Project, status_code=201)
async def create_project(
    project_data: ProjectCreate,
    user: dict = Depends(require_permission(Permission.CREATE_PROJECT)),
):
    """
    Create a new project.
    Requires CREATE_PROJECT permission (PM role by default).
    """
    try:
        project = await project_service.create_project(
            project_data, created_by=user["employee_id"]
        )
        # CR-013 (D2-A): the PM who creates a project manages it.
        if (user.get("role") or "").upper() == "PM":
            project_id = project.id if hasattr(project, "id") else project.get("id")
            await col("users").update_one({"employee_id": user["employee_id"]},
                                          {"$addToSet": {"project_ids": project_id}})
        return project
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Get project by ID. User must have access to the project."""
    # Verify user has access to this project
    await verify_project_access(user, project_id)

    project = await project_service.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.get("/", response_model=list[Project])
async def list_projects(
    org_id: str = Query(..., description="Organization ID"),
    user: dict = Depends(get_current_user),
):
    """
    List all active projects in an organization.
    Results are filtered based on user's role and project assignments.
    """
    # CR-013: never another organisation's projects.
    if user.get("org_id") and org_id != user["org_id"]:
        raise HTTPException(status_code=403, detail="You can only list your own organisation's projects")

    # Get all projects in the org
    all_projects = await project_service.get_active_projects(org_id)

    # Filter based on role
    if has_global_access(user):
        # CEO sees everything (in their organisation, checked above)
        return all_projects
    else:
        # CR-013: PMs fall here too and see the projects they manage.
        # Others see projects assigned directly or through their team.
        user_project_ids = set(user.get("project_ids", []))
        user_team_id = user.get("team_id")
        filtered_projects = [
            p for p in all_projects
            if (
                (p.id if hasattr(p, "id") else p.get("id")) in user_project_ids
                or (
                    user_team_id
                    and (p.team_id if hasattr(p, "team_id") else p.get("team_id"))
                    == user_team_id
                )
            )
        ]
        return filtered_projects


@router.get("/team/{team_id}", response_model=list[Project])
async def list_team_projects(
    team_id: str,
    user: dict = Depends(get_current_user),
):
    """List all projects assigned to a team. User must have access to the team."""
    # Verify user has access to this team
    await verify_team_access(user, team_id)

    projects = await project_service.get_team_projects(team_id)
    if (user.get("role") or "").upper() == "PM":  # CR-013: only the projects they manage
        managed = managed_project_ids(user)
        projects = [p for p in projects if (p.id if hasattr(p, "id") else p.get("id")) in managed]
    return projects


# ── CR-013: project membership ──────────────────────────────────────────────

class MemberRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, max_length=100)


def _can_assign_anyone(user: dict) -> bool:
    return Permission.ASSIGN_PROJECT in get_user_permissions(
        user.get("role", ""), user.get("is_admin", False), user.get("designation"))


async def _authorize_membership_change(user: dict, project_id: str, target: dict) -> None:
    """CEO and admins (ASSIGN_PROJECT) change any member; a PM manages the
    non-PM members of their own projects (D1-A)."""
    if _can_assign_anyone(user):
        return
    if (user.get("role") or "").upper() == "PM" and project_id in managed_project_ids(user):
        if (target.get("role") or "").upper() == "PM":
            raise HTTPException(status_code=403, detail="Only the CEO or an admin can assign project managers")
        return
    raise HTTPException(status_code=403, detail="You can't change this project's members")


async def _project_and_member(user: dict, project_id: str, employee_id: str):
    project = await col("projects").find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    target = await col("users").find_one({"employee_id": employee_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found")
    await _authorize_membership_change(user, project_id, target)
    return project, target


@router.get("/{project_id}/members")
async def list_project_members(project_id: str, user: dict = Depends(get_current_user)):
    """People on a project: assigned directly, or through the team that owns it."""
    await verify_project_access(user, project_id)
    project = await col("projects").find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query = {"$or": [{"project_ids": project_id}] + ([{"team_id": project["team_id"]}] if project.get("team_id") else [])}
    people = await col("users").find(
        {**query, "is_active": {"$ne": False}},
        {"_id": 0, "employee_id": 1, "name": 1, "role": 1, "project_ids": 1, "team_id": 1},
    ).to_list(length=1000)
    members = [{
        "employee_id": p["employee_id"], "name": p.get("name"), "role": p.get("role"),
        "link": "assigned" if project_id in (p.get("project_ids") or []) else "team",
    } for p in people]
    return {"project_id": project_id, "members": sorted(members, key=lambda m: (m["link"], m["role"] or "", m["employee_id"])),
            "can_manage": _can_assign_anyone(user) or project_id in managed_project_ids(user)}


@router.post("/{project_id}/members", status_code=201)
async def add_project_member(project_id: str, request: MemberRequest, user: dict = Depends(get_current_user)):
    project, target = await _project_and_member(user, project_id, request.employee_id)
    if target.get("is_active", True) is False:
        raise HTTPException(status_code=422, detail="Only active employees can be added")
    project_org = project.get("org_id") or project.get("organization_id")
    if target.get("org_id") and project_org and target["org_id"] != project_org:
        raise HTTPException(status_code=422, detail="The employee belongs to another organisation")
    old = list(target.get("project_ids") or [])
    if project_id in old:
        return {"project_id": project_id, "employee_id": request.employee_id, "changed": False}
    await col("users").update_one({"employee_id": request.employee_id}, {"$addToSet": {"project_ids": project_id}})
    await log_audit(action=AuditAction.USER_UPDATED, actor=user, resource_type="employee",
                    resource_id=request.employee_id,
                    details={"field": "project_ids", "old": old, "new": old + [project_id], "project_id": project_id})
    return {"project_id": project_id, "employee_id": request.employee_id, "changed": True}


@router.delete("/{project_id}/members/{employee_id}")
async def remove_project_member(project_id: str, employee_id: str, user: dict = Depends(get_current_user)):
    _, target = await _project_and_member(user, project_id, employee_id)
    old = list(target.get("project_ids") or [])
    if project_id not in old:
        return {"project_id": project_id, "employee_id": employee_id, "changed": False}
    await col("users").update_one({"employee_id": employee_id}, {"$pull": {"project_ids": project_id}})
    await log_audit(action=AuditAction.USER_UPDATED, actor=user, resource_type="employee", resource_id=employee_id,
                    details={"field": "project_ids", "old": old, "new": [p for p in old if p != project_id],
                             "project_id": project_id})
    return {"project_id": project_id, "employee_id": employee_id, "changed": True}
