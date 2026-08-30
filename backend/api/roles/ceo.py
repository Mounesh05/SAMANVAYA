"""
CEO role-specific dashboard endpoints.
Shows: Organization health, delivery confidence, critical risks, portfolio view.
"""

from fastapi import APIRouter, Depends, Query
from core.dependencies import require_roles
from repositories.project_repository import ProjectRepository
from repositories.risk_repository import RiskRepository

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
    return {
        "role": "CEO",
        "name": user["name"],
        "organization_health": {
            "total_projects": 0,
            "healthy_projects": 0,
            "at_risk_projects": 0,
            "critical_projects": 0,
        },
        "delivery_confidence": "78%",
        "critical_risks": 0,
        "active_incidents": 0,
        "message": "CEO dashboard - organization-wide view"
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
