"""
DevOps Engineer role-specific dashboard endpoints.
Shows: Pipeline health, deployment status, infrastructure, incidents.

Only the projects the user can access are shown (webhook events, deployments
and incidents are filtered by project). Previously every project's events
were shown, "deployments_today" counted deployment events among the latest
100 events of any date, and "active_incidents" counted failed builds.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from core.authorization import get_accessible_project_ids
from core.database import col
from core.dependencies import require_roles

ACTIVE_INCIDENT_STATUSES = ["open", "investigating"]
_PAGE_STATUS = {"success": "success", "failure": "failed", "error": "failed", "in_progress": "pending"}


def for_deployments_page(d: dict) -> dict:
    """A deployment record in the shape the Deployments page renders
    (id, service, environment, version, status, deployed_by, deployed_at)."""
    return {
        **d,
        "service": d.get("repository"),
        "version": (d.get("sha") or "")[:7] or None,
        "status": _PAGE_STATUS.get(d.get("status"), d.get("status")),
        "deployed_at": d.get("finished_at") or d.get("created_at"),
        "rollback_available": bool(d.get("production") and d.get("previous_deployment_id")),
    }
_SUCCESS = {"success", "successful", "passed"}
_FAILURE = {"failure", "failed", "cancelled", "error", "timed_out"}


def _event_status(event: dict) -> str:
    payload = event.get("payload", {})
    return str(
        payload.get("workflow_run", {}).get("conclusion")
        or payload.get("deployment_status", {}).get("state")
        or payload.get("check_run", {}).get("conclusion")
        or ""
    ).lower()


async def _devops_snapshot(user: dict):
    project_ids = await get_accessible_project_ids(user)
    events = await col("webhook_events").find(
        {"event_type": {"$in": ["workflow_run", "deployment", "deployment_status", "check_run"]},
         "project_id": {"$in": project_ids}},
        {"_id": 0},
    ).sort("created_at", -1).limit(100).to_list(100)

    pipelines = [event for event in events if event.get("event_type") in {"workflow_run", "check_run"}]
    deployment_events = [event for event in events if event.get("event_type") in {"deployment", "deployment_status"}]
    successful = sum(1 for e in pipelines if _event_status(e) in _SUCCESS)
    failed = sum(1 for e in pipelines if _event_status(e) in _FAILURE)

    today = datetime.now(timezone.utc).date().isoformat()
    deployments = await col("deployments").find(
        {"project_id": {"$in": project_ids}}, {"_id": 0},
    ).sort("created_at", -1).limit(100).to_list(100)
    deployments_today = sum(
        1 for d in deployments
        if d.get("production") and str(d.get("finished_at") or d.get("created_at") or "")[:10] == today
    )
    active_incidents = await col("incidents").count_documents(
        {"project_id": {"$in": project_ids}, "status": {"$in": ACTIVE_INCIDENT_STATUSES}}
    )
    return {
        "events": events,
        "pipelines": pipelines,
        "deployment_events": deployment_events,
        "deployments": deployments,
        "deployments_today": deployments_today,
        "active_incidents": active_incidents,
        "successful": successful,
        "failed": failed,
    }


router = APIRouter()


@router.get("/dashboard")
async def devops_dashboard(user: dict = Depends(require_roles("DEVOPS"))):
    """
    DevOps dashboard - CI/CD and infrastructure health, for the user's projects.

    Returns:
        - Pipeline status (success rate of finished workflow runs and checks)
        - Production deployments today
        - Active incidents (open or investigating)
    """
    snapshot = await _devops_snapshot(user)
    total = snapshot["successful"] + snapshot["failed"]
    unhealthy = snapshot["failed"] or snapshot["active_incidents"]
    return {
        "role": "DEVOPS",
        "name": user["name"],
        "summary": {
            "active_pipelines": len(snapshot["pipelines"]),
            "build_success_rate": round(snapshot["successful"] / total * 100, 2) if total else None,
            "deployments_today": snapshot["deployments_today"],
            "active_incidents": snapshot["active_incidents"],
            "failed_runs": snapshot["failed"],
            "system_health": "DEGRADED" if unhealthy else "HEALTHY" if total or snapshot["deployments"] else None,
        },
        "pipelines": snapshot["pipelines"],
        "deployments": [for_deployments_page(d) for d in snapshot["deployments"]],
        "insufficient_data": not snapshot["events"] and not snapshot["deployments"],
    }


@router.get("/pipelines")
async def pipelines(user: dict = Depends(require_roles("DEVOPS", "QA", "LEAD"))):
    """Get CI/CD pipeline status."""
    snapshot = await _devops_snapshot(user)
    return {"pipelines": snapshot["pipelines"], "total": len(snapshot["pipelines"]), "insufficient_data": not snapshot["pipelines"]}


@router.get("/deployments")
async def deployments(user: dict = Depends(require_roles("DEVOPS", "LEAD"))):
    """Get deployment history and status (recorded deployments, newest first)."""
    snapshot = await _devops_snapshot(user)
    items = [for_deployments_page(d) for d in snapshot["deployments"]]
    return {"deployments": items, "total": len(items), "insufficient_data": not items}
