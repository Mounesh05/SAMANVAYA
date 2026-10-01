"""
CEO role-specific dashboard endpoints.
Shows: Organization health, delivery confidence, critical risks, portfolio view.
"""

from fastapi import APIRouter, Depends, Query
from core.database import col
from core.dependencies import require_roles
from repositories.project_repository import ProjectRepository
from repositories.risk_repository import RiskRepository
from repositories.sprint_repository import SprintRepository

router = APIRouter()


@router.get("/dashboard")
async def ceo_dashboard(user: dict = Depends(require_roles("CEO"))):
    """
    CEO dashboard - Organization-wide execution health.
    
    Returns:
        - Portfolio health
        - Delivery confidence
        - Critical risks
        - Key metrics
    """
    project_repo = ProjectRepository()
    risk_repo = RiskRepository()
    sprint_repo = SprintRepository()
    projects = await project_repo.find_all({"status": "active"})
    project_risks = [await risk_repo.find_open(project["id"]) for project in projects]
    all_risks = [risk for risks in project_risks for risk in risks]
    critical_risks = [
        risk for risk in all_risks
        if str(risk.get("risk_level", "")).upper() == "CRITICAL"
    ]
    healthy_projects = sum(1 for risks in project_risks if not risks)
    at_risk_projects = sum(1 for risks in project_risks if risks)
    incidents = await col("incidents").count_documents({"status": {"$in": ["open", "active"]}})
    completion_values = []
    for project in projects:
        for sprint in await sprint_repo.find_by_project(project["id"]):
            if sprint.get("status") == "active" and sprint.get("completion_pct") is not None:
                completion_values.append(float(sprint["completion_pct"]))

    return {
        "role": "CEO",
        "name": user["name"],
        "organization_health": {
            "total_projects": len(projects),
            "healthy_projects": healthy_projects,
            "at_risk_projects": at_risk_projects,
            "critical_projects": len(critical_risks),
        },
        "delivery_confidence": (
            f"{round(sum(completion_values) / len(completion_values))}%"
            if completion_values else None
        ),
        "critical_risks": len(critical_risks),
        "active_incidents": incidents,
        "insufficient_data": not projects,
    }


@router.get("/execution-health")
async def execution_health(
    org_id: str = Query(...),
    user: dict = Depends(require_roles("CEO")),
):
    """
    Get organization execution health.
    
    High-level view of all projects and their health.
    """
    project_repo = ProjectRepository()
    risk_repo = RiskRepository()
    
    projects = await project_repo.find_active(org_id)
    
    # Aggregate health across projects
    project_health = []
    for project in projects:
        risks = await risk_repo.find_open(project["id"])
        critical_risks = [r for r in risks if r.get("risk_level") == "CRITICAL"]
        
        project_health.append({
            "project_id": project["id"],
            "name": project["name"],
            "status": project["status"],
            "open_risks": len(risks),
            "critical_risks": len(critical_risks),
        })
    
    return {
        "org_id": org_id,
        "total_projects": len(projects),
        "projects": project_health,
    }


@router.get("/critical-risks")
async def critical_risks(
    org_id: str = Query(...),
    user: dict = Depends(require_roles("CEO")),
):
    """Get all critical risks across the organization."""
    project_repo = ProjectRepository()
    risk_repo = RiskRepository()
    
    projects = await project_repo.find_active(org_id)
    
    all_critical_risks = []
    for project in projects:
        risks = await risk_repo.find_by_level(project["id"], "CRITICAL")
        all_critical_risks.extend(risks)
    
    return {
        "org_id": org_id,
        "critical_risks": all_critical_risks,
        "total": len(all_critical_risks),
    }
