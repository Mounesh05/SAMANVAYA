"""
CR-015: larger-company operating model (access and rules only).

The CEO sees everything, sets policy and gives final approvals. Admins set up
teams and platform-wide settings, HR records people changes, and engineering
owns its tools. PMs own delivery, not repositories, CI or PR syncing.
D1-A: the transfer management stage is the CEO's. D2-A: global risk defaults
are an admin setting. D3-A: Leads run individual AI evaluations.
"""

import inspect

import pytest
from fastapi import HTTPException

from core.permissions import ADMIN_PERMISSIONS, Permission, get_user_permissions


def user(role, is_admin=False):
    return {"employee_id": f"{role}-1", "id": f"{role}-1", "role": role, "organizational_role": role,
            "project_ids": [], "team_id": None, "org_id": "O1", "is_admin": is_admin}


PM_MOVED = [Permission.MANAGE_REPOSITORY_LINK, Permission.MANAGE_TEST_AUTOMATION,
            Permission.SYNC_REPOSITORY_PRS, Permission.APPROVE_TRANSFER_AS_MANAGEMENT]


@pytest.mark.parametrize("permission", PM_MOVED)
def test_pm_no_longer_holds_engineering_tools_or_the_management_stage(permission):
    assert permission not in get_user_permissions("PM")


@pytest.mark.parametrize("permission", PM_MOVED[:3])
def test_engineering_still_holds_them(permission):
    assert permission in get_user_permissions("LEAD") or permission in get_user_permissions("DEVOPS")


def test_admins_set_global_risk_defaults_and_set_up_teams():
    assert Permission.MANAGE_GLOBAL_RISK_CONFIG in ADMIN_PERMISSIONS
    admin = get_user_permissions("DEVELOPER", True)
    assert {Permission.MANAGE_GLOBAL_RISK_CONFIG, Permission.CREATE_TEAM, Permission.MANAGE_TEAMS} <= admin


def test_the_ceo_keeps_final_approvals_and_policy():
    ceo = get_user_permissions("CEO")
    assert {Permission.APPROVE_TRANSFER_AS_MANAGEMENT, Permission.MANAGE_EVALUATION_POLICY,
            Permission.VIEW_ALL_DATA} <= ceo


def test_hr_alone_executes_transfers():
    holders = {r for r in ["CEO", "PM", "LEAD", "HR", "DEVELOPER", "QA", "DEVOPS"]
               if Permission.EXECUTE_TRANSFER in get_user_permissions(r)}
    assert holders == {"HR"}


@pytest.mark.asyncio
async def test_individual_ai_evaluation_route_is_for_leads():
    from api.routes import evaluation
    check = inspect.signature(evaluation.evaluate_developer_ai).parameters["user"].default.dependency
    assert (await check(user=user("LEAD")))["role"] == "LEAD"
    for role, is_admin in [("CEO", False), ("CEO", True), ("PM", False), ("HR", False), ("DEVELOPER", True)]:
        with pytest.raises(HTTPException) as error:
            await check(user=user(role, is_admin))
        assert error.value.status_code == 403
