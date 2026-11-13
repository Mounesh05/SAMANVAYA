"""
CR-014: incident triage (existing roles only).

DevOps, Lead and PM triage incidents in projects they can access (D1-A); the
owner is an active engineering member of the project (D2-A); high and critical
incidents need a post-incident review before closing (D3-A). Every change is
time-stamped, kept on the timeline and audited.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import OrganizationalRole, Permission, ROLE_PERMISSIONS
from domain.models.incident import IncidentUpdate


def person(employee_id, role, **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": employee_id, "role": role,
            "organizational_role": role, "project_ids": ["P1"], "team_id": None, "is_admin": False,
            "is_active": True, **extra}


OPS, LEAD, PM = person("OPS-1", "DEVOPS"), person("LEAD-1", "LEAD", team_id="T1"), person("PM-1", "PM")
CEO, DEV = person("CEO-1", "CEO"), person("DEV-1", "DEVELOPER")
PROJECT = {"id": "P1", "team_id": "T1"}


@pytest.fixture
async def desk(mock_db, monkeypatch):
    from api.routes import incidents
    from repositories import incident_repository
    monkeypatch.setattr(incidents, "col", lambda name: mock_db[name])
    monkeypatch.setattr(incident_repository, "col", lambda name: mock_db[name])
    monkeypatch.setattr("core.database.col", lambda name: mock_db[name])
    audit = AsyncMock()
    monkeypatch.setattr(incidents, "log_audit", audit)
    await mock_db.users.insert_many([
        person("DEV-1", "DEVELOPER"), person("QA-1", "QA"), person("OPS-1", "DEVOPS"),
        person("HR-1", "HR"), person("OLD-1", "DEVELOPER", is_active=False), person("FAR-1", "DEVELOPER", project_ids=["P9"]),
    ])
    await mock_db.incidents.insert_many([
        {"id": "INC-1", "project_id": "P1", "title": "Checkout down", "description": "500s", "severity": "high",
         "status": "open", "reporter_id": "DEV-1", "reporter_name": "Dana", "created_at": "2026-11-13T08:00:00+00:00",
         "timeline": []},
        {"id": "INC-2", "project_id": "P1", "title": "Slow page", "description": "slow", "severity": "low",
         "status": "open", "reporter_id": "QA-1", "created_at": "2026-11-13T09:00:00+00:00"},
    ])
    with patch("core.authorization._project_repo") as projects:
        projects.find_by_id = AsyncMock(return_value=PROJECT)
        projects.find_all = AsyncMock(return_value=[PROJECT])
        yield mock_db, audit


async def triage(incident_id, user, **fields):
    from api.routes.incidents import triage_incident
    return await triage_incident(incident_id, IncidentUpdate(**fields), user)


async def refused(call, status):
    with pytest.raises(HTTPException) as error:
        await call
    assert error.value.status_code == status
    return error.value


class TestWhoTriages:
    def test_triage_permission_holders(self):
        holders = {r.value for r, granted in ROLE_PERMISSIONS.items() if Permission.TRIAGE_INCIDENT in granted}
        assert holders == {"DEVOPS", "LEAD", "PM"}
        assert Permission.VIEW_INCIDENTS in ROLE_PERMISSIONS[OrganizationalRole.PM]

    @pytest.mark.anyio
    @pytest.mark.parametrize("role", ["CEO", "DEVELOPER", "QA", "HR"])
    async def test_others_cannot_triage(self, role):
        from api.routes.incidents import triage_incident
        import inspect
        check = inspect.signature(triage_incident).parameters["user"].default.dependency
        await refused(check(user=person("X", role)), 403)

    @pytest.mark.anyio
    async def test_projects_outside_your_access_are_refused(self, desk):
        await refused(triage("INC-1", person("PM-9", "PM", project_ids=[]), status="investigating"), 403)


class TestLifecycle:
    @pytest.mark.anyio
    async def test_full_lifecycle_with_timestamps_timeline_and_audit(self, desk):
        db, audit = desk
        ack = await triage("INC-1", OPS, status="investigating", assignee_id="DEV-1", note="On it")
        assert ack.status == "investigating" and ack.acknowledged_at and ack.assignee_name == "DEV-1"
        resolved = await triage("INC-1", LEAD, status="resolved", resolution_summary="Rolled back release 42")
        assert resolved.resolved_at and resolved.resolution_summary == "Rolled back release 42"
        closed = await triage("INC-1", PM, status="closed", postmortem="Cause: bad config. Follow-up: add check.")
        assert closed.status == "closed" and closed.closed_at
        assert [e.action for e in closed.timeline] == ["acknowledged", "resolved", "closed"]
        assert closed.timeline[0].changes["status"] == ["open", "investigating"] and closed.timeline[0].note == "On it"
        assert [c.kwargs["action"].value for c in audit.await_args_list] == ["INCIDENT_UPDATED"] * 3
        await refused(triage("INC-1", OPS, note="late"), 409)

    @pytest.mark.anyio
    @pytest.mark.parametrize("start, target", [("open", "resolved"), ("open", "closed"), ("investigating", "closed")])
    async def test_skipping_steps_is_refused(self, desk, start, target):
        db, _ = desk
        await db.incidents.update_one({"id": "INC-2"}, {"$set": {"status": start}})
        await refused(triage("INC-2", OPS, status=target, resolution_summary="x", postmortem="y"), 409)

    @pytest.mark.anyio
    async def test_resolving_needs_a_summary(self, desk):
        await triage("INC-2", OPS, status="investigating")
        await refused(triage("INC-2", OPS, status="resolved"), 422)

    @pytest.mark.anyio
    async def test_reopen_clears_the_resolution_time(self, desk):
        await triage("INC-2", OPS, status="investigating")
        await triage("INC-2", OPS, status="resolved", resolution_summary="cache cleared")
        reopened = await triage("INC-2", OPS, status="investigating", note="Back again")
        assert reopened.status == "investigating" and reopened.resolved_at is None
        assert reopened.timeline[-1].action == "reopened"

    @pytest.mark.anyio
    async def test_serious_incidents_need_a_review_low_ones_do_not(self, desk):
        await triage("INC-1", OPS, status="investigating")
        await triage("INC-1", OPS, status="resolved", resolution_summary="fixed")
        error = await refused(triage("INC-1", OPS, status="closed"), 422)
        assert "post-incident review" in error.detail
        await triage("INC-2", OPS, status="investigating")
        await triage("INC-2", OPS, status="resolved", resolution_summary="fixed")
        assert (await triage("INC-2", OPS, status="closed")).status == "closed"

    @pytest.mark.anyio
    async def test_severity_can_be_raised_and_a_note_added_alone(self, desk):
        updated = await triage("INC-2", LEAD, severity="critical")
        assert updated.severity == "critical" and updated.timeline[-1].changes["severity"] == ["low", "critical"]
        noted = await triage("INC-2", LEAD, note="Customer impact confirmed")
        assert noted.timeline[-1].action == "noted"
        await refused(triage("INC-2", LEAD), 400)


class TestOwner:
    @pytest.mark.anyio
    @pytest.mark.parametrize("owner", ["DEV-1", "QA-1", "OPS-1"])
    async def test_engineering_members_can_own(self, desk, owner):
        assert (await triage("INC-2", OPS, assignee_id=owner)).assignee_id == owner

    @pytest.mark.anyio
    @pytest.mark.parametrize("owner", ["HR-1", "OLD-1", "FAR-1", "NOBODY"])
    async def test_other_owners_are_refused(self, desk, owner):
        await refused(triage("INC-2", OPS, assignee_id=owner), 422)

    @pytest.mark.anyio
    async def test_unassigning(self, desk):
        await triage("INC-2", OPS, assignee_id="DEV-1")
        assert (await triage("INC-2", OPS, assignee_id=None)).assignee_id is None


class TestReading:
    @pytest.mark.anyio
    async def test_viewers_and_own_reporters_see_details(self, desk):
        from api.routes.incidents import get_incident
        assert (await get_incident("INC-1", user=CEO)).id == "INC-1"
        assert (await get_incident("INC-1", user=DEV)).reporter_id == "DEV-1"
        await refused(get_incident("INC-2", user=DEV), 403)
        await refused(get_incident("INC-404", user=OPS), 404)

    @pytest.mark.anyio
    async def test_status_filter(self, desk):
        from api.routes.incidents import list_incidents
        await triage("INC-2", OPS, status="investigating")
        rows = await list_incidents(project_id=None, status="investigating", user=OPS)
        assert [r.id for r in rows] == ["INC-2"]
