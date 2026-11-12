"""
CR-005: PM access (access and rules only, no new backend structure).

Decisions implemented: D1-A (PMs keep organisation-wide delivery visibility
until project membership exists), D2-A (no browsing individual performance
records), D3-A (QA alone verifies/closes defects), D4-A (Leads see their team
members' task lists).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import Permission, get_user_permissions
from test_lead_access import LEAD, people  # noqa: F401  (fixture reuse)
from test_performance_access import records, service as performance_service  # noqa: F401  (fixture reuse)


def make_user(employee_id="PM-1", role="PM", project_ids=None, team_id=None, **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": f"User {employee_id}", "role": role,
            "organizational_role": role, "project_ids": project_ids or [], "team_id": team_id, **extra}


# ── D2: PMs don't browse individual performance records ─────────────────────

@pytest.mark.anyio
class TestPmPerformance:
    async def _add_pm(self, records):  # noqa: F811
        await records.users.insert_one({"employee_id": "P1", "role": "PM", "org_id": "O1",
                                        "is_active": True, "project_ids": ["AUDIT-PROJECT"]})

    @pytest.mark.parametrize("read", ["detail", "trend"])
    async def test_pm_cannot_open_a_project_members_record(self, records, read):  # noqa: F811
        await self._add_pm(records)
        with pytest.raises(HTTPException) as error:
            await getattr(performance_service(), read)("AUDIT-DEV", {"employee_id": "P1"})
        assert error.value.status_code == 403

    async def test_pm_cannot_read_team_summaries_or_shadow(self, records):  # noqa: F811
        await self._add_pm(records)
        with pytest.raises(HTTPException):
            await performance_service().team("AUDIT-PROJECT", "current", {"employee_id": "P1"})
        with pytest.raises(HTTPException):
            await performance_service().shadow("AUDIT-DEV", {"employee_id": "P1"})

    async def test_lead_still_reads_team_records(self, records):  # noqa: F811
        result = await performance_service().detail("AUDIT-DEV", {"employee_id": "L"})
        assert result is not None

    def test_pm_keeps_review_and_delivery_permissions(self):
        permissions = get_user_permissions("PM")
        assert {Permission.SUBMIT_PM_FEEDBACK, Permission.VIEW_PROJECT_PERFORMANCE} <= permissions
        assert Permission.TRIGGER_AI_EVALUATION not in permissions


# ── D3: QA alone verifies and closes defects ────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["CLOSED", "REOPENED"])
async def test_pm_cannot_verify_or_close_defects(target):
    from domain.models.qa import DefectUpdate
    from domain.services.qa_service import QAService
    service = QAService()
    service.accessible_project = AsyncMock(return_value={"id": "PRJ-A"})
    service.repo = AsyncMock()
    service.repo.find_one = AsyncMock(return_value={
        "id": "QAB-1", "project_id": "PRJ-A", "status": "READY_FOR_RETEST",
        "assignee_id": "DEV-A", "reporter_id": "QA-1", "history": []})
    with pytest.raises(HTTPException) as error:
        await service.update_defect(make_user(), "QAB-1", DefectUpdate(status=target))
    assert error.value.status_code == 403


# ── D1-A: PMs keep organisation-wide delivery visibility ────────────────────

@pytest.mark.asyncio
async def test_pm_still_sees_every_project():
    from core.authorization import verify_project_access
    with patch("core.authorization._project_repo") as projects:
        projects.find_by_id = AsyncMock(return_value={"id": "PRJ-Z", "team_id": "TEAM-Z"})
        assert await verify_project_access(make_user(), "PRJ-Z", require_write=True) is None


# ── D4: Leads see their team members' tasks ─────────────────────────────────

@pytest.mark.anyio
class TestLeadTeamTasks:
    async def test_lead_opens_a_team_members_task_list(self, people):  # noqa: F811
        from core.authorization import verify_can_view_user_tasks
        assert await verify_can_view_user_tasks(LEAD, "DEV-A") is None
        assert await verify_can_view_user_tasks(LEAD, "DEV-P") is None  # on one of the Lead's projects

    async def test_lead_cannot_open_another_teams_tasks(self, people):  # noqa: F811
        from core.authorization import verify_can_view_user_tasks
        with pytest.raises(HTTPException) as error:
            await verify_can_view_user_tasks(LEAD, "DEV-B")
        assert error.value.status_code == 403

    async def test_developers_still_see_only_their_own(self, people):  # noqa: F811
        from core.authorization import verify_can_view_user_tasks
        with pytest.raises(HTTPException):
            await verify_can_view_user_tasks(make_user("DEV-A", "DEVELOPER", team_id="TEAM-A"), "DEV-B")
