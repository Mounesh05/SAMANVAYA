"""
CR-006: HR access (access and rules only, no new backend structure).

Transfer HR and management stages are permission-based, HR (and the CEO)
execute approved transfers (D1-A), and Employee Relations can read the HR cases
it owns. Deactivation stays system-admin only (D2-A); designations remain
dormant until a designation field exists (D3-A, separate change).
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from core.permissions import Permission, ROLE_PERMISSIONS
from services.transfer_service import TransferService
from test_performance_access import records, service as performance_service  # noqa: F401  (fixture reuse)

HR_STAGES = ["pending_hr_validation", "pending_hr_review"]


def actor(role, designation=None, employee_id="X"):
    return {"employee_id": employee_id, "name": employee_id, "role": role, "designation": designation}


def can(stage, user):
    return TransferService.__new__(TransferService)._can_approve_at_stage(
        {"current_manager_id": "LEAD-1", "receiving_manager_id": "LEAD-2"}, stage,
        user["employee_id"], user["role"], user)


class TestTransferStages:
    @pytest.mark.parametrize("stage", HR_STAGES)
    def test_hr_reviewers_act_at_hr_stages(self, stage):
        assert can(stage, actor("HR"))
        assert can(stage, actor("HR", "HR_MANAGER"))
        assert can(stage, actor("HR", "HRBP"))

    @pytest.mark.parametrize("stage", HR_STAGES)
    @pytest.mark.parametrize("designation", ["RECRUITER", "EMPLOYEE_RELATIONS", "COMPENSATION_BENEFITS"])
    def test_hr_designations_without_review_rights_cannot(self, stage, designation):
        assert not can(stage, actor("HR", designation))

    @pytest.mark.parametrize("stage", HR_STAGES)
    @pytest.mark.parametrize("role", ["DEVELOPER", "LEAD", "PM", "QA", "DEVOPS", "CEO"])
    def test_non_hr_roles_cannot_act_at_hr_stages(self, stage, role):
        assert not can(stage, actor(role))

    def test_management_stage_is_the_ceo(self):
        # CR-015 D1-A: senior management (the CEO) approves moves between teams.
        allowed = {r for r in ["PM", "CEO", "LEAD", "HR", "DEVELOPER"] if can("pending_management_approval", actor(r))}
        assert allowed == {"CEO"}

    def test_manager_stages_stay_tied_to_the_named_manager(self):
        assert can("pending_current_manager_release", actor("LEAD", employee_id="LEAD-1"))
        assert not can("pending_current_manager_release", actor("LEAD", employee_id="LEAD-9"))

    def test_old_role_only_call_still_works(self):
        service = TransferService.__new__(TransferService)
        assert service._can_approve_at_stage({}, "pending_hr_validation", "H", "HR")


class TestExecution:
    def test_hr_executes(self):
        holders = {role.value for role, granted in ROLE_PERMISSIONS.items() if Permission.EXECUTE_TRANSFER in granted}
        assert holders == {"HR"}  # CR-015: not the CEO

    @pytest.mark.asyncio
    async def test_hr_executes_an_approved_transfer(self):
        service = TransferService.__new__(TransferService)
        service.transfer_repo = AsyncMock()
        service.user_repo = AsyncMock()
        transfer = {"id": "TRF-1", "status": "approved", "employee_id": "DEV-A", "requested_team_id": "TEAM-B"}
        service.transfer_repo.find_by_id = AsyncMock(side_effect=[transfer, {
            **transfer, "status": "effective", "employee_name": "D", "initiated_by": "D", "initiated_by_id": "D",
            "current_team_id": "TEAM-A", "reason": "r", "justification": "j", "workflow_type": "employee_initiated",
            "created_at": "", "updated_at": ""}])
        service.user_repo.find_by_employee_id = AsyncMock(return_value={"employee_id": "DEV-A"})
        result = await service.execute_transfer("TRF-1", actor("HR", employee_id="HR-1"))
        assert result.status == "effective"
        service.user_repo.update.assert_awaited_once_with({"employee_id": "DEV-A"}, {"team_id": "TEAM-B"})

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["PM", "LEAD", "DEVELOPER"])
    async def test_others_cannot_execute(self, role):
        service = TransferService.__new__(TransferService)
        service.transfer_repo = AsyncMock()
        service.transfer_repo.find_by_id = AsyncMock(return_value={"id": "TRF-1", "status": "approved"})
        with pytest.raises(ValueError):
            await service.execute_transfer("TRF-1", actor(role))


# ── Employee Relations case access ──────────────────────────────────────────

@pytest.mark.anyio
async def test_employee_relations_reads_its_own_hr_case(records):  # noqa: F811
    await records.users.insert_one({"employee_id": "ER-1", "role": "HR", "designation": "EMPLOYEE_RELATIONS",
                                    "org_id": "O1", "is_active": True})
    record = await records.developer_performances.find_one({})
    await records.hr_assessments.insert_one({"developer_id": "AUDIT-DEV", "evaluator_id": "ER-1", "org_id": "O1",
                                             "performance_id": str(record["_id"]), "notes": "case"})
    case = await performance_service().hr_case(str(record["_id"]), {"employee_id": "ER-1"})
    assert case and case["evaluator_id"] == "ER-1"


@pytest.mark.anyio
async def test_employee_relations_still_gets_no_general_outcomes(records):  # noqa: F811
    await records.users.insert_one({"employee_id": "ER-1", "role": "HR", "designation": "EMPLOYEE_RELATIONS",
                                    "org_id": "O1", "is_active": True})
    with pytest.raises(HTTPException) as error:
        await performance_service().detail("AUDIT-DEV", {"employee_id": "ER-1"})
    assert error.value.status_code == 403


@pytest.mark.anyio
async def test_recruiter_cannot_read_hr_cases(records):  # noqa: F811
    await records.users.insert_one({"employee_id": "RC-1", "role": "HR", "designation": "RECRUITER",
                                    "org_id": "O1", "is_active": True})
    record = await records.developer_performances.find_one({})
    with pytest.raises(HTTPException) as error:
        await performance_service().hr_case(str(record["_id"]), {"employee_id": "RC-1"})
    assert error.value.status_code == 403
