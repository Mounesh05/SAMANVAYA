"""DevOps reporting from the caller's linked repositories and incident records."""

from datetime import datetime, timedelta, timezone
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from core.authorization import get_accessible_project_ids
from core.database import col
from core.dependencies import get_current_user, require_permission, require_roles
from core.permissions import Permission
from domain.services.ai_evidence_service import _repository
from repositories.pr_repository import PRRepository


router = APIRouter()
PAGE_SIZE = 50


def _window():
    now = datetime.now(timezone.utc)
    today = now.date()
    start = today - timedelta(days=13)
    return {"start": start.isoformat(), "today": today.isoformat(), "end": (today + timedelta(days=1)).isoformat(),
            "as_of": now.isoformat()}


def _dates(window):
    start = datetime.fromisoformat(window["start"]).date()
    length = (datetime.fromisoformat(window["end"]).date() - start).days
    return [(start + timedelta(days=offset)).isoformat() for offset in range(length)]


def _reported_time(window):
    dates = "|".join(_dates(window))
    # GitHub returns ISO UTC timestamps. Filter incomplete legacy values before
    # grouping so every counted row also has a corresponding day drilldown.
    timestamp = rf"^(?:{dates})T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|\+00:00)$"
    return {"$gte": window["start"], "$lt": window["end"], "$regex": timestamp, "$not": {"$type": "array"}}


async def _source_scope(user):
    organization = user.get("org_id")
    projects = await get_accessible_project_ids(user) if user.get("organization_id", organization) == organization else []
    pairs = []
    for project in projects:
        try:
            owner, name = await _repository(project, organization)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            continue
        repository = re.compile("^" + re.escape(f"{owner}/{name}") + "$", re.I)
        pairs.append({"project_id": project, "payload.repository.full_name": {"$regex": repository, "$not": {"$type": "array"}}})
    scope = PRRepository._project_scope(projects, organization)
    events = {**scope, "source": "github", "$or": pairs} if pairs else {"_id": {"$in": []}}
    return events, scope


def _attempts(scope, window):
    run = "$payload.workflow_run"
    identity = {"$type": "number", "$gt": 0, "$not": {"$type": "array"}}
    match = {**scope, "event_type": "workflow_run", "payload.workflow_run.id": identity,
             "payload.workflow_run.run_attempt": identity, "payload.workflow_run.updated_at": _reported_time(window)}
    # Prefer a completed observation on provider timestamp ties. Delivery order
    # can differ from GitHub's lifecycle order.
    return [
        {"$match": match},
        {"$project": {"_id": 0, "repository": {"$toLower": "$payload.repository.full_name"},
                      "id": run + ".id", "attempt": run + ".run_attempt", "name": run + ".name",
                      "branch": run + ".head_branch", "sha": run + ".head_sha",
                      "status": run + ".status", "conclusion": run + ".conclusion", "updated_at": run + ".updated_at",
                      "completed": {"$eq": [run + ".status", "completed"]}}},
        {"$sort": {"updated_at": -1, "completed": -1}},
        {"$group": {"_id": {"repo": "$repository", "run": "$id", "attempt": "$attempt"}, "row": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$row"}},
        {"$addFields": {"outcome": {"$switch": {"branches": [
            {"case": {"$ne": ["$completed", True]}, "then": "other"},
            {"case": {"$eq": ["$conclusion", "success"]}, "then": "success"},
            {"case": {"$in": ["$conclusion", ["failure", "timed_out", "startup_failure"]]}, "then": "failed"},
            {"case": {"$eq": ["$conclusion", "cancelled"]}, "then": "cancelled"},
        ], "default": "other"}}}},
    ]


def _deployments(scope, window, repository=None, deployment_id=None):
    dep, status = "$payload.deployment", "$payload.deployment_status"
    match = {**scope, "event_type": {"$in": ["deployment", "deployment_status"]},
             "payload.deployment.id": {"$type": "number", "$gt": 0, "$not": {"$type": "array"}}}
    if deployment_id is None:
        match["payload.deployment.created_at"] = _reported_time(window)
    else:
        match["payload.deployment.id"] = {"$eq": deployment_id, "$not": {"$type": "array"}}
    if repository:
        match["payload.repository.full_name"] = re.compile("^" + re.escape(repository) + "$", re.I)
    return [
        {"$match": match},
        {"$project": {"_id": 0, "id": dep + ".id", "repository": {"$toLower": "$payload.repository.full_name"},
                      "environment": {"$ifNull": [status + ".environment", dep + ".environment"]},
                      "status": {"$ifNull": [status + ".state", "unconfirmed"]}, "sha": dep + ".sha",
                      "created_at": dep + ".created_at", "deployed_by": dep + ".creator.login",
                      "updated_at": {"$ifNull": [status + ".created_at", dep + ".created_at"]},
                      "status_id": {"$ifNull": [status + ".id", 0]}}},
        {"$sort": {"updated_at": -1, "status_id": -1}},
        {"$group": {"_id": {"repo": "$repository", "deployment": "$id"}, "row": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$row"}},
    ]


async def _aggregate(stages):
    result = await col("webhook_events").aggregate(stages, allowDiskUse=True).to_list(1)
    return result[0]


def _count(rows):
    return rows[0]["value"] if rows else 0


@router.get("/reporting/dashboard")
async def devops_dashboard(user: dict = Depends(require_roles("DEVOPS"))):
    events, projects = await _source_scope(user)
    window = _window()
    attempts = await _aggregate([*_attempts(events, window), {"$facet": {
        "counts": [{"$group": {"_id": {"date": {"$substr": ["$updated_at", 0, 10]}, "outcome": "$outcome"},
                               "count": {"$sum": 1}}}],
        "recent": [{"$sort": {"updated_at": -1, "repository": 1, "id": -1, "attempt": -1}}, {"$limit": 8}],
    }}])
    deployments = await _aggregate([*_deployments(events, window), {"$facet": {
        "today": [{"$match": {"created_at": {"$gte": window["today"]}}}, {"$count": "value"}],
        "recent": [{"$sort": {"updated_at": -1, "repository": 1, "id": -1}}, {"$limit": 8}],
    }}])
    incidents = await col("incidents").count_documents({**projects, "status": {"$in": ["open", "investigating"]}})
    totals = dict.fromkeys(("success", "failed", "cancelled", "other"), 0)
    days = {day: dict(totals) for day in _dates(window)}
    for item in attempts["counts"]:
        day, outcome = item["_id"]["date"], item["_id"]["outcome"]
        days[day][outcome] += item["count"]
        totals[outcome] += item["count"]
    decided = totals["success"] + totals["failed"]
    return {"role": "DEVOPS", "name": user.get("name"), "window": window, "outcomes": totals,
            "daily": [{"date": day, **counts} for day, counts in days.items()],
            "pipelines": attempts["recent"], "deployments": deployments["recent"],
            "summary": {"workflow_attempts": sum(totals.values()), "decided_attempts": decided,
                        "deployments_today": _count(deployments["today"]), "active_incidents": incidents,
                        "build_success_rate": round(100 * totals["success"] / decided, 2) if decided else None},
            "insufficient_data": not (attempts["recent"] or deployments["recent"] or incidents)}


async def _page(stages, page, sort):
    result = await _aggregate([*stages, {"$facet": {
        "count": [{"$count": "value"}],
        "rows": [{"$sort": sort}, {"$skip": (page - 1) * PAGE_SIZE}, {"$limit": PAGE_SIZE}],
    }}])
    return result["rows"], {"page": page, "page_size": PAGE_SIZE, "total": _count(result["count"])}


@router.get("/reporting/pipelines")
async def pipelines(user: dict = Depends(require_permission(Permission.VIEW_PIPELINES)),
                    page: Annotated[int, Query(ge=1, le=1000000)] = 1,
                    outcome: Literal["success", "failed", "cancelled", "other", "decided"] | None = None,
                    day: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None):
    scope, _ = await _source_scope(user)
    window = _window()
    stages = _attempts(scope, window)
    if outcome:
        stages.append({"$match": {"outcome": {"$in": ["success", "failed"]} if outcome == "decided" else outcome}})
    if day:
        stages.append({"$match": {"updated_at": {"$regex": "^" + re.escape(day) + "T"}}})
    rows, pagination = await _page(stages, page, {"updated_at": -1, "repository": 1, "id": -1, "attempt": -1})
    return {"pipelines": rows, **pagination, "window": window, "insufficient_data": not pagination["total"]}


@router.get("/reporting/deployments")
async def deployments(user: dict = Depends(require_permission(Permission.VIEW_DEPLOYMENTS)),
                      page: Annotated[int, Query(ge=1, le=1000000)] = 1, today: bool = False,
                      repository: Annotated[str | None, Query(pattern=r"^[\w.-]+/[\w.-]+$", max_length=205)] = None,
                      deployment_id: Annotated[int | None, Query(gt=0, le=9223372036854775807)] = None):
    if deployment_id is not None and not repository:
        raise HTTPException(422, "Choose a repository for this deployment")
    scope, _ = await _source_scope(user)
    window = _window()
    stages = _deployments(scope, window, repository, deployment_id)
    if today:
        stages.append({"$match": {"created_at": {"$gte": window["today"], "$lt": window["end"]}}})
    rows, pagination = await _page(stages, page, {"updated_at": -1, "repository": 1, "id": -1})
    return {"deployments": rows, **pagination, "window": window, "insufficient_data": not pagination["total"]}


async def _recent_events(user):
    """Keep the original event-history contract for existing API consumers."""
    scope, _ = await _source_scope(user)
    events = await col("webhook_events").find(
        {**scope, "event_type": {"$in": ["workflow_run", "check_run", "deployment", "deployment_status"]}},
        {"_id": 0},
    ).sort("created_at", -1).limit(100).to_list(100)
    return {
        "pipelines": [event for event in events if event["event_type"] in {"workflow_run", "check_run"}],
        "deployments": [event for event in events if event["event_type"] in {"deployment", "deployment_status"}],
    }


@router.get("/dashboard")
async def dashboard_events(dashboard: dict = Depends(devops_dashboard), user: dict = Depends(get_current_user)):
    # Pipeline inventory and infrastructure health need their own data sources.
    dashboard["summary"].update(active_pipelines=None, system_health=None)
    return {**dashboard, **await _recent_events(user)}


@router.get("/pipelines")
async def pipeline_events(user: dict = Depends(require_permission(Permission.VIEW_PIPELINES))):
    rows = (await _recent_events(user))["pipelines"]
    return {"pipelines": rows, "total": len(rows), "insufficient_data": not rows}


@router.get("/deployments")
async def deployment_events(user: dict = Depends(require_permission(Permission.VIEW_DEPLOYMENTS))):
    rows = (await _recent_events(user))["deployments"]
    return {"deployments": rows, "total": len(rows), "insufficient_data": not rows}
