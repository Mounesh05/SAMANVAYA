"""
Project Manager role-specific dashboard endpoints.
Shows: Project health, delivery confidence, sprint progress, risks.
"""

from fastapi import APIRouter, Depends, Query
from core.dependencies import require_roles
from repositories.project_repository import ProjectRepository
from repositories.sprint_repository import SprintRepository
from repositories.story_repository import StoryRepository
from repositories.risk_repository import RiskRepository
from domain.services.sprint_service import SprintService

router = APIRouter()


@router.get("/dashboard")
async def pm_dashboard(user: dict = Depends(require_roles("PM"))):
    """
    PM dashboard - Project execution overview.
    
    Returns:
        - Active projects
        - Sprint health (Plan vs Reality)
        - Delivery risks
        - Resource allocation
    """
    project_repo = ProjectRepository()
    sprint_repo = SprintRepository()
    risk_repo = RiskRepository()
    
    # Get all active projects (should filter by PM's org/portfolio in production)
    # For now, we'll show sample data
    
    return {
        "role": "PM",
        "name": user["name"],
        "summary": {
            "active_projects": 0,
            "active_sprints": 0,
            "high_risks": 0,
            "delivery_confidence": "MEDIUM",
        },
        "message": "PM dashboard - connect to projects via org_id filter"
    }


@router.get("/projects")
async def pm_projects(
    org_id: str = Query(...),
    user: dict = Depends(require_roles("PM")),
):
    """Get all projects managed by PM."""
    project_repo = ProjectRepository()
    projects = await project_repo.find_active(org_id)
    
    return {
        "org_id": org_id,
        "projects": projects,
        "total": len(projects),
    }


@router.get("/project/{project_id}/health")
async def project_health(
    project_id: str,
    user: dict = Depends(require_roles("PM")),
):
    """
    Get comprehensive project health: Plan vs Reality.
    
    This is the PM's main view of project execution.
    """
    sprint_repo = SprintRepository()
    story_repo = StoryRepository()
    risk_repo = RiskRepository()
    sprint_service = SprintService()
    
    # Get active sprint
    active_sprint = await sprint_repo.find_active(project_id)
    
    if not active_sprint:
        return {"message": "No active sprint", "project_id": project_id}
    
    # Get sprint health
    sprint_health = await sprint_service.calculate_sprint_health(active_sprint["id"])
    
    # Get open risks
    risks = await risk_repo.find_open(project_id)
    
    return {
        "project_id": project_id,
        "active_sprint": active_sprint,
        "sprint_health": sprint_health,
        "open_risks": risks,
        "risk_count": len(risks),
    }


@router.get("/risks")
async def pm_risks(user: dict = Depends(require_roles("PM"))):
    """Get all high-priority risks across projects."""
    # This would aggregate risks across PM's projects
    return {
        "message": "PM risks endpoint - aggregate across projects",
        "pm": user["name"],
    }
