"""
DORA delivery metrics endpoint.

Reads recorded deployments ("deployments" collection) and incidents and
returns intelligence/metrics/delivery.py's report for one project.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from core.authorization import verify_project_access
from core.dependencies import get_current_user
from intelligence.metrics.delivery import dora_report
from repositories.incident_repository import DeploymentRepository, IncidentRepository

router = APIRouter()


@router.get("/projects/{project_id}/dora")
async def project_dora_metrics(
    project_id: str,
    days: int = Query(90, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Deployment frequency, change lead time, change fail rate, failed deployment
    recovery time and rework rate over the last `days` days, with DORA levels."""
    await verify_project_access(user, project_id)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    deployments = await DeploymentRepository().find_by_project(project_id)
    incidents = await IncidentRepository().find_for_projects([project_id])
    return dora_report(deployments, incidents, start, end)
