"""Blocked tasks in the PM's active projects, grouped by elapsed time."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException

from core.authorization import managed_project_ids
from core.database import col
from core.organization import project_child_tenant_filter


AgeGroup = Literal["all", "under_day", "one_two_days", "three_six_days", "week_plus", "unknown"]
BUCKETS = ("under_day", "one_two_days", "three_six_days", "week_plus", "unknown")


async def ensure_blocked_work_indexes():
    await col("tasks").create_index(
        [("project_id", 1), ("id", 1)], name="blocked_tasks_by_project",
        partialFilterExpression={"status": "blocked"},
    )
    await col("activities").create_index(
        [("item_id", 1), ("project_id", 1), ("created_at", -1), ("_id", -1)],
        name="task_status_changes_by_item",
        partialFilterExpression={"event_type": "status_changed", "item_type": "task"},
    )


def managed_project_query(user: dict) -> dict:
    """Match assigned projects with an explicit, consistent tenant."""
    org = user.get("org_id")
    if not isinstance(org, str) or not org.strip() or user.get("organization_id", org) != org:
        return {"id": {"$in": []}}
    exact_org = {"$eq": org, "$not": {"$type": "array"}}
    return {
        "id": {"$in": sorted(p for p in managed_project_ids(user) if isinstance(p, str) and p),
               "$not": {"$type": "array"}},
        "org_id": exact_org,
        "$or": [{"organization_id": {"$exists": False}}, {"organization_id": exact_org}],
    }


def _age(start, now):
    try:
        start = datetime.fromisoformat(start)
    except (TypeError, ValueError):
        return "unknown", None
    if start.tzinfo is None or start > now:
        return "unknown", None
    days = (now - start).days
    if days < 1:
        return "under_day", days
    if days < 3:
        return "one_two_days", days
    if days < 7:
        return "three_six_days", days
    return "week_plus", days


async def blocked_work(user: dict, group: AgeGroup, offset: int, limit: int):
    organization = user.get("org_id")
    if not isinstance(organization, str) or not organization.strip() or user.get("organization_id", organization) != organization:
        raise HTTPException(403, "Your organization is required to view blocked work")
    tenant = project_child_tenant_filter(user)
    projects = await col("projects").find(
        {**managed_project_query(user), "status": "active"}, {"id": 1, "name": 1}
    ).to_list(None)
    names = {project["id"]: project.get("name") or project["id"] for project in projects}
    tasks = col("tasks").find({**tenant, "status": "blocked",
        "project_id": {"$in": list(names), "$not": {"$type": "array"}}},
        {"id": 1, "title": 1, "project_id": 1, "assignee_id": 1, "blocked_since": 1}).sort([("project_id", 1), ("id", 1)])
    now = datetime.now(timezone.utc)
    counts = dict.fromkeys(BUCKETS, 0)
    rows = []
    matched = 0
    while batch := await tasks.to_list(200):
        # Older tasks predate blocked_since. Only use the latest status change
        # for the exact project and task, including moves out of Blocked.
        legacy_ids = [row["id"] for row in batch if "blocked_since" not in row]
        history = {}
        if legacy_ids:
            for event in await col("activities").aggregate([
                {"$match": {**tenant, "project_id": {"$in": list(names), "$not": {"$type": "array"}}, "item_type": "task",
                            "item_id": {"$in": legacy_ids, "$not": {"$type": "array"}}, "event_type": "status_changed"}},
                {"$sort": {"created_at": -1, "_id": -1}},
                {"$group": {"_id": {"project": "$project_id", "task": "$item_id"},
                            "status": {"$first": "$details.to_status"}, "at": {"$first": "$created_at"}}},
            ]).to_list(None):
                if event["status"] == "blocked":
                    history[(event["_id"]["project"], event["_id"]["task"])] = event["at"]
        for row in batch:
            project_id = row["project_id"]
            start = row.get("blocked_since", history.get((project_id, row["id"])))
            bucket, days = _age(start, now)
            counts[bucket] += 1
            if group == "all" or bucket == group:
                if offset <= matched < offset + limit:
                    rows.append({"task_id": row["id"], "title": row.get("title") or row["id"],
                                 "project_id": project_id, "project_name": names[project_id],
                                 "assignee_id": row.get("assignee_id"), "age_days": days,
                                 "blocked_since": start if days is not None else None})
                matched += 1
    return {"as_of": now.isoformat(), "counts": counts, "tasks": rows, "matched": matched}
