"""Exact-revision production observations from accepted GitHub deployment statuses."""

import re
from datetime import datetime, timezone

from fastapi import HTTPException

from core.database import col
from domain.services.ai_evidence_service import _repository


def capture_production_status(payload: dict, organization: str | None) -> dict | None:
    """Capture the project tenant and provider identity at the time of delivery."""
    deployment = payload.get("deployment")
    status = payload.get("deployment_status")
    if not isinstance(deployment, dict) or not isinstance(status, dict) or not organization:
        return None
    revision = deployment.get("sha")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision):
        return None
    environment = deployment.get("environment")
    # A provider-classified production environment may use its own name.
    is_production = deployment.get("production_environment")
    if is_production is not True and (is_production is not None or str(environment).lower() != "production"):
        return None
    if status.get("environment") and str(status["environment"]).lower() != str(environment).lower():
        return None
    deployment_id, status_id = deployment.get("id"), status.get("id")
    if any(type(value) is not int or value <= 0 for value in (deployment_id, status_id)):
        return None
    try:
        observed = datetime.fromisoformat(status["created_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if observed.tzinfo is None or not isinstance(status.get("state"), str):
        return None
    return {
        "org_id": organization, "revision": revision.lower(),
        "deployment_id": deployment_id, "status_id": status_id, "state": status["state"],
        "observed_at": observed.astimezone(timezone.utc).isoformat(),
    }


async def scoped_production_status(payload: dict, project: dict, repository: str) -> dict | None:
    org_id = project.get("org_id")
    if not isinstance(org_id, str) or not org_id.strip() or project.get("organization_id", org_id) != org_id:
        return None
    observation = capture_production_status(payload, org_id)
    if not observation:
        return None
    try:
        owner, name = await _repository(project["id"], org_id)
    except HTTPException as exc:
        if exc.status_code == 409:
            return None
        raise
    if repository.casefold() != f"{owner}/{name}".casefold():
        return None
    return {**observation, "repository": repository.lower()}


async def production_evidence(project_id: str, repository: str, revision: str, org_id: str) -> dict:
    """Latest provider observation for this commit, which can outlive the running release."""
    event = await col("webhook_events").find_one(
        {"source": "github", "event_type": "deployment_status", "project_id": project_id,
         "production.org_id": org_id, "production.repository": repository.lower(),
         "production.revision": revision.lower()},
        {"_id": 0, "production": 1},
        sort=[("production.observed_at", -1), ("production.status_id", -1)],
    )
    if not event:
        return {"status": "unknown", "reason": "No verified production deployment status for this revision."}
    observation = event["production"]
    state = observation["state"]
    result = {"success": "deployed", "error": "failed", "failure": "failed"}.get(state, "unknown")
    return {"status": result, "deployment_id": observation["deployment_id"], "observed_at": observation["observed_at"],
            "reason": f"GitHub reported {state} for production deployment #{observation['deployment_id']} on this revision."}
