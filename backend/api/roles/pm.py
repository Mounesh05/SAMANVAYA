"""
Project Manager role-specific dashboard endpoints.
Shows: Project health, delivery confidence, sprint progress, risks.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from core.dependencies import require_roles
from repositories.project_repository import ProjectRepository
from repositories.sprint_repository import SprintRepository
from repositories.risk_repository import RiskRepository
from domain.services.sprint_service import SprintService
from domain.services.pm_blocked_work import AgeGroup, blocked_work, managed_project_query
from core.organization import resolve_organization
from core.authorization import managed_project_ids

router = APIRouter()


@router.get("/blocked-work")
async def pm_blocked_work(group: AgeGroup = "all", offset: int = Query(0, ge=0),
                          limit: int = Query(12, ge=1, le=100), user: dict = Depends(require_roles("PM"))):
    return await blocked_work(user, group, offset, limit)


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

    portfolio = await project_repo.find_all(managed_project_query(user))
    projects = [project for project in portfolio if project.get("status") == "active"]
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
            # Live from the sprint's tasks: the stored figure is only final at completion.
            if sprint.get("status") == "active":
                live = await SprintService().live_completion_pct(sprint["id"])
                if live is not None:
                    completion_values.append(live)

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
        "portfolio": portfolio,
        "insufficient_data": not projects,
    }


@router.get("/projects")
async def pm_projects(
    org_id: str | None = Query(None),
    user: dict = Depends(require_roles("PM")),
):
    """Get all projects managed by PM."""
    org_id = resolve_organization(user, org_id)
    project_repo = ProjectRepository()
    projects = await project_repo.find_all({**managed_project_query(user), "status": "active"})
    
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
    org = resolve_organization(user, None)
    if project_id not in managed_project_ids(user):
        raise HTTPException(403, "You do not manage this project")
    project = await ProjectRepository().find_by_id(project_id)
    if (not project or user.get("organization_id", org) != org or
            project.get("org_id") != org or project.get("organization_id", org) != org):
        raise HTTPException(404, "Project unavailable")
    sprint_repo = SprintRepository()
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
    projects = await project_repo.find_all({**managed_project_query(user), "status": "active"})
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
