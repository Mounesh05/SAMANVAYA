"""
Approval Workflow API Routes - Phase 3.2

All endpoints require JWT authentication.
Approve/reject actions verify the caller is an authorized approver.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from domain.services.hitl_workflow_service import hitl_service, ApprovalPriority
from core.dependencies import get_current_user

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


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get approval request details."""
    approval = await hitl_service.get_approval_status(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post("/")
async def create_approval(
    request: CreateApprovalRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create new approval request."""
    approval = await hitl_service.request_approval(
        action=request.action,
        description=request.description,
        agent_name=request.agent_name,
        context=request.context,
        impact_level=request.impact_level,
        priority=ApprovalPriority(request.priority),
        approvers=request.approvers
    )
    return approval.to_dict()


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    request: ApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """Approve an approval request. Caller must be an authorized approver."""
    approver_id = current_user["employee_id"]
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
    success = await hitl_service.reject(
        approval_id=approval_id,
        rejector_id=rejector_id,
        reason=request.reason
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Could not reject request")
    
    return {"success": True, "approval_id": approval_id}


@router.post("/cleanup")
async def cleanup_expired_approvals(
    current_user: dict = Depends(get_current_user),
):
    """Cleanup expired approval requests."""
    count = await hitl_service.cleanup_expired()
    return {"expired_count": count}
