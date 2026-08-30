"""
Project API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from domain.models.project import ProjectCreate, Project
from domain.services.project_service import ProjectService
from core.dependencies import get_current_user, require_roles

router = APIRouter()
project_service = ProjectService()


@router.post("/", response_model=Project, status_code=201)
async def create_project(
    project_data: ProjectCreate,
    user: dict = Depends(require_roles("CEO", "PM", "HR")),
):
    """
    Create a new project.
    Only CEO, PM, and HR can create projects.
    """
    try:
        project = await project_service.create_project(
            project_data, created_by=user["employee_id"]
        )
        return project
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Get project by ID."""
    project = await project_service.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return project


@router.get("/", response_model=list[Project])
async def list_projects(
    org_id: str = Query(..., description="Organization ID"),
    user: dict = Depends(get_current_user),
):
    """List all active projects in an organization."""
    projects = await project_service.get_active_projects(org_id)
    return projects


@router.get("/team/{team_id}", response_model=list[Project])
async def list_team_projects(
    team_id: str,
    user: dict = Depends(get_current_user),
):
    """List all projects assigned to a team."""
    projects = await project_service.get_team_projects(team_id)
    return projects
