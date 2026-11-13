"""
Rules that used to compare role names now check permissions, with the same
holders as before. These guard the conversions made with the frontend clean-up.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import ADMIN_PERMISSIONS, Permission, ROLE_PERMISSIONS


def holders(permission):
    return {role.value for role, granted in ROLE_PERMISSIONS.items() if permission in granted}


def person(role, **extra):
    return {"employee_id": f"{role}-1", "role": role, "organizational_role": role, "project_ids": ["P1"],
            "team_id": "T1", "is_admin": False, "org_id": "O1", **extra}


def test_engineering_tools_keep_their_holders():
    assert holders(Permission.USE_ENGINEERING_INTELLIGENCE) == {"DEVELOPER", "LEAD", "PM", "CEO", "QA", "DEVOPS"}
    assert Permission.USE_ENGINEERING_INTELLIGENCE in ADMIN_PERMISSIONS  # the old admin bypass


def test_contract_approval_keeps_its_holders():
    assert holders(Permission.APPROVE_ENGINEERING_CONTRACTS) == {"LEAD", "PM", "CEO"}
    assert Permission.APPROVE_ENGINEERING_CONTRACTS not in ADMIN_PERMISSIONS  # CR-008


@pytest.mark.asyncio
async def test_engineering_access_is_by_permission():
    from api.routes.algorithms import engineering_user
    await engineering_user(person("QA"))
    await engineering_user(person("HR", is_admin=True))
    with pytest.raises(HTTPException):
        await engineering_user(person("HR"))


@pytest.mark.asyncio
@pytest.mark.parametrize("role, allowed", [("PM", True), ("LEAD", True), ("CEO", False), ("HR", False)])
async def test_moving_someone_elses_task(role, allowed):
    from core.authorization import verify_task_status_update_access
    with patch("core.authorization._task_repo") as tasks, patch("core.authorization._project_repo") as projects:
        tasks.find_by_id = AsyncMock(return_value={"id": "T-1", "project_id": "P1", "assignee_id": "OTHER"})
        projects.find_by_id = AsyncMock(return_value={"id": "P1", "team_id": "T1"})
        if allowed:
            assert await verify_task_status_update_access(person(role), "T-1") == "P1"
        else:
            with pytest.raises(HTTPException):
                await verify_task_status_update_access(person(role), "T-1")


@pytest.mark.asyncio
async def test_contributors_move_only_their_own_tasks():
    from core.authorization import verify_task_status_update_access
    with patch("core.authorization._task_repo") as tasks, patch("core.authorization._project_repo") as projects:
        projects.find_by_id = AsyncMock(return_value={"id": "P1", "team_id": "T1"})
        tasks.find_by_id = AsyncMock(return_value={"id": "T-1", "project_id": "P1", "assignee_id": "DEVELOPER-1"})
        assert await verify_task_status_update_access(person("DEVELOPER"), "T-1") == "P1"
        tasks.find_by_id = AsyncMock(return_value={"id": "T-1", "project_id": "P1", "assignee_id": "OTHER"})
        with pytest.raises(HTTPException):
            await verify_task_status_update_access(person("DEVELOPER"), "T-1")


@pytest.mark.asyncio
async def test_review_queue_is_team_data():
    import inspect
    from api.roles.lead import review_queue
    check = inspect.signature(review_queue).parameters["user"].default.dependency
    assert (await check(user=person("LEAD")))["role"] == "LEAD"
    with pytest.raises(HTTPException):
        await check(user=person("PM"))
    assert holders(Permission.VIEW_TEAM_DATA) == {"LEAD"}


@pytest.mark.parametrize("helper, role, expected", [
    ("_manages_defects", "QA", True), ("_manages_defects", "PM", True), ("_manages_defects", "LEAD", True),
    ("_manages_defects", "CEO", False), ("_manages_defects", "DEVELOPER", False),
    ("_own_defects_only", "DEVELOPER", True), ("_own_defects_only", "DEVOPS", True),
    ("_own_defects_only", "CEO", False), ("_own_defects_only", "QA", False),
    ("_reads_qa", "HR", False), ("_reads_qa", "CEO", True),
])
def test_defect_rules_keep_their_holders(helper, role, expected):
    from domain.services import qa_service
    assert getattr(qa_service, helper)(person(role)) is expected
