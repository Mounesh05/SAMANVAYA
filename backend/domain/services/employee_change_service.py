"""
CR-010: two-person approval for account changes.

Granting or removing admin rights, changing a role, and activating or
deactivating an account are made by one person and confirmed by a second,
independent person (D1-A). Approvers come from the existing roles only (D2-A):

- admin rights and active status: another active admin;
- role changes: another active admin, or another holder of MANAGE_EMPLOYEES.

Neither the requester nor the person being changed can approve. When nobody
else is eligible the change is applied at once and audited as such (D3-A).
The rules are checked again when an approved change is applied.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.audit import AuditAction, log_audit
from core.permissions import Permission, get_user_permissions
from domain.services.hitl_workflow_service import ApprovalPriority, hitl_service

COVERED_FIELDS = ("is_admin", "is_active", "role")
KIND = "employee_change"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_value(employee: dict, field: str):
    if field == "is_active":
        return employee.get("is_active", True)
    if field == "is_admin":
        return bool(employee.get("is_admin", False))
    return (employee.get(field) or "").upper()


def covered_changes(employee: dict, update_data: dict) -> Dict[str, Any]:
    """Remove covered fields from update_data; return those that really change."""
    change = {}
    for field in COVERED_FIELDS:
        if field in update_data:
            value = update_data.pop(field)
            if value != current_value(employee, field):
                change[field] = value
    return change


async def refuse_if_last_admin(repo, employee: dict) -> None:
    """CR-008: never remove admin rights from, or deactivate, the last active admin."""
    if not employee.get("is_admin") or employee.get("is_active", True) is False:
        return
    others = await repo.col.count_documents({
        "is_admin": True,
        "is_active": {"$ne": False},
        "employee_id": {"$ne": employee.get("employee_id")},
    })
    if others == 0:
        raise HTTPException(
            status_code=409,
            detail="This is the last active admin. Make another employee an admin first.",
        )


async def eligible_approvers(repo, change: Dict[str, Any], requester_id: str, subject_id: str) -> List[str]:
    admin_only = "is_admin" in change or "is_active" in change
    people = await repo.col.find(
        {"is_active": {"$ne": False}},
        {"_id": 0, "employee_id": 1, "role": 1, "is_admin": 1, "designation": 1},
    ).to_list(length=None)
    approvers = []
    for person in people:
        employee_id = person.get("employee_id")
        if not employee_id or employee_id in (requester_id, subject_id):
            continue
        if person.get("is_admin"):
            approvers.append(employee_id)
        elif not admin_only and Permission.MANAGE_EMPLOYEES in get_user_permissions(
                person.get("role") or "", False, person.get("designation")):
            approvers.append(employee_id)
    return approvers


def describe(employee: dict, change: Dict[str, Any]) -> str:
    name = employee.get("name") or employee.get("employee_id")
    parts = []
    if "is_admin" in change:
        parts.append("grant admin rights to" if change["is_admin"] else "remove admin rights from")
    if "is_active" in change:
        parts.append("reactivate" if change["is_active"] else "deactivate")
    if "role" in change:
        parts.append(f"change the role ({current_value(employee, 'role')} to {change['role']}) of")
    text = f"{', '.join(parts)} {name} ({employee.get('employee_id')})"
    return text[:1].upper() + text[1:]


async def _recheck(repo, employee: dict, change: Dict[str, Any]) -> None:
    if change.get("is_active") is False and (employee.get("role") or "").upper() == "CEO":
        raise HTTPException(status_code=403, detail="The CEO account cannot be deactivated.")
    if (change.get("role") or "").upper() == "CEO":
        raise HTTPException(status_code=403, detail="Cannot assign or promote an employee to CEO through employee administration.")
    if change.get("is_admin") is False or change.get("is_active") is False:
        await refuse_if_last_admin(repo, employee)


async def apply_change(repo, employee_id: str, change: Dict[str, Any], *, actor: dict,
                       requested_by: str, approved_by: Optional[str], approval_id: Optional[str] = None) -> dict:
    """Apply a covered change after checking the rules again. Returns the updated record."""
    employee = await repo.find_by_employee_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    await _recheck(repo, employee, change)

    data = dict(change)
    old_designation = employee.get("designation")
    if "role" in change and change["role"] != "HR" and old_designation:
        data["designation"] = None  # CR-009: leaving HR clears the designation
    if change.get("is_active") is False:
        data["deactivated_at"] = _now()
        data["deactivated_by"] = approved_by or requested_by
    data["updated_at"] = _now()
    data["updated_by"] = requested_by
    await repo.update_one({"employee_id": employee_id}, {"$set": data})

    details = {"requested_by": requested_by, "approved_by": approved_by, "approval_id": approval_id,
               "second_approver": "approved" if approved_by else "none_available"}
    audit = dict(actor=actor, resource_type="employee", resource_id=employee_id)
    if "is_admin" in change:
        await log_audit(action=AuditAction.ADMIN_GRANTED if change["is_admin"] else AuditAction.ADMIN_REVOKED,
                        details=details, **audit)
    if "is_active" in change:
        await log_audit(action=AuditAction.USER_ACTIVATED if change["is_active"] else AuditAction.USER_DEACTIVATED,
                        details=details, **audit)
    if "role" in change:
        await log_audit(action=AuditAction.USER_UPDATED, details={
            **details, "field": "role", "old": current_value(employee, "role"), "new": change["role"]}, **audit)
    if data.get("designation", old_designation) != old_designation:
        await log_audit(action=AuditAction.USER_UPDATED, details={
            **details, "field": "designation", "old": old_designation, "new": None}, **audit)
    return await repo.find_by_employee_id(employee_id)


async def request_or_apply(repo, employee: dict, change: Dict[str, Any], actor: dict) -> Dict[str, Any]:
    """Send a covered change for approval, or apply it when nobody else can approve (D3-A)."""
    requester = actor.get("employee_id")
    subject = employee.get("employee_id")
    await _recheck(repo, employee, change)
    approvers = await eligible_approvers(repo, change, requester, subject)
    if not approvers:
        await apply_change(repo, subject, change, actor=actor, requested_by=requester, approved_by=None)
        return {"status": "applied", "second_approver": "none_available"}

    approval = await hitl_service.request_approval(
        action=KIND,
        description=describe(employee, change),
        agent_name="employee-administration",
        context={"employee_id": subject, "employee_name": employee.get("name"),
                 "current": {field: current_value(employee, field) for field in change}},
        impact_level="high",
        priority=ApprovalPriority.HIGH,
        approvers=approvers,
        requested_by=requester,
        kind=KIND,
        change={"employee_id": subject, "fields": change},
    )
    await log_audit(action=AuditAction.USER_UPDATED, actor=actor, resource_type="employee", resource_id=subject,
                    details={"approval_requested": approval.id, "change": change})
    return {"status": "pending_approval", "approval_id": approval.id, "change": change}
