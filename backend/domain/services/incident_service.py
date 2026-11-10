"""
Incident service: create, update and list production incidents.

Status flow: open -> investigating -> resolved -> closed. A resolved incident
can be reopened (back to investigating), which clears resolved_at. Moving to
resolved sets resolved_at; closing an incident that was never resolved also
sets it, so recovery time is always measurable once an incident is closed.

Linking `caused_by_deployment_id` marks the incident as caused by a change
(cause="change"), which is what DORA's change fail rate and failed deployment
recovery time count. The deployment must belong to the same project.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from domain.models.incident import IncidentCreate, IncidentUpdate
from intelligence.metrics.pull_requests import parse_time
from repositories.incident_repository import DeploymentRepository, IncidentRepository

ALLOWED_TRANSITIONS = {
    "open": {"investigating", "resolved", "closed"},
    "investigating": {"resolved", "closed", "open"},
    "resolved": {"closed", "investigating"},
    "closed": set(),
}


class IncidentError(ValueError):
    """Invalid incident data or status change."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentService:
    def __init__(self) -> None:
        self.incidents = IncidentRepository()
        self.deployments = DeploymentRepository()

    async def _check_deployment(self, deployment_id: Optional[str], project_id: str) -> None:
        if not deployment_id:
            return
        deployment = await self.deployments.find_by_id(deployment_id)
        if not deployment:
            raise IncidentError(f"Deployment {deployment_id} not found")
        if deployment.get("project_id") != project_id:
            raise IncidentError("Deployment belongs to a different project")

    async def create(self, data: IncidentCreate, created_by: Optional[str]) -> Dict[str, Any]:
        started = data.started_at or _now()
        if parse_time(started) is None:
            raise IncidentError("started_at must be an ISO-8601 date-time")
        await self._check_deployment(data.caused_by_deployment_id, data.project_id)
        now = _now()
        incident = {
            "id": f"INC-{uuid.uuid4().hex[:8].upper()}",
            **data.model_dump(exclude={"started_at", "cause"}),
            "cause": data.cause or ("change" if data.caused_by_deployment_id else "unknown"),
            "status": "open",
            "started_at": started,
            "resolved_at": None,
            "closed_at": None,
            "fixed_by_deployment_id": None,
            "resolution": None,
            "created_at": now,
            "created_by": created_by,
            "updated_at": now,
        }
        await self.incidents.insert(dict(incident))
        return incident

    async def update(self, incident_id: str, data: IncidentUpdate) -> Dict[str, Any]:
        incident = await self.incidents.find_by_id(incident_id)
        if not incident:
            raise LookupError("Incident not found")
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        for field in ("caused_by_deployment_id", "fixed_by_deployment_id"):
            if field in changes:
                await self._check_deployment(changes[field], incident["project_id"])
        if changes.get("caused_by_deployment_id") and "cause" not in changes:
            changes["cause"] = "change"

        new_status = changes.get("status")
        current = incident.get("status", "open")
        if new_status and new_status != current:
            if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
                raise IncidentError(f"Cannot move an incident from {current} to {new_status}")
            now = _now()
            if new_status == "resolved":
                changes["resolved_at"] = now
            elif new_status == "closed":
                changes["closed_at"] = now
                if not incident.get("resolved_at"):
                    changes["resolved_at"] = now
            elif new_status in ("investigating", "open") and current == "resolved":
                changes["resolved_at"] = None   # reopened: recovery is not over
        changes["updated_at"] = _now()
        await self.incidents.update({"id": incident_id}, changes)
        return {**incident, **changes}

    async def get(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return await self.incidents.find_by_id(incident_id)

    async def list_for_projects(self, project_ids: List[str], status: Optional[str] = None) -> List[Dict[str, Any]]:
        if not project_ids:
            return []
        items = await self.incidents.find_for_projects(project_ids, status)
        return sorted(items, key=lambda i: str(i.get("started_at") or ""), reverse=True)
