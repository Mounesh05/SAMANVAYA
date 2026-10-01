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

    projects = await project_repo.find_all({"status": "active"})
    active_sprints = []
    high_risk_count = 0
    completion_values = []

    for project in projects:
        sprints = await sprint_repo.find_by_project(project["id"])
        active_sprints.extend(sprint for sprint in sprints if sprint.get("status") == "active")
        risks = await risk_repo.find_open(project["id"])
        high_risk_count += sum(
            1 for risk in risks if str(risk.get("risk_level", "")).upper() in {"HIGH", "CRITICAL"}
        )
        for sprint in sprints:
            if sprint.get("status") == "active" and sprint.get("completion_pct") is not None:
                completion_values.append(float(sprint["completion_pct"]))

    delivery_confidence = (
        f"{round(sum(completion_values) / len(completion_values))}%"
        if completion_values else None
    )
    
    return {
        "role": "PM",
        "name": user["name"],
        "summary": {
            "active_projects": len(projects),
            "active_sprints": len(active_sprints),
            "high_risks": high_risk_count,
            "delivery_confidence": delivery_confidence,
        },
        "projects": projects,
        "insufficient_data": not projects,
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
    project_repo = ProjectRepository()
    risk_repo = RiskRepository()
    projects = await project_repo.find_all({"status": "active"})
    risks = []
    for project in projects:
        project_risks = await risk_repo.find_open(project["id"])
        risks.extend(
            risk for risk in project_risks
            if str(risk.get("risk_level", "")).upper() in {"HIGH", "CRITICAL"}
        )
    return {
        "risks": risks,
        "total": len(risks),
        "pm": user["name"],
        "insufficient_data": not risks,
    }
