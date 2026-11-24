"""DevOps metrics reconcile with scoped, deduplicated provider records."""
import pytest

from api.roles import devops
from core import authorization, database
from repositories.project_repository import ProjectRepository

pytestmark = pytest.mark.anyio
OPS = {"name": "Ops", "role": "DEVOPS", "org_id": "O", "project_ids": ["P", "F"]}
WINDOW = {"start": "2026-11-10", "today": "2026-11-23", "end": "2026-11-24", "as_of": "2026-11-23T15:00:00Z"}
DATE = "2026-11-23T12:00:00Z"


def workflow(run, attempt, state, conclusion, at=DATE, project="P", repo="acme/shop"):
    return {"source": "github", "event_type": "workflow_run", "project_id": project,
            "payload": {"repository": {"full_name": repo},
                        "workflow_run": {"id": run, "run_attempt": attempt, "status": state, "conclusion": conclusion,
                                         "updated_at": at, "name": "Search tests", "head_branch": "main"}}}


def deployment(identity, born=DATE, state=None, updated=DATE, status_id=1):
    payload = {"repository": {"full_name": "acme/shop"},
               "deployment": {"id": identity, "created_at": born, "environment": "production", "sha": "f" * 40}}
    if state:
        payload["deployment_status"] = {"id": status_id, "state": state, "created_at": updated}
    return {"project_id": "P", "source": "github", "event_type": "deployment_status" if state else "deployment", "payload": payload}


@pytest.fixture
async def db(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    monkeypatch.setattr(devops, "_window", lambda: WINDOW)
    await mock_db.projects.insert_many([{"id": "P", "org_id": "O"}, {"id": "F", "org_id": "foreign"},
                                        {"id": "P2", "org_id": "O"}])
    await mock_db.github_project_configs.insert_many([
        {"project_id": "P", "repository_owner": "Acme", "repository_name": "shop"},
        {"project_id": "F", "repository_owner": "Acme", "repository_name": "other"},
        {"project_id": "P2", "repository_owner": "Acme", "repository_name": "private"},
    ])
    return mock_db


async def test_source_drilldowns_reconcile_attempts_and_deployments(db):
    older = "2026-11-09T10:00:00Z"
    yesterday = "2026-11-22T10:00:00Z"
    await db.webhook_events.insert_many([
        workflow(1, 1, "completed", "failure", yesterday),
        workflow(1, 2, "completed", "success"),
        workflow(1, 2, "in_progress", None),  # delivered out of order with equal timestamp
        workflow(1, 2, "completed", "success"),  # duplicate event for same attempt
        workflow(2, 1, "completed", "cancelled"), workflow(3, 1, "queued", None),
        workflow(4, 1, "completed", "success", older),
        {**workflow(5, 1, "completed", "success"), "event_type": "check_run"},
        deployment(9), deployment(9, state="success", status_id=3), deployment(9, state="in_progress", status_id=2),
        deployment(8, born=yesterday, state="failure"), deployment(7, born=older, state="failure"),
    ])
    await db.incidents.insert_many([
        {"id": "I1", "project_id": "P", "status": "open"}, {"id": "I2", "project_id": "P", "status": "investigating"},
        {"id": "I3", "project_id": "P", "status": "resolved"}, {"id": "I4", "project_id": "F", "status": "open"},
    ])
    dash = await devops.devops_dashboard(OPS)
    assert dash["summary"] == {"workflow_attempts": 4, "decided_attempts": 2, "build_success_rate": 50,
                                "deployments_today": 1, "active_incidents": 2}
    assert dash["daily"][-1] == {"date": WINDOW["today"], "success": 1, "failed": 0, "cancelled": 1, "other": 1}
    assert len(dash["daily"]) == 14
    assert (await devops.pipelines(OPS, day=WINDOW["today"]))["total"] == 3
    assert (await devops.pipelines(OPS, outcome="decided"))["total"] == 2
    assert (await devops.deployments(OPS, today=True))["deployments"][0]["status"] == "success"
    assert (await devops.deployments(OPS))["total"] == 2
    historical = await devops.deployments(OPS, repository="ACME/SHOP", deployment_id=7)
    assert historical["total"] == 1 and historical["deployments"][0]["status"] == "failure"


async def test_all_pages_are_scoped_and_incomplete_or_ambiguous_records_are_withheld(db):
    await db.webhook_events.insert_many([
        workflow(1, 1, "completed", "success"),
        workflow(2, 1, "completed", "failure", project="F", repo="acme/other"),
        workflow(3, 1, "completed", "failure", project="F"),
        workflow(4, 1, "completed", "failure", project="P", repo="acme/other"),
        workflow(5, 1, "completed", "failure", project=None),
        {**workflow(6, 1, "completed", "failure"), "org_id": "foreign"},
        workflow(7, 1, "completed", "success", project="P2", repo="acme/private"),
        workflow(8, None, "completed", "success"),
        workflow(9, 1, "completed", "success", at="2026-11-12"),
        workflow(10, 1, "completed", "success", repo=["acme/shop", "acme/other"]),
        workflow(11, 1, "completed", "failure", at="2026-11-1x"),
    ])
    assert [row["id"] for row in (await devops.pipelines(OPS))["pipelines"]] == [1]
    assert (await devops.pipelines({**OPS, "role": "CEO", "org_id": None}))["total"] == 0
    assert (await devops.pipelines({**OPS, "organization_id": "foreign"}))["total"] == 0
    ceo = await devops.pipelines({**OPS, "role": "CEO"})
    assert {row["id"] for row in ceo["pipelines"]} == {1, 7}
    await db.github_project_configs.insert_one({"project_id": "F", "repository_owner": "ACME", "repository_name": "SHOP"})
    assert (await devops.pipelines(OPS))["total"] == 0


async def test_over_a_hundred_events_are_counted_and_detail_is_paginated(db):
    await db.webhook_events.insert_many([workflow(n, 1, "completed", "success") for n in range(1, 126)])
    assert (await devops.devops_dashboard(OPS))["summary"]["workflow_attempts"] == 125
    data = await devops.pipelines(OPS, page=3)
    assert len(data["pipelines"]) == 25 and data["total"] == 125


async def test_event_history_and_reporting_routes_preserve_their_contracts(db):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from core.dependencies import get_current_user

    app = FastAPI()
    app.include_router(devops.router, prefix="/role/devops")
    app.dependency_overrides[get_current_user] = lambda: OPS
    event = workflow(41, 2, "completed", "success")
    await db.webhook_events.insert_many([event.copy(), event.copy(), deployment(77),
                                          workflow(42, 1, "completed", "failure", project="F")])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
        async def get(path):
            response = await client.get("/role/devops/" + path)
            assert response.status_code == 200, response.text
            return response.json()

        raw = await get("pipelines")
        assert raw["total"] == 2 and all(row["payload"] == event["payload"] for row in raw["pipelines"])
        assert (await get("deployments"))["deployments"][0]["payload"]["deployment"]["id"] == 77
        assert (await get("dashboard"))["pipelines"] == raw["pipelines"]
        attempts = await get("reporting/pipelines?outcome=success")
        assert attempts["total"] == 1 and attempts["pipelines"][0]["id"] == 41
        assert (await get("reporting/deployments"))["deployments"][0]["id"] == 77
        assert (await get("reporting/dashboard"))["summary"]["workflow_attempts"] == 1


async def test_unresolved_incident_card_reconciles_with_all_pages_and_project_scope(db):
    from api.routes.incidents import list_incidents

    def incident(identity, status, **fields):
        return {"id": identity, "title": identity, "description": "Reported", "project_id": "P",
                "severity": "high", "status": status, "reporter_id": "ops", **fields}

    await db.incidents.insert_many([incident("A", "open"), incident("B", "investigating"),
                                    incident("C", "resolved"), incident("D", "open", org_id="foreign"),
                                    incident("E", "open", project_id="F")])
    summary = (await devops.devops_dashboard(OPS))["summary"]
    first = await list_incidents(status="unresolved", user=OPS, limit=1)
    second = await list_incidents(project_id="P", status="unresolved", user=OPS, limit=1, offset=1)
    assert [r.id for r in first + second] == ["A", "B"]
    assert summary["active_incidents"] == len(first + second)


async def test_failed_deployment_notification_reaches_only_assigned_active_devops(db):
    from unittest.mock import AsyncMock
    from domain.models.webhook_event import WebhookEvent
    from domain.services.webhook_event_processor import WebhookEventProcessor

    base = {"role": "DEVOPS", "is_active": True, "org_id": "O", "project_ids": ["P"], "team_id": "T"}
    await db.users.insert_many([{**base, "employee_id": "assigned"}, {**base, "employee_id": "foreign", "org_id": "F"},
                                {**base, "employee_id": "inactive", "is_active": False},
                                {**base, "employee_id": "unassigned", "project_ids": []}])
    processor = WebhookEventProcessor()
    processor.notification_service.notify = AsyncMock(return_value={"id": "N"})
    event = WebhookEvent(id="E", repository="acme/shop", **deployment(9, state="failure"))
    result = await processor._handle_deployment_status_event(event)
    assert result["notifications_sent"] == ["N"]
    processor.notification_service.notify.assert_awaited_once()
    sent = processor.notification_service.notify.await_args.kwargs
    assert sent["user_id"] == "assigned" and sent["link"] == "/deployments?repository=acme%2Fshop&deployment_id=9"
