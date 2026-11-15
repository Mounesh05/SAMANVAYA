"""Starting and completing sprints, and live delivery confidence.

Sprints used to stay in "planning" forever (no way to start them), and the
PM/CEO dashboards read a completion figure that was stored as 0% at creation
and never updated.
"""
import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import Permission, ROLE_PERMISSIONS
from domain.services.sprint_service import SprintService, SprintStatusConflict

PROJECT = {"id": "PRJ-1", "org_id": "ORG001", "team_id": "T1", "status": "active", "name": "Expense Tracker"}


class FakeSprints:
    def __init__(self, *sprints):
        self.docs = {s["id"]: dict(s) for s in sprints}

    async def find_by_id(self, sprint_id):
        doc = self.docs.get(sprint_id)
        return dict(doc) if doc else None

    async def find_active(self, project_id):
        return next((dict(s) for s in self.docs.values()
                     if s["project_id"] == project_id and s["status"] == "active"), None)

    async def find_by_project(self, project_id):
        return [dict(s) for s in self.docs.values() if s["project_id"] == project_id]

    async def update_one(self, query, update):
        doc = self.docs.get(query["id"])
        if not doc or doc["status"] != query["status"]:
            return False
        doc.update(update["$set"])
        return True


class FakeStories:
    async def find_by_sprint(self, _sprint_id):
        return []


class FakeTasks:
    def __init__(self, statuses):
        self.statuses = statuses

    async def find_by_sprint(self, _sprint_id):
        return [{"id": f"T{i}", "status": s, "story_id": None} for i, s in enumerate(self.statuses)]


def sprint(sprint_id="SPR-1", status="planning", project_id="PRJ-1"):
    return {"id": sprint_id, "name": sprint_id, "project_id": project_id, "goal": None,
            "start_date": "2026-11-15", "end_date": "2026-11-16", "status": status,
            "velocity": None, "completion_pct": 0.0, "created_at": "2026-11-15T00:00:00+00:00"}


def service(sprints, statuses=("done", "todo", "todo", "done")):
    s = SprintService()
    s.sprint_repo, s.story_repo, s.task_repo = sprints, FakeStories(), FakeTasks(list(statuses))
    return s


@pytest.mark.anyio
async def test_a_sprint_starts_then_completes_with_final_figures():
    repo = FakeSprints(sprint())
    svc = service(repo)
    started = await svc.change_status("SPR-1", "active")
    assert started.status == "active" and repo.docs["SPR-1"]["started_at"]
    done = await svc.change_status("SPR-1", "completed")
    assert done.status == "completed"
    # 2 of 4 equal-weight tasks done.
    assert (repo.docs["SPR-1"]["completion_pct"], repo.docs["SPR-1"]["velocity"]) == (50.0, 2)


@pytest.mark.anyio
@pytest.mark.parametrize("current,target", [
    ("planning", "completed"), ("active", "active"), ("completed", "active"), ("completed", "completed"),
])
async def test_a_sprint_only_moves_one_step_forward(current, target):
    with pytest.raises(SprintStatusConflict):
        await service(FakeSprints(sprint(status=current))).change_status("SPR-1", target)


@pytest.mark.anyio
async def test_one_active_sprint_per_project():
    repo = FakeSprints(sprint("SPR-1", "active"), sprint("SPR-2"), sprint("SPR-3", project_id="PRJ-2"))
    svc = service(repo)
    with pytest.raises(SprintStatusConflict, match="already active"):
        await svc.change_status("SPR-2", "active")
    # Another project is unaffected.
    assert (await svc.change_status("SPR-3", "active")).status == "active"


@pytest.mark.anyio
async def test_a_change_made_meanwhile_is_not_overwritten():
    repo = FakeSprints(sprint())
    svc = service(repo)
    repo.find_by_id = AsyncMock(return_value=sprint(status="planning"))
    repo.docs["SPR-1"]["status"] = "active"  # someone else started it after our read
    with pytest.raises(SprintStatusConflict, match="changed meanwhile"):
        await svc.change_status("SPR-1", "active")


@pytest.mark.anyio
async def test_live_completion_follows_the_tasks():
    svc = service(FakeSprints(sprint(status="active")), statuses=("done", "done", "done", "todo"))
    assert await svc.live_completion_pct("SPR-1") == 75.0
    assert await svc.live_completion_pct("SPR-MISSING") is None


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["CEO", "HR", "PM", "LEAD", "DEVELOPER", "QA", "DEVOPS"])
async def test_start_and_complete_need_the_create_sprint_permission(role):
    """Same gate as creating a sprint: only PM and Lead hold CREATE_SPRINT."""
    from api.routes import sprints
    check = inspect.signature(sprints.change_sprint_status).parameters["user"].default.dependency
    user = {"employee_id": "E10", "role": role, "team_id": "T1", "org_id": "ORG001"}
    allowed = any(Permission.CREATE_SPRINT in perms for r, perms in ROLE_PERMISSIONS.items()
                  if str(getattr(r, "value", r)) == role)
    assert allowed == (role in {"PM", "LEAD"})
    if allowed:
        assert await check(user=user) is user
    else:
        with pytest.raises(HTTPException) as error:
            await check(user=user)
        assert error.value.status_code == 403


@pytest.mark.anyio
async def test_a_lead_cannot_start_another_teams_sprint():
    from api.routes import sprints
    from domain.models.sprint import SprintStatusUpdate
    lead = {"employee_id": "E4", "role": "LEAD", "team_id": "T9", "org_id": "ORG001"}
    with patch.object(sprints, "sprint_repo") as repo, patch("core.authorization._project_repo") as projects:
        repo.find_by_id = AsyncMock(return_value=sprint())
        projects.find_by_id = AsyncMock(return_value=PROJECT)
        with pytest.raises(HTTPException) as error:
            await sprints.change_sprint_status("SPR-1", SprintStatusUpdate(status="active"), user=lead)
    assert error.value.status_code == 403


@pytest.mark.anyio
async def test_the_route_reports_conflicts_as_409():
    from api.routes import sprints
    from domain.models.sprint import SprintStatusUpdate
    lead = {"employee_id": "E4", "role": "LEAD", "team_id": "T1", "org_id": "ORG001"}
    with patch.object(sprints, "sprint_repo") as repo, patch("core.authorization._project_repo") as projects, \
            patch.object(sprints.sprint_service, "change_status",
                         AsyncMock(side_effect=SprintStatusConflict("A planning sprint cannot be moved to completed."))):
        repo.find_by_id = AsyncMock(return_value=sprint())
        projects.find_by_id = AsyncMock(return_value=PROJECT)
        with pytest.raises(HTTPException) as error:
            await sprints.change_sprint_status("SPR-1", SprintStatusUpdate(status="completed"), user=lead)
    assert error.value.status_code == 409


def test_only_active_and_completed_can_be_requested():
    from pydantic import ValidationError
    from domain.models.sprint import SprintStatusUpdate
    with pytest.raises(ValidationError):
        SprintStatusUpdate(status="planning")


@pytest.mark.anyio
async def test_pm_delivery_confidence_is_live_not_the_stored_zero():
    from api.roles import pm
    with patch.object(pm, "ProjectRepository") as projects, patch.object(pm, "SprintRepository") as sprints_repo, \
            patch.object(pm, "RiskRepository") as risks, \
            patch.object(pm.SprintService, "live_completion_pct", AsyncMock(return_value=60.0)):
        projects.return_value.find_all = AsyncMock(return_value=[PROJECT])
        sprints_repo.return_value.find_by_project = AsyncMock(return_value=[sprint(status="active"), sprint("SPR-2")])
        risks.return_value.find_open = AsyncMock(return_value=[])
        result = await pm.pm_dashboard(user={"employee_id": "E3", "name": "Shreyas K T", "role": "PM"})
    assert result["summary"]["delivery_confidence"] == "60%"
    assert result["summary"]["active_sprints"] == 1
