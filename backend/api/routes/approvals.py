"""
Approval Workflow API Routes - Phase 3.2

All endpoints require JWT authentication.
Approve/reject actions verify the caller is an authorized approver.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from domain.services.hitl_workflow_service import hitl_service, ApprovalPriority
from core.dependencies import get_current_user, require_admin
from core.authorization import has_org_access
from core.audit import AuditAction, log_audit
from domain.services import employee_change_service as changes
from repositories.user_repository import UserRepository

router = APIRouter()


class ApproveRequest(BaseModel):
    comment: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str


class CreateApprovalRequest(BaseModel):
    action: str
    description: str
    agent_name: str
    context: dict
    impact_level: str
    priority: str
    approvers: List[str]


@router.get("/pending")
async def get_pending_approvals(
    current_user: dict = Depends(get_current_user),
):
    """Get all pending approvals for the authenticated user."""
    user_id = current_user["employee_id"]
    approvals = await hitl_service.get_pending_for_user(user_id)
    return {"approvals": approvals, "count": len(approvals)}


@router.get("/mine")
async def get_my_requests(
    current_user: dict = Depends(get_current_user),
):
    """CR-010: pending requests raised by the authenticated user."""
    requests = await hitl_service.get_requested_by(current_user["employee_id"])
    return {"approvals": requests, "count": len(requests)}


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get approval request details."""
    approval = await hitl_service.get_approval_status(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    # Authorization: approver, requester, or org access
    user_id = current_user["employee_id"]
    if (user_id not in approval["approvers"] and user_id != approval.get("requested_by")
            and not has_org_access(current_user)):
        raise HTTPException(status_code=403, detail="Access denied")

    return approval


@router.post("/")
async def create_approval(
    request: CreateApprovalRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create new approval request. Only PM/LEAD/CEO can create approval requests."""
    # Authorization: only PM/LEAD/CEO can request approvals
    user_role = current_user.get('role', '').upper()
    if user_role not in ('PM', 'LEAD', 'CEO') and not has_org_access(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only PM, LEAD, or CEO can create approval requests"
        )

    try:
        approval = await hitl_service.request_approval(
            action=request.action,
            description=request.description,
            agent_name=request.agent_name,
            context=request.context,
            impact_level=request.impact_level,
            priority=ApprovalPriority(request.priority),
            approvers=request.approvers,
            requested_by=current_user["employee_id"],  # CR-010: never an approver
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return approval.to_dict()


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    request: ApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """Approve an approval request. Caller must be an authorized approver."""
    approver_id = current_user["employee_id"]
    approval = await hitl_service.get_approval_status(approval_id)
    if approval and approval.get("kind") == changes.KIND:
        return await _approve_employee_change(approval, current_user, request.comment)
    success = await hitl_service.approve(
        approval_id=approval_id,
        approver_id=approver_id,
        comment=request.comment
    )

    if not success:
        raise HTTPException(status_code=400, detail="Could not approve request")

    return {"success": True, "approval_id": approval_id}


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    request: RejectRequest,
    current_user: dict = Depends(get_current_user),
):
    """Reject an approval request. Caller must be an authorized approver."""
    rejector_id = current_user["employee_id"]
    approval = await hitl_service.get_approval_status(approval_id)
    success = await hitl_service.reject(
        approval_id=approval_id,
        rejector_id=rejector_id,
        reason=request.reason
    )

    if not success:
        raise HTTPException(status_code=400, detail="Could not reject request")
    if approval and approval.get("kind") == changes.KIND:
        await log_audit(action=AuditAction.USER_UPDATED, actor=current_user, resource_type="employee",
                        resource_id=approval["change"]["employee_id"],
                        details={"approval_rejected": approval_id, "reason": request.reason,
                                 "requested_by": approval.get("requested_by")})

    return {"success": True, "approval_id": approval_id}


async def _approve_employee_change(approval: dict, current_user: dict, comment):
    """CR-010: a second, eligible person approves; the change is re-checked and applied."""
    approver_id = current_user["employee_id"]
    subject = approval["change"]["employee_id"]
    fields = approval["change"]["fields"]
    repo = UserRepository()
    if approver_id not in await changes.eligible_approvers(repo, fields, approval.get("requested_by"), subject):
        raise HTTPException(status_code=403, detail="You are not eligible to approve this change")
    claimed = await hitl_service.claim(approval["id"], approver_id, comment)
    if not claimed:
        raise HTTPException(status_code=400, detail="Could not approve: it has expired, was already handled, or you raised it")
    try:
        await changes.apply_change(repo, subject, fields, actor=current_user,
                                   requested_by=approval.get("requested_by"), approved_by=approver_id,
                                   approval_id=approval["id"])
    except HTTPException as error:
        await hitl_service.mark_failed(approval["id"], str(error.detail))
        raise HTTPException(status_code=409, detail=f"Approved, but the change could not be applied: {error.detail}")
    return {"success": True, "approval_id": approval["id"], "applied": True}


@router.post("/cleanup")
async def cleanup_expired_approvals(
    current_user: dict = Depends(require_admin()),
):
    """Cleanup expired approval requests. Platform maintenance: admins only."""
    count = await hitl_service.cleanup_expired()
    return {"expired_count": count}
