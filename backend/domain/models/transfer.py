"""
Organizational Transfer domain models.
Represents employee transfer requests and workflow state.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TransferStatus(str, Enum):
    """Transfer workflow states."""
    SUBMITTED = "submitted"
    PENDING_HR_VALIDATION = "pending_hr_validation"
    PENDING_CURRENT_MANAGER_RELEASE = "pending_current_manager_release"
    PENDING_RECEIVING_MANAGER_ACCEPTANCE = "pending_receiving_manager_acceptance"
    PENDING_MANAGEMENT_APPROVAL = "pending_management_approval"
    PENDING_HR_REVIEW = "pending_hr_review"
    RETURNED_FOR_CORRECTION = "returned_for_correction"
    APPROVED = "approved"
    EFFECTIVE = "effective"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class WorkflowType(str, Enum):
    """Transfer workflow types."""
    MANAGER_INITIATED = "manager_initiated"
    EMPLOYEE_INITIATED = "employee_initiated"
    GRIEVANCE_BYPASS = "grievance_bypass"


class Approval(BaseModel):
    """Single approval in the workflow."""
    stage: str
    approver_id: str
    approver_name: str
    approver_role: str
    decision: str  # approved, rejected, flagged
    comments: Optional[str] = None
    timestamp: str


class TransferCreate(BaseModel):
    """Request model for creating a transfer."""
    employee_id: str
    requested_team_id: str
    reason: str
    justification: str
    effective_date: Optional[str] = None


class Transfer(BaseModel):
    """Complete transfer request."""
    id: str
    employee_id: str
    employee_name: str
    initiated_by: str
    initiated_by_id: str
    current_team_id: Optional[str] = None
    requested_team_id: str
    current_manager_id: Optional[str] = None
    receiving_manager_id: Optional[str] = None
    reason: str
    justification: str
    status: TransferStatus
    workflow_type: WorkflowType
    approvals: List[Approval] = []
    hr_flags: List[str] = []
    created_at: str
    updated_at: str
    effective_date: Optional[str] = None


class TransferApproval(BaseModel):
    """Request model for approving/rejecting a transfer."""
    comments: Optional[str] = None


class TransferFlag(BaseModel):
    """Request model for HR flagging issues."""
    flag: str
    comments: Optional[str] = None
