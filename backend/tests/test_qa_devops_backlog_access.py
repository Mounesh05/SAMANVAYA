"""QA and DevOps team-scoped backlog access regression tests."""

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch

from core.permissions import Permission, get_user_permissions
from domain.services.sprint_service import SprintService
from domain.services.story_service import StoryService
from domain.services.task_service import TaskService


PROJECT_ID = "PRJ-D0213890"
TEAM_ID = "TEAM-CAMPUS-78C8F16E"
SPRINT_ID = "SPR-231ACC90"


def create_user(role: str, employee_id: str) -> dict:
    return {
        "employee_id": employee_id,
        "id": employee_id,
        "name": role,
        "role": role,
        "organizational_role": role,
        "project_ids": [],
        "team_id": TEAM_ID,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "employee_id", "story_id"),
    [
        ("QA", "DEMO-QA", "CC-05"),
        ("DEVOPS", "DEMO-DEVOPS", "CC-06"),
    ],
)
async def test_backlog_roles_read_project_sprint_story_and_assigned_tasks(
    role, employee_id, story_id
):
    user = create_user(role, employee_id)

    with patch("core.authorization._project_repo") as project_repo:
        project_repo.find_by_id = AsyncMock(
            return_value={"id": PROJECT_ID, "team_id": TEAM_ID}
        )
        with patch("api.routes.projects.project_service") as project_service:
            project_service.get_project = AsyncMock(
                return_value={"id": PROJECT_ID, "team_id": TEAM_ID}
            )
            from api.routes.projects import get_project

            project = await get_project(PROJECT_ID, user=user)
            assert project["id"] == PROJECT_ID

        with patch.object(
            SprintService,
            "get_project_sprints",
            new=AsyncMock(return_value=[{"id": SPRINT_ID, "project_id": PROJECT_ID}]),
        ):
            from api.routes.sprints import list_project_sprints

            sprints = await list_project_sprints(PROJECT_ID, user=user)
            assert sprints[0]["id"] == SPRINT_ID

        with patch("api.routes.stories.sprint_repo") as sprint_repo:
            sprint_repo.find_by_id = AsyncMock(
                return_value={"id": SPRINT_ID, "project_id": PROJECT_ID}
            )
            with patch.object(StoryService, "get_sprint_stories", new=AsyncMock(
                return_value=[{"id": story_id, "project_id": PROJECT_ID}]
            )):
                from api.routes.stories import list_sprint_stories

                stories = await list_sprint_stories(SPRINT_ID, user=user)
                assert stories[0]["id"] == story_id

        with patch("core.authorization._story_repo") as story_repo:
            story_repo.find_by_id = AsyncMock(
                return_value={"id": story_id, "project_id": PROJECT_ID}
            )
            with patch.object(TaskService, "get_story_tasks", new=AsyncMock(
                return_value=[
                    {
                        "id": f"TASK-{role}",
                        "project_id": PROJECT_ID,
                        "story_id": story_id,
                        "assignee_id": employee_id,
                    }
                ]
            )):
                from api.routes.tasks import list_story_tasks

                tasks = await list_story_tasks(story_id, user=user)
                assert tasks[0]["story_id"] == story_id
                assert tasks[0]["assignee_id"] == employee_id


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["QA", "DEVOPS"])
async def test_backlog_roles_cannot_read_other_team_project(role):
    user = create_user(role, f"DEMO-{role}")
    with patch("core.authorization._project_repo") as project_repo:
        project_repo.find_by_id = AsyncMock(
            return_value={"id": "PRJ-OTHER", "team_id": "TEAM-OTHER"}
        )
        from core.authorization import verify_project_access

        with pytest.raises(HTTPException) as exc_info:
            await verify_project_access(user, "PRJ-OTHER")
        assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    ("role", "employee_id"),
    [("QA", "DEMO-QA"), ("DEVOPS", "DEMO-DEVOPS")],
)
@pytest.mark.asyncio
async def test_backlog_roles_can_transition_only_their_assigned_tasks(role, employee_id):
    from core.authorization import verify_task_status_update_access

    user = create_user(role, employee_id)
    with patch("core.authorization._task_repo") as task_repo:
        task_repo.find_by_id = AsyncMock(
            return_value={
                "id": "TASK-OWN",
                "project_id": PROJECT_ID,
                "assignee_id": employee_id,
            }
        )
        with patch("core.authorization._project_repo") as project_repo:
            project_repo.find_by_id = AsyncMock(
                return_value={"id": PROJECT_ID, "team_id": TEAM_ID}
            )
            assert await verify_task_status_update_access(user, "TASK-OWN") == PROJECT_ID

        task_repo.find_by_id = AsyncMock(
            return_value={
                "id": "TASK-OTHER",
                "project_id": PROJECT_ID,
                "assignee_id": "DEMO-MOUNESH",
            }
        )
        with pytest.raises(HTTPException) as exc_info:
            await verify_task_status_update_access(user, "TASK-OTHER")
        assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    ("role", "employee_id"),
    [("QA", "DEMO-QA"), ("DEVOPS", "DEMO-DEVOPS")],
)
@pytest.mark.asyncio
async def test_backlog_roles_transition_own_task_through_workflow(role, employee_id):
    from api.routes.tasks import update_task_status
    from domain.services.workflow_service import WorkflowService

    user = create_user(role, employee_id)
    with patch("core.authorization._task_repo") as task_repo:
        task_repo.find_by_id = AsyncMock(
            return_value={
                "id": "TASK-OWN",
                "project_id": PROJECT_ID,
                "assignee_id": employee_id,
            }
        )
        with patch("core.authorization._project_repo") as project_repo:
            project_repo.find_by_id = AsyncMock(
                return_value={"id": PROJECT_ID, "team_id": TEAM_ID}
            )
            with patch.object(
                WorkflowService,
                "transition_task",
                new=AsyncMock(
                    return_value={"id": "TASK-OWN", "status": "in_progress"}
                ),
            ) as transition:
                result = await update_task_status(
                    "TASK-OWN", "in_progress", user=user
                )
                assert result["status"] == "in_progress"
                transition.assert_awaited_once()


@pytest.mark.asyncio
async def test_developer_own_task_restriction_remains():
    from core.authorization import verify_task_status_update_access

    user = create_user("DEVELOPER", "DEMO-MOUNESH")
    with patch("core.authorization._task_repo") as task_repo:
        task_repo.find_by_id = AsyncMock(
            return_value={
                "id": "TASK-OTHER",
                "project_id": PROJECT_ID,
                "assignee_id": "DEMO-SUMITH",
            }
        )
        with pytest.raises(HTTPException) as exc_info:
            await verify_task_status_update_access(user, "TASK-OTHER")
        assert exc_info.value.status_code == 403


@pytest.mark.parametrize("role", ["PM", "LEAD"])
@pytest.mark.asyncio
async def test_pm_and_lead_keep_task_transition_permissions(role):
    from core.authorization import verify_task_status_update_access

    user = create_user(role, f"DEMO-{role}")
    if role == "PM":
        user["project_ids"] = [PROJECT_ID]  # CR-013: PMs manage assigned projects
    with patch("core.authorization._task_repo") as task_repo:
        task_repo.find_by_id = AsyncMock(
            return_value={"id": "TASK-1", "project_id": PROJECT_ID}
        )
        with patch("core.authorization._project_repo") as project_repo:
            project_repo.find_by_id = AsyncMock(
                return_value={"id": PROJECT_ID, "team_id": TEAM_ID}
            )
            assert await verify_task_status_update_access(user, "TASK-1") == PROJECT_ID


@pytest.mark.parametrize("role", ["QA", "DEVOPS"])
def test_backlog_roles_receive_only_scoped_transition_capability(role):
    permissions = get_user_permissions(role)
    assert Permission.VIEW_PROJECT_DATA in permissions
    assert Permission.TRANSITION_TASK in permissions
    assert Permission.MOVE_TASK not in permissions
    assert Permission.CREATE_TASK not in permissions
    assert Permission.CREATE_SPRINT not in permissions
    assert Permission.CREATE_PROJECT not in permissions
    assert Permission.CREATE_STORY not in permissions
    assert Permission.MANAGE_EMPLOYEES not in permissions
    assert Permission.MANAGE_TEAMS not in permissions
    assert Permission.ASSIGN_PROJECT not in permissions
    assert Permission.TRIGGER_AI_EVALUATION not in permissions
    assert Permission.MANAGE_SETTINGS not in permissions


def test_pm_permissions_are_preserved():
    permissions = get_user_permissions("PM")
    assert Permission.CREATE_PROJECT in permissions
    assert Permission.CREATE_TASK in permissions
    assert Permission.CREATE_SPRINT in permissions
    assert Permission.CREATE_STORY in permissions
    assert Permission.TRANSITION_TASK in permissions


def test_lead_permissions_are_preserved():
    permissions = get_user_permissions("LEAD")
    assert Permission.CREATE_TASK in permissions
    assert Permission.CREATE_STORY in permissions
    assert Permission.TRANSITION_TASK in permissions
    assert Permission.CREATE_SPRINT in permissions  # CR-004 Decision 1: Leads run team sprints


@pytest.mark.parametrize("role", ["QA", "DEVOPS"])
@pytest.mark.asyncio
async def test_backlog_roles_cannot_transition_task_in_another_project(role):
    from core.authorization import verify_task_status_update_access

    employee_id = f"DEMO-{role}"
    user = create_user(role, employee_id)
    with patch("core.authorization._task_repo") as task_repo:
        task_repo.find_by_id = AsyncMock(
            return_value={
                "id": "TASK-OTHER-PROJECT",
                "project_id": "PRJ-OTHER",
                "assignee_id": employee_id,
            }
        )
        with patch("core.authorization._project_repo") as project_repo:
            project_repo.find_by_id = AsyncMock(
                return_value={"id": "PRJ-OTHER", "team_id": "TEAM-OTHER"}
            )
            with pytest.raises(HTTPException) as exc_info:
                await verify_task_status_update_access(user, "TASK-OTHER-PROJECT")
            assert exc_info.value.status_code == 403
