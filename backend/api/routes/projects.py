"""
Project API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from domain.models.project import ProjectCreate, Project
from domain.services.project_service import ProjectService
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import (
    verify_project_access,
    verify_team_access,
    has_global_access,
    has_org_access,
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
        return project
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
    # Get all projects in the org
    all_projects = await project_service.get_active_projects(org_id)
    
    # Filter based on role
    if has_global_access(user):
        # CEO sees everything
        return all_projects
    elif has_org_access(user):
        # PM sees all projects in org
        return all_projects
    else:
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
    return projects
