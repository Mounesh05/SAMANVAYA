from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from api.roles import pm
from core import database
from domain.services.pm_blocked_work import blocked_work
from domain.services.workflow_service import WorkflowService


@pytest.mark.anyio
async def test_current_blocked_ages_and_drilldown_are_scoped(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    now = datetime.now(timezone.utc)
    actor = {"role": "PM", "project_ids": ["A", "B", "C"], "org_id": "own"}
    await mock_db.projects.insert_many([
        {"id": "A", "name": "Managed", "org_id": "own", "status": "active"},
        {"id": "B", "org_id": "foreign", "status": "active"},
        {"id": "C", "org_id": "own", "status": "paused"},
        {"id": "D", "org_id": "own", "status": "active"},
    ])
    for task in [
        {"id": "A1", "status": "in_progress"}, {"id": "A2"}, {"id": "A3"},
        {"id": "A4", "blocked_since": (now + timedelta(days=2)).isoformat()},
        {"id": "A5"}, {"id": "A6", "org_id": "foreign"},
        {"id": "B1", "project_id": "B"}, {"id": "C1", "project_id": "C"}, {"id": "D1", "project_id": "D"},
    ]:
        await mock_db.tasks.insert_one({"status": "blocked", "project_id": "A", "created_at": "2020-01-01", **task})
    for identifier, destination, days, project in [
        ("A2", "blocked", 12, "A"), ("A2", "in_progress", 8, "A"), ("A2", "blocked", 2, "A"),
        ("A3", "blocked", 14, "B"), ("A5", "blocked", 10, "A"), ("A5", "in_progress", 2, "A"),
    ]:
        await mock_db.activities.insert_one({"event_type": "status_changed", "item_type": "task",
            "item_id": identifier, "created_at": (now - timedelta(days=days)).isoformat(), "project_id": project,
            "details": {"to_status": destination}})
    # Same mutation path as the board and task detail.
    flow = WorkflowService()
    await flow.transition_task("A1", "blocked", "pm", "Pilot Manager")
    result = await blocked_work(actor, "all", 0, 1)
    assert result["counts"] == {"under_day": 1, "one_two_days": 1, "three_six_days": 0, "week_plus": 0, "unknown": 3}
    assert result["matched"] == 5 and result["tasks"][0]["task_id"] == "A1"
    assert result["tasks"][0]["age_days"] == 0
    assert (await blocked_work(actor, "one_two_days", 0, 12))["tasks"][0]["task_id"] == "A2"
    unknown = await blocked_work(actor, "unknown", 1, 1)
    assert unknown["matched"] == 3 and unknown["tasks"][0]["age_days"] is None
    await flow.transition_task("A1", "in_progress", "pm", "Pilot Manager")
    assert (await mock_db.tasks.find_one({"id": "A1"}))["blocked_since"] is None
    assert (await blocked_work(actor, "all", 0, 20))["matched"] == 4
    for user in ({**actor, "org_id": ""}, {**actor, "organization_id": "other"}):
        with pytest.raises(HTTPException) as denied:
            await blocked_work(user, "all", 0, 10)
        assert denied.value.status_code == 403
    for project_id in ("B", "D"):
        with pytest.raises(HTTPException) as denied:
            await pm.project_health(project_id, user=actor)
        assert denied.value.status_code in (403, 404)


@pytest.mark.anyio
async def test_pm_report_to_project_tasks_through_mounted_routes(mock_db, monkeypatch):
    from main import app
    from api.routes import tasks
    from core import authorization
    from core.dependencies import get_current_user
    from domain.services.task_service import TaskService
    from repositories.project_repository import ProjectRepository

    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    monkeypatch.setattr(tasks, "task_service", TaskService())
    actor = {"name": "Morgan", "role": "PM", "org_id": "own", "project_ids": ["P", "Q", "R", "S"]}
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: dict(actor))
    await mock_db.projects.insert_many([
        {"id": "P", "org_id": "own", "status": "active"},
        {"id": "Q", "org_id": "other", "status": "active"},
        {"id": "R", "org_id": "own", "status": "paused"},
        {"id": "S", "org_id": "own", "organization_id": "other", "status": "active"},
        {"id": "U", "org_id": "own", "status": "active"},
    ])
    for project in ("P", "Q", "R", "S", "U"):
        await mock_db.tasks.insert_one({"id": f"T-{project}", "title": "Search", "assignee_id": "Engineer",
                                        "project_id": project, "status": "blocked"})
    await mock_db.tasks.insert_many([
        {"id": "accepted", "project_id": "P", "title": "Review", "assignee_id": "Engineer", "org_id": "own"},
        {"id": "conflict", "project_id": "P", "title": "Other", "assignee_id": "Engineer", "organization_id": "other"},
        {"id": "invalid", "project_id": "P", "title": "Other", "assignee_id": "Engineer", "org_id": ["own", "other"]},
    ])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        dashboard = await client.get("/api/role/pm/dashboard")
        assert dashboard.status_code == 200
        assert [item["id"] for item in dashboard.json()["projects"]] == ["P"]
        assert {item["id"] for item in dashboard.json()["portfolio"]} == {"P", "R"}
        listing = await client.get("/api/role/pm/projects")
        assert [item["id"] for item in listing.json()["projects"]] == ["P"]
        url = "/api/role/pm/blocked-work"
        report = await client.get(url, params={"group": "unknown", "limit": 1})
        assert report.status_code == 200
        assert report.json()["counts"]["unknown"] == 1
        row, = report.json()["tasks"]
        assert row["age_days"] is None and row["blocked_since"] is None
        project_tasks = f"/api/tasks/project/{row['project_id']}"
        detail = await client.get(project_tasks)
        assert detail.status_code == 200
        assert {task["id"] for task in detail.json()} == {row["task_id"], "accepted"}
        assert (await client.get("/api/tasks/project/S")).status_code == 403
        assert (await client.get(url, params={"group": "yesterday"})).status_code == 422
        assert (await client.get(url, params={"limit": 101})).status_code == 422
        actor["project_ids"] = []
        assert (await client.get(url)).json()["matched"] == 0
        assert (await client.get(project_tasks)).status_code == 403
        actor["role"] = "QA"
        assert (await client.get(url)).status_code == 403
