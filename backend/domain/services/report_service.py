"""
CR-011: report downloads for the CEO, PM and HR (existing roles only).

Each report needs EXPORT_DATA *and* the right to view that data (D1-A), is
limited to the projects or organisation the caller can access, needs a
purpose (D3-A), and is written to the audit log with a content digest. The
performance report is aggregated only and hides groups under five people
(D2-A).
"""

import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.audit import AuditAction, log_audit
from core.authorization import get_accessible_project_ids, has_global_access
from core.database import col
from core.permissions import Permission, get_user_permissions
from domain.models.performance_evidence import canonical_digest

MAX_ROWS = 5000
MAX_RANGE_DAYS = 366
MIN_GROUP = 5
SMALL_GROUP = "fewer than 5"
LIMITATIONS = ("Legacy methodology, evidence coverage and period normalization are not verified; "
               "numeric changes are not a verified employee trend")

REPORTS: Dict[str, Dict[str, Any]] = {
    "sprint_velocity": {
        "title": "Sprint Velocity & Completion",
        "view": [Permission.VIEW_PROJECT_DATA, Permission.VIEW_ALL_DATA],
        "columns": ["project_id", "sprint_id", "sprint_name", "status", "start_date", "end_date",
                    "points_committed", "points_completed", "completion_pct", "stories_open"],
    },
    "quality_trends": {
        "title": "Engineering Quality & Static Analysis",
        "view": [Permission.VIEW_CODE_QUALITY, Permission.VIEW_PROJECT_DATA, Permission.VIEW_ALL_DATA],
        "columns": ["project_id", "run_id", "created_at", "language", "quality_score", "quality_grade",
                    "risk_score", "risk_level", "status"],
    },
    "delivery_risk": {
        "title": "Delivery & Risk Governance",
        "view": [Permission.VIEW_PROJECT_DATA, Permission.VIEW_ALL_DATA],
        "columns": ["project_id", "project_name", "status", "open_risks", "critical_risks", "high_risks"],
    },
    "performance_distribution": {
        "title": "Workforce Performance Distribution",
        "view": [Permission.VIEW_ORGANIZATION_PERFORMANCE, Permission.VIEW_PERFORMANCE_OUTCOMES],
        "columns": ["period", "team_id", "grade", "people"],
    },
}


def _permissions(user: dict):
    return get_user_permissions(user.get("role", user.get("organizational_role", "")),
                                user.get("is_admin", False), user.get("designation"))


def available_reports(user: dict) -> List[Dict[str, str]]:
    permissions = _permissions(user)
    if Permission.EXPORT_DATA not in permissions:
        return []
    return [{"type": key, "title": spec["title"]} for key, spec in REPORTS.items()
            if any(p in permissions for p in spec["view"])]


def _authorize(user: dict, report_type: str) -> Dict[str, Any]:
    spec = REPORTS.get(report_type)
    if not spec:
        raise HTTPException(status_code=404, detail="Unknown report")
    permissions = _permissions(user)
    if Permission.EXPORT_DATA not in permissions:
        raise HTTPException(status_code=403, detail="Downloading reports needs the export permission")
    if not any(p in permissions for p in spec["view"]):
        raise HTTPException(status_code=403, detail="You can't view the data in this report")
    return spec


def _range(start: Optional[date], end: Optional[date]):
    end = end or datetime.now(timezone.utc).date()
    start = start or end - timedelta(days=90)
    if start > end:
        raise HTTPException(status_code=422, detail="The start date must be before the end date")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Choose a period of 12 months or less")
    return start.isoformat(), (end + timedelta(days=1)).isoformat()  # end is inclusive


async def _projects(user: dict, project_id: Optional[str]) -> List[dict]:
    """Projects the caller may report on, in their organisation."""
    allowed = set(await get_accessible_project_ids(user))
    query: Dict[str, Any] = {"id": {"$in": sorted(allowed)}}
    if user.get("org_id"):
        query["org_id"] = user["org_id"]
    if project_id:
        if project_id not in allowed:
            raise HTTPException(status_code=403, detail="You don't have access to this project")
        query["id"] = project_id
    return await col("projects").find(query, {"_id": 0}).to_list(length=1000)


async def _sprint_velocity(projects, start, end):
    ids = [p["id"] for p in projects]
    sprints = await col("sprints").find(
        {"project_id": {"$in": ids}, "start_date": {"$lt": end}, "end_date": {"$gte": start}}, {"_id": 0},
    ).sort("start_date", 1).to_list(length=MAX_ROWS + 1)
    rows = []
    for sprint in sprints:
        stories = await col("stories").find(
            {"sprint_id": sprint.get("id"), "status": {"$ne": "draft"}}, {"_id": 0, "points": 1, "status": 1},
        ).to_list(length=None)
        committed = sum(int(s.get("points") or 0) for s in stories)
        completed = sum(int(s.get("points") or 0) for s in stories if s.get("status") == "done")
        rows.append({
            "project_id": sprint.get("project_id"), "sprint_id": sprint.get("id"), "sprint_name": sprint.get("name"),
            "status": sprint.get("status"), "start_date": sprint.get("start_date"), "end_date": sprint.get("end_date"),
            "points_committed": committed, "points_completed": completed,
            "completion_pct": round(100 * completed / committed, 1) if committed else None,
            "stories_open": sum(1 for s in stories if s.get("status") != "done"),
        })
    return rows


async def _quality_trends(projects, start, end):
    ids = [p["id"] for p in projects]
    runs = await col("code_quality_runs").find(
        {"repository_id": {"$in": ids}, "created_at": {"$gte": start, "$lt": end}},
        {"_id": 0, "repository_id": 1, "run_id": 1, "created_at": 1, "language": 1, "quality_score": 1,
         "quality_grade": 1, "risk_score": 1, "risk_level": 1, "status": 1},
    ).sort("created_at", 1).to_list(length=MAX_ROWS + 1)
    return [{"project_id": r.get("repository_id"), **{k: r.get(k) for k in REPORTS["quality_trends"]["columns"][1:]}}
            for r in runs]


async def _delivery_risk(projects, start, end):
    rows = []
    for project in projects:
        risks = await col("risks").find({"project_id": project["id"], "status": "open"},
                                        {"_id": 0, "risk_level": 1}).to_list(length=None)
        levels = Counter((r.get("risk_level") or "").upper() for r in risks)
        rows.append({"project_id": project["id"], "project_name": project.get("name"), "status": project.get("status"),
                     "open_risks": len(risks), "critical_risks": levels["CRITICAL"], "high_risks": levels["HIGH"]})
    return rows


async def _performance_distribution(user, start, end):
    org_id = user.get("org_id")
    if not org_id and not has_global_access(user):
        raise HTTPException(status_code=403, detail="Your account has no organisation, so no performance data is in scope")
    project_query = {"org_id": org_id} if org_id else {}
    project_ids = [p["id"] for p in await col("projects").find(project_query, {"_id": 0, "id": 1}).to_list(length=None)]
    records = await col("developer_performances").find(
        {"project_id": {"$in": project_ids}, "period_start": {"$gte": start, "$lt": end}},
        {"_id": 0, "developer_id": 1, "grade": 1, "period_label": 1, "period_start": 1, "org_id": 1},
    ).sort("period_start", -1).to_list(length=None)
    people = {}
    if records:
        user_query: Dict[str, Any] = {"employee_id": {"$in": list({r["developer_id"] for r in records})}}
        if org_id:
            user_query["org_id"] = org_id
        people = {u["employee_id"]: u.get("team_id") or "unassigned"
                  for u in await col("users").find(user_query, {"_id": 0, "employee_id": 1, "team_id": 1}).to_list(None)}
    latest = {}
    for record in records:  # newest first: keep one result per person per period
        key = (record.get("period_label") or "", record["developer_id"])
        if record["developer_id"] in people and key not in latest:
            latest[key] = record
    counts = defaultdict(int)
    for (period, developer_id), record in latest.items():
        counts[(period, people[developer_id], record.get("grade") or "ungraded")] += 1
    return [{"period": period, "team_id": team, "grade": grade, "people": n if n >= MIN_GROUP else SMALL_GROUP}
            for (period, team, grade), n in sorted(counts.items())]


def _safe_cell(value):
    """Stop spreadsheets running cells as formulas (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def to_csv(columns: List[str], rows: List[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_safe_cell(row.get(c)) for c in columns])
    return buffer.getvalue()


async def generate(user: dict, report_type: str, *, purpose: str, project_id: Optional[str] = None,
                   start: Optional[date] = None, end: Optional[date] = None) -> Dict[str, Any]:
    spec = _authorize(user, report_type)
    if not purpose or not purpose.strip():
        raise HTTPException(status_code=422, detail="Give a short purpose for this export")
    period_start, period_end = _range(start, end)
    if report_type == "performance_distribution":
        rows = await _performance_distribution(user, period_start, period_end)
    else:
        projects = await _projects(user, project_id)
        builder = {"sprint_velocity": _sprint_velocity, "quality_trends": _quality_trends,
                   "delivery_risk": _delivery_risk}[report_type]
        rows = await builder(projects, period_start, period_end)
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=422, detail=f"More than {MAX_ROWS} rows; choose a project or a shorter period")
    digest = canonical_digest(rows)
    await log_audit(action=AuditAction.EXPORT_DATA, actor=user, resource_type="report", resource_id=report_type,
                    details={"purpose": purpose.strip(), "project_id": project_id, "from": period_start,
                             "to": (end or datetime.now(timezone.utc).date()).isoformat(),
                             "row_count": len(rows), "digest": digest})
    result = {"report": report_type, "title": spec["title"], "columns": spec["columns"], "rows": rows,
              "row_count": len(rows), "digest": digest, "generated_at": datetime.now(timezone.utc).isoformat()}
    if report_type == "performance_distribution":
        result["limitations"] = [LIMITATIONS, f"Groups with fewer than {MIN_GROUP} people are not counted exactly."]
    return result
