"""
CR-010: two-person approval for account changes (existing roles only).

Admin rights, role changes and activation/deactivation go to a second person
(D1-A): another admin for admin rights and active status, another admin or
MANAGE_EMPLOYEES holder for role changes (D2-A). With nobody else eligible the
change applies with an audited exception (D3-A). The approvals workflow no
longer allows self-approval or approving expired requests.
"""

from datetime import datetime, timedelta, timezone

import pytest

from approval_helpers import approve, body, refused, reject, update, wire


def person(employee_id, role="DEVELOPER", is_admin=False, designation=None, is_active=True):
    return {"employee_id": employee_id, "name": employee_id, "email": f"{employee_id.lower()}@samanvaya.com",
            "role": role, "dept": "X", "is_admin": is_admin, "is_active": is_active, "designation": designation}


ADM1 = {"employee_id": "ADM-1", "name": "Ada", "role": "DEVELOPER", "is_admin": True}
ADM2 = {"employee_id": "ADM-2", "name": "Bo", "role": "DEVOPS", "is_admin": True}
HR1 = {"employee_id": "HR-1", "name": "Hana", "role": "HR", "is_admin": False}
HR2 = {"employee_id": "HR-2", "name": "Hugo", "role": "HR", "is_admin": False}


@pytest.fixture
async def org(mock_db, monkeypatch):
    audit = wire(mock_db, monkeypatch)
    await mock_db.users.insert_many([
        person("ADM-1", is_admin=True), person("ADM-2", "DEVOPS", is_admin=True),
        person("HR-1", "HR"), person("HR-2", "HR"), person("DEV-1"), person("CEO-1", "CEO"),
    ])
    yield mock_db, audit


async def user_doc(db, employee_id):
    return await db.users.find_one({"employee_id": employee_id})


class TestPending:
    @pytest.mark.anyio
    async def test_admin_grant_waits_for_a_second_admin_then_applies(self, org):
        db, audit = org
        pending = body(await update("DEV-1", ADM1, is_admin=True))
        assert pending["status"] == "pending_approval"
        assert (await user_doc(db, "DEV-1"))["is_admin"] is False
        approval = await db.approvals.find_one({"id": pending["approval_id"]})
        assert approval["approvers"] == ["ADM-2"] and approval["requested_by"] == "ADM-1"

        await approve(pending["approval_id"], ADM2)
        assert (await user_doc(db, "DEV-1"))["is_admin"] is True
        granted = [c.kwargs for c in audit.await_args_list if c.kwargs["action"].value == "ADMIN_GRANTED"][0]
        assert granted["details"]["requested_by"] == "ADM-1" and granted["details"]["approved_by"] == "ADM-2"

    @pytest.mark.anyio
    async def test_other_fields_in_the_same_edit_apply_now(self, org):
        db, _ = org
        result = body(await update("DEV-1", ADM1, dept="Platform", is_admin=True))
        assert result["status"] == "pending_approval"
        doc = await user_doc(db, "DEV-1")
        assert doc["dept"] == "Platform" and doc["is_admin"] is False

    @pytest.mark.anyio
    async def test_deactivation_by_delete_waits_too(self, org):
        from api.routes.employees import delete_employee
        db, _ = org
        result = body(await delete_employee("DEV-1", ADM1))
        assert result["status"] == "pending_approval"
        assert (await user_doc(db, "DEV-1"))["is_active"] is True
        await approve(result["approval_id"], ADM2)
        assert (await user_doc(db, "DEV-1"))["is_active"] is False

    @pytest.mark.anyio
    async def test_role_change_can_be_approved_by_another_hr_person(self, org):
        db, _ = org
        pending = body(await update("DEV-1", HR1, role="QA"))
        approval = await db.approvals.find_one({"id": pending["approval_id"]})
        assert set(approval["approvers"]) == {"ADM-1", "ADM-2", "HR-2"}
        await approve(pending["approval_id"], HR2)
        assert (await user_doc(db, "DEV-1"))["role"] == "QA"

    @pytest.mark.anyio
    async def test_unchanged_values_are_not_sent_for_approval(self, org):
        db, _ = org
        result = await update("DEV-1", ADM1, is_admin=False, dept="Y")
        assert getattr(result, "status_code", 200) != 202
        assert await db.approvals.count_documents({}) == 0


class TestWhoMayApprove:
    @pytest.mark.anyio
    async def test_hr_cannot_approve_admin_rights(self, org):
        pending = body(await update("DEV-1", ADM1, is_admin=True))
        await refused(approve(pending["approval_id"], HR2), 403)

    @pytest.mark.anyio
    async def test_the_requester_cannot_approve(self, org):
        pending = body(await update("DEV-1", HR1, role="QA"))
        await refused(approve(pending["approval_id"], HR1), 403)

    @pytest.mark.anyio
    async def test_the_subject_cannot_approve_their_own_change(self, org):
        pending = body(await update("ADM-2", HR1, role="QA"))
        await refused(approve(pending["approval_id"], ADM2), 403)

    @pytest.mark.anyio
    async def test_reject_changes_nothing_and_is_audited(self, org):
        db, audit = org
        pending = body(await update("DEV-1", ADM1, is_admin=True))
        await reject(pending["approval_id"], ADM2, "not needed")
        assert (await user_doc(db, "DEV-1"))["is_admin"] is False
        assert audit.await_args.kwargs["details"]["approval_rejected"] == pending["approval_id"]
        await refused(approve(pending["approval_id"], ADM2), 400)

    @pytest.mark.anyio
    async def test_expired_requests_cannot_be_approved(self, org):
        db, _ = org
        pending = body(await update("DEV-1", ADM1, is_admin=True))
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        await db.approvals.update_one({"id": pending["approval_id"]}, {"$set": {"expires_at": past}})
        await refused(approve(pending["approval_id"], ADM2), 400)
        assert (await user_doc(db, "DEV-1"))["is_admin"] is False


class TestRulesRecheckedAndExceptions:
    @pytest.mark.anyio
    async def test_change_that_breaks_a_rule_by_approval_time_is_not_applied(self, org):
        db, _ = org
        pending = body(await update("DEV-1", ADM1, is_active=False))
        await db.users.update_one({"employee_id": "DEV-1"}, {"$set": {"role": "CEO"}})  # now protected
        error = await refused(approve(pending["approval_id"], ADM2), 409)
        assert "could not be applied" in error.detail
        assert (await user_doc(db, "DEV-1"))["is_active"] is True
        assert (await db.approvals.find_one({"id": pending["approval_id"]}))["status"] == "failed"

    @pytest.mark.anyio
    async def test_no_second_admin_applies_with_an_audited_exception(self, mock_db, monkeypatch):
        audit = wire(mock_db, monkeypatch)
        await mock_db.users.insert_many([person("CEO-1", "CEO", is_admin=True), person("IT-1")])
        ceo = {"employee_id": "CEO-1", "name": "Chief", "role": "CEO", "is_admin": True}
        result = body(await update("IT-1", ceo, is_admin=True))
        assert result["is_admin"] is True
        assert (await mock_db.users.find_one({"employee_id": "IT-1"}))["is_admin"] is True
        assert audit.await_args.kwargs["details"]["second_approver"] == "none_available"
        assert await mock_db.approvals.count_documents({}) == 0

    @pytest.mark.anyio
    async def test_creating_an_admin_account_directly_is_refused(self, org):
        from api.routes.employees import EmployeeCreate, create_employee
        employee = EmployeeCreate(employee_id="NEW-1", name="N", email="n.ew@samanvaya.com", role="DEVELOPER",
                                  dept="X", organisation_password="Org-Passw0rd!x", employee_password="Emp-Passw0rd!y",
                                  is_admin=True)
        await refused(create_employee(employee, ADM1), 422)


class TestGeneralRequests:
    @pytest.mark.anyio
    async def test_general_requests_cannot_name_only_the_requester(self, org):
        from api.routes.approvals import CreateApprovalRequest, create_approval
        request = CreateApprovalRequest(action="merge_pr", description="d", agent_name="a", context={},
                                        impact_level="low", priority="normal", approvers=["PM-1"])
        await refused(create_approval(request, {"employee_id": "PM-1", "role": "PM"}), 422)

    @pytest.mark.anyio
    async def test_requester_is_dropped_from_approvers_and_cannot_approve(self, org):
        from api.routes.approvals import CreateApprovalRequest, create_approval
        db, _ = org
        request = CreateApprovalRequest(action="merge_pr", description="d", agent_name="a", context={},
                                        impact_level="low", priority="normal", approvers=["PM-1", "LEAD-1"])
        created = await create_approval(request, {"employee_id": "PM-1", "role": "PM"})
        assert created["approvers"] == ["LEAD-1"] and created["requested_by"] == "PM-1"
        await refused(approve(created["id"], {"employee_id": "PM-1", "role": "PM"}), 400)
        assert (await approve(created["id"], {"employee_id": "LEAD-1", "role": "LEAD"}))["success"] is True

    @pytest.mark.anyio
    async def test_my_requests_lists_what_i_raised(self, org):
        from api.routes.approvals import get_my_requests
        await update("DEV-1", ADM1, is_admin=True)
        mine = await get_my_requests(ADM1)
        assert mine["count"] == 1 and mine["approvals"][0]["kind"] == "employee_change"
