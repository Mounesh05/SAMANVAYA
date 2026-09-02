"""
Approval Workflow API Routes - Phase 3.2
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from domain.services.hitl_workflow_service import hitl_service, ApprovalPriority

router = APIRouter()


class ApproveRequest(BaseModel):
    approver_id: str
    comment: Optional[str] = None


class RejectRequest(BaseModel):
    rejector_id: str
    reason: str


class CreateApprovalRequest(BaseModel):
    action: str
    description: str
    agent_name: str
    context: dict
    impact_level: str
    priority: str
    approvers: List[str]


@router.get("/approvals/pending/{user_id}")
async def get_pending_approvals(user_id: str):
    """Get all pending approvals for a user."""
    approvals = await hitl_service.get_pending_for_user(user_id)
    return {"approvals": approvals, "count": len(approvals)}


@router.get("/approvals/{approval_id}")
async def get_approval(approval_id: str):
    """Get approval request details."""
    approval = await hitl_service.get_approval_status(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post("/approvals")
async def create_approval(request: CreateApprovalRequest):
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


@router.post("/approvals/{approval_id}/approve")
async def approve_request(approval_id: str, request: ApproveRequest):
    """Approve an approval request."""
    success = await hitl_service.approve(
        approval_id=approval_id,
        approver_id=request.approver_id,
        comment=request.comment
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Could not approve request")
    
    return {"success": True, "approval_id": approval_id}


@router.post("/approvals/{approval_id}/reject")
async def reject_request(approval_id: str, request: RejectRequest):
    """Reject an approval request."""
    success = await hitl_service.reject(
        approval_id=approval_id,
        rejector_id=request.rejector_id,
        reason=request.reason
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Could not reject request")
    
    return {"success": True, "approval_id": approval_id}


@router.post("/approvals/cleanup")
async def cleanup_expired_approvals():
    """Cleanup expired approval requests."""
    count = await hitl_service.cleanup_expired()
    return {"expired_count": count}
