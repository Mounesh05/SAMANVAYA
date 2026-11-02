"""
DevOps Engineer role-specific dashboard endpoints.
Shows: Pipeline health, deployment status, infrastructure, incidents.
"""

from fastapi import APIRouter, Depends
from core.dependencies import require_roles
from core.database import col

router = APIRouter()


@router.get("/dashboard")
async def devops_dashboard(user: dict = Depends(require_roles("DEVOPS"))):
    """
    DevOps dashboard - CI/CD and infrastructure health.
    """
    pipelines_list = await col("pipelines").find({}, {"_id": 0}).to_list(100)
    deployments_list = await col("deployments").find({}, {"_id": 0}).to_list(100)
    incidents_list = await col("devops_incidents").find({"status": {"$in": ["INVESTIGATING", "MONITORING", "Open", "ACTIVE"]}}, {"_id": 0}).to_list(100)
    health = await col("devops_system_health").find_one({"type": "system_health"}, {"_id": 0})
    
    succ_pipelines = [p for p in pipelines_list if p.get("status") in ["SUCCESS", "Success", "Passed"]]
    succ_rate = round((len(succ_pipelines) / len(pipelines_list) * 100), 1) if pipelines_list else 98.4

    return {
        "role": "DEVOPS",
        "name": user.get("name", "DevOps Engineer"),
        "summary": {
            "active_pipelines": len(pipelines_list),
            "build_success_rate": succ_rate,
            "deployments_today": len(deployments_list),
            "active_incidents": len(incidents_list),
            "system_health": health.get("status", "HEALTHY") if health else "HEALTHY",
        },
        "message": "DevOps dashboard - CI/CD and infrastructure"
    }


@router.get("/pipelines")
async def pipelines(user: dict = Depends(require_roles("DEVOPS"))):
    """Get CI/CD pipeline status."""
    pipes = await col("pipelines").find({}, {"_id": 0}).to_list(100)
    return {
        "pipelines": pipes,
        "message": "Pipeline status"
    }


@router.get("/deployments")
async def deployments(user: dict = Depends(require_roles("DEVOPS"))):
    """Get deployment history and status."""
    deps = await col("deployments").find({}, {"_id": 0}).to_list(100)
    return {
        "deployments": deps,
        "message": "Deployment tracking"
    }
