"""Tasks follow the pull requests that name them (TSK-XXXXXXXX).

Opened -> review, changes requested or draft -> in progress, merged -> done,
closed without merging -> in progress. Only the assignee's own pull requests
in the same project move a task, one workflow step at a time.
"""
from unittest.mock import AsyncMock, patch

import pytest

from domain.models.workflow import TASK_WORKFLOW
from domain.services import task_progress_service as tps
from domain.services.task_progress_service import (
    TaskProgressService, apply_task_progress, target_status, task_ids_in, workflow_path,
)

PROJECT = "PRJ-BFAAEA0A"


def pr(number=1, state="open", merged=False, draft=False, title="Expense model (TSK-533075F3, TSK-0519EE96)",
       branch="feature/expense-model", body="", login="Mallikarjuna902"):
    return {"number": number, "state": state, "merged": merged, "draft": draft, "title": title,
            "head": {"ref": branch}, "body": body, "user": {"login": login}}


class FakeTasks:
    def __init__(self, *tasks):
        self.docs = {t["id"]: dict(t) for t in tasks}

    async def find_one(self, query):
        doc = self.docs.get(query["id"])
        return dict(doc) if doc else None


class FakeUsers:
    def __init__(self, *users):
        self.users = users

    async def find_one(self, query):
        import re
        pattern = re.compile(query["github_username"]["$regex"], re.IGNORECASE)
        return next((u for u in self.users if u.get("github_username") and pattern.match(u["github_username"])
                     and u.get("is_active", True) is not False), None)


class FakeWorkflow:
    """Applies the real task workflow rules and records each step."""

    def __init__(self, tasks):
        self.tasks, self.steps = tasks, []

    async def transition_task(self, task_id, new_status, user_id, user_name, reason=None):
        task = self.tasks.docs[task_id]
        if new_status not in TASK_WORKFLOW.get(task["status"], []):
            raise ValueError(f"Cannot transition from '{task['status']}' to '{new_status}'")
        self.steps.append((task_id, task["status"], new_status, user_id, user_name, reason))
        task["status"] = new_status
        return task


def task(task_id="TSK-533075F3", status="todo", assignee="E5", project=PROJECT):
    return {"id": task_id, "status": status, "assignee_id": assignee, "project_id": project}


E5 = {"employee_id": "E5", "github_username": "Mallikarjuna902", "is_active": True}


def service(*tasks, users=(E5,)):
    s = TaskProgressService.__new__(TaskProgressService)
    s.task_repo = FakeTasks(*tasks)
    s.user_repo = FakeUsers(*users)
    s.workflow = FakeWorkflow(s.task_repo)
    return s


# ── Reading the pull request ────────────────────────────────────────────────

def test_task_ids_come_from_title_branch_and_description_once_each():
    found = task_ids_in(pr(title="Fix tsk-533075f3", branch="feature/TSK-0519EE96-model",
                           body="Also TSK-533075F3 and TSK-C472CB2F. Not TSK-123."))
    assert found == ["TSK-533075F3", "TSK-0519EE96", "TSK-C472CB2F"]
    assert task_ids_in(pr(title="No task here", branch="main")) == []


@pytest.mark.parametrize("kwargs,reviews,expected", [
    ({}, [], "review"),
    ({"draft": True}, [], "in_progress"),
    ({}, [{"state": "CHANGES_REQUESTED", "submitted_at": "2026-11-15T10:00:00Z"}], "in_progress"),
    ({}, [{"state": "CHANGES_REQUESTED", "submitted_at": "2026-11-15T10:00:00Z"},
          {"state": "APPROVED", "submitted_at": "2026-11-15T12:00:00Z"}], "review"),
    ({}, [{"state": "APPROVED", "submitted_at": "2026-11-15T10:00:00Z"},
          {"state": "COMMENTED", "submitted_at": "2026-11-15T12:00:00Z"}], "review"),
    ({"state": "closed", "merged": True}, [], "done"),
    ({"state": "closed"}, [], "in_progress"),
])
def test_target_status_follows_the_pull_request(kwargs, reviews, expected):
    assert target_status(pr(**kwargs), reviews) == expected


def test_paths_never_skip_a_step_or_pass_through_blocked():
    assert workflow_path("todo", "review") == ["in_progress", "review"]
    assert workflow_path("todo", "done") == ["in_progress", "review", "done"]
    assert workflow_path("review", "in_progress") == ["in_progress"]
    assert workflow_path("review", "review") == []


# ── Moving tasks ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_an_open_pull_request_moves_its_tasks_to_review_step_by_step():
    s = service(task(), task("TSK-0519EE96", "in_progress"))
    results = await s.apply(PROJECT, pr())
    assert [(r["task_id"], r["from"], r["to"]) for r in results] == [
        ("TSK-533075F3", "todo", "review"), ("TSK-0519EE96", "in_progress", "review")]
    assert [(t, a, b) for t, a, b, *_ in s.workflow.steps] == [
        ("TSK-533075F3", "todo", "in_progress"), ("TSK-533075F3", "in_progress", "review"),
        ("TSK-0519EE96", "in_progress", "review")]
    # Recorded as GitHub, with the reason.
    assert all(step[3] == "github" and step[4] == "GitHub (PR #1)" for step in s.workflow.steps)
    assert s.workflow.steps[0][5] == "Pull request #1 is waiting for review"


@pytest.mark.anyio
async def test_merge_finishes_the_task_and_repeating_changes_nothing():
    s = service(task(status="review"))
    merged = pr(state="closed", merged=True, title="TSK-533075F3")
    assert (await s.apply(PROJECT, merged))[0]["to"] == "done"
    assert (await s.apply(PROJECT, merged))[0]["steps"] == []
    assert len(s.workflow.steps) == 1


@pytest.mark.anyio
async def test_changes_requested_sends_the_task_back_to_in_progress():
    s = service(task(status="review"))
    reviews = [{"state": "CHANGES_REQUESTED", "submitted_at": "2026-11-15T10:00:00Z"}]
    assert (await s.apply(PROJECT, pr(title="TSK-533075F3"), reviews))[0]["to"] == "in_progress"


@pytest.mark.anyio
@pytest.mark.parametrize("the_task,users,login,reason", [
    (task(project="PRJ-OTHER"), (E5,), "Mallikarjuna902", "another project"),
    (task(assignee="E6"), (E5,), "Mallikarjuna902", "not the task's assignee"),
    (task(), (E5,), "someone-else", "not the task's assignee"),
    (task(), ({**E5, "is_active": False},), "Mallikarjuna902", "not the task's assignee"),
    (task(status="blocked"), (E5,), "Mallikarjuna902", "blocked"),
    (task(status="done"), (E5,), "Mallikarjuna902", "reopen it manually"),
])
async def test_tasks_are_only_moved_when_it_is_safe(the_task, users, login, reason):
    s = service(the_task, users=users)
    result = (await s.apply(PROJECT, pr(title="TSK-533075F3", login=login)))[0]
    assert reason in result["skipped"]
    assert s.workflow.steps == []


@pytest.mark.anyio
async def test_github_username_matching_ignores_case_and_unknown_ids_are_reported():
    s = service(task(), users=({**E5, "github_username": "mallikarjuna902"},))
    results = await s.apply(PROJECT, pr(title="TSK-533075F3 TSK-FFFFFFFF"))
    assert results[0]["to"] == "review"
    assert results[1] == {"task_id": "TSK-FFFFFFFF", "skipped": "No task with this ID"}


@pytest.mark.anyio
async def test_a_move_made_meanwhile_is_respected():
    s = service(task())
    real = s.workflow.transition_task

    async def someone_blocks_it_after_the_first_step(task_id, new_status, **kwargs):
        result = await real(task_id, new_status, **kwargs)
        s.task_repo.docs[task_id]["status"] = "blocked"
        return result
    s.workflow.transition_task = someone_blocks_it_after_the_first_step
    result = (await s.apply(PROJECT, pr(title="TSK-533075F3")))[0]
    assert (result["to"], result["steps"]) == ("in_progress", ["in_progress"])


@pytest.mark.anyio
async def test_nothing_happens_without_a_project_or_task_ids():
    s = service(task())
    assert await s.apply(None, pr()) == []
    assert await s.apply(PROJECT, pr(title="No ids", branch="main")) == []


@pytest.mark.anyio
async def test_failures_never_break_the_caller():
    with patch.object(tps, "TaskProgressService") as cls:
        cls.return_value.apply = AsyncMock(side_effect=RuntimeError("database down"))
        assert await apply_task_progress(PROJECT, pr()) == []


# ── Hooks ───────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_webhook_merge_and_review_events_apply_task_progress():
    from domain.services import webhook_event_processor as wep
    from domain.models.webhook_event import WebhookEvent
    processor = wep.WebhookEventProcessor.__new__(wep.WebhookEventProcessor)
    processor.notification_service = AsyncMock()
    processor.notification_service.notify = AsyncMock(return_value={"id": "N1"})
    merged = pr(state="closed", merged=True)
    with patch.object(wep, "apply_task_progress", AsyncMock(return_value=[{"task_id": "TSK-533075F3"}])) as apply:
        closed_event = WebhookEvent(id="EV1", event_type="pull_request", event_action="closed", repository="Mallikarjuna902/samanvaya-pilot",
                                    project_id=PROJECT, payload={"pull_request": merged, "repository": {"full_name": "Mallikarjuna902/samanvaya-pilot"}},
                                    created_at="2026-11-15T10:00:00Z")
        result = await processor._handle_pull_request_event(closed_event)
        assert "task_progress" in result["triggers_executed"]
        apply.assert_awaited_with(PROJECT, merged)

        review = {"state": "changes_requested", "user": {"login": "lead"}, "submitted_at": "2026-11-15T11:00:00Z"}
        review_event = WebhookEvent(id="EV2", event_type="pull_request_review", event_action="submitted",
                                    repository="Mallikarjuna902/samanvaya-pilot", project_id=PROJECT,
                                    payload={"review": review, "pull_request": pr()}, created_at="2026-11-15T11:00:00Z")
        result = await processor._handle_review_event(review_event)
        assert "task_progress" in result["triggers_executed"]
        apply.assert_awaited_with(PROJECT, pr(), [review])


def test_pull_request_sync_applies_task_progress_with_reviews():
    import inspect
    from domain.services import github_sync_service
    source = inspect.getsource(github_sync_service.GitHubSyncService.sync_pull_request)
    assert 'apply_task_progress(project_id, github_pr, github_data.get("reviews"))' in source
    assert source.count('"task_progress": task_progress') == 2
