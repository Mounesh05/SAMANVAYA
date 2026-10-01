"""
DevOps Engineer role-specific dashboard endpoints.
Shows: Pipeline health, deployment status, infrastructure, incidents.
"""

from fastapi import APIRouter, Depends
from core.dependencies import require_roles
from core.database import col
from datetime import datetime, timezone


async def _devops_snapshot():
    events = await col("webhook_events").find(
        {"event_type": {"$in": ["workflow_run", "deployment", "deployment_status", "check_run"]}},
        {"_id": 0},
    ).sort("created_at", -1).limit(100).to_list(100)
    pipelines = [event for event in events if event.get("event_type") in {"workflow_run", "check_run"}]
    deployments = [event for event in events if event.get("event_type") in {"deployment", "deployment_status"}]
    successful = 0
    failed = 0
    for event in pipelines + deployments:
        status = str(
            event.get("payload", {}).get("workflow_run", {}).get("conclusion")
            or event.get("payload", {}).get("deployment_status", {}).get("state")
            or event.get("payload", {}).get("check_run", {}).get("conclusion")
            or ""
        ).lower()
        if status in {"success", "successful", "passed"}:
            successful += 1
        elif status in {"failure", "failed", "failure", "cancelled", "error"}:
            failed += 1
    return {
        "events": events,
        "pipelines": pipelines,
        "deployments": deployments,
        "successful": successful,
        "failed": failed,
    }

router = APIRouter()


@router.get("/dashboard")
async def devops_dashboard(user: dict = Depends(require_roles("DEVOPS"))):
    """
    DevOps dashboard - CI/CD and infrastructure health.
    
    Returns:
        - Pipeline status
        - Deployment health
        - Infrastructure status
        - Active incidents
    """
    snapshot = await _devops_snapshot()
    total = snapshot["successful"] + snapshot["failed"]
    return {
        "role": "DEVOPS",
        "name": user["name"],
        "summary": {
            "active_pipelines": len(snapshot["pipelines"]),
            "build_success_rate": round(snapshot["successful"] / total * 100, 2) if total else None,
            "deployments_today": len(snapshot["deployments"]),
            "active_incidents": snapshot["failed"],
            "system_health": "DEGRADED" if snapshot["failed"] else "HEALTHY" if total else None,
        },
        "pipelines": snapshot["pipelines"],
        "deployments": snapshot["deployments"],
        "insufficient_data": not snapshot["events"],
    }


@router.get("/pipelines")
async def pipelines(user: dict = Depends(require_roles("DEVOPS"))):
    """Get CI/CD pipeline status."""
    snapshot = await _devops_snapshot()
    return {"pipelines": snapshot["pipelines"], "total": len(snapshot["pipelines"]), "insufficient_data": not snapshot["pipelines"]}


@router.get("/deployments")
async def deployments(user: dict = Depends(require_roles("DEVOPS"))):
    """Get deployment history and status."""
    snapshot = await _devops_snapshot()
    return {"deployments": snapshot["deployments"], "total": len(snapshot["deployments"]), "insufficient_data": not snapshot["deployments"]}
