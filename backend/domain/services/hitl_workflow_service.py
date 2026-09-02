"""
Human-in-the-Loop (HITL) Approval Workflow - Phase 3.2

Allows agents to request human approval for high-impact actions.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Approval request status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalPriority(str, Enum):
    """Approval priority levels."""
    URGENT = "urgent"      # Requires immediate attention
    HIGH = "high"          # Important, respond within hours
    NORMAL = "normal"      # Standard approval
    LOW = "low"            # Can wait


class ApprovalRequest:
    """Represents a human approval request."""
    
    def __init__(
        self,
        action: str,
        description: str,
        agent_name: str,
        context: Dict[str, Any],
        impact_level: str,
        priority: ApprovalPriority,
        approvers: List[str],
        expires_in_hours: int = 24
    ):
        self.id = f"APPROVAL-{uuid.uuid4().hex[:8].upper()}"
        self.action = action
        self.description = description
        self.agent_name = agent_name
        self.context = context
        self.impact_level = impact_level
        self.priority = priority
        self.approvers = approvers
        self.status = ApprovalStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        # Calculate expiration time properly
        from datetime import timedelta
        self.expires_at = self.created_at + timedelta(hours=expires_in_hours)
        self.approved_by: Optional[str] = None
        self.approved_at: Optional[datetime] = None
        self.rejection_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "description": self.description,
            "agent_name": self.agent_name,
            "context": self.context,
            "impact_level": self.impact_level,
            "priority": self.priority.value,
            "approvers": self.approvers,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason
        }


class HITLWorkflowService:
    """
    Service for managing human-in-the-loop approval workflows.
    """
    
    def __init__(self):
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        from domain.services.enhanced_notification_service import EnhancedNotificationService
        self.notification_service = EnhancedNotificationService()
    
    async def request_approval(
        self,
        action: str,
        description: str,
        agent_name: str,
        context: Dict[str, Any],
        impact_level: str,
        priority: ApprovalPriority,
        approvers: List[str]
    ) -> ApprovalRequest:
        """
        Create approval request.
        
        Args:
            action: Action requiring approval (e.g., "merge_pr", "trigger_deployment")
            description: Human-readable description
            agent_name: Name of requesting agent
            context: Additional context for decision
            impact_level: "low", "medium", "high", "critical"
            priority: Approval priority
            approvers: List of user IDs who can approve
        
        Returns:
            ApprovalRequest object
        """
        approval = ApprovalRequest(
            action=action,
            description=description,
            agent_name=agent_name,
            context=context,
            impact_level=impact_level,
            priority=priority,
            approvers=approvers
        )
        
        self.pending_approvals[approval.id] = approval
        
        # Notify approvers
        await self._notify_approvers(approval)
        
        logger.info(f"Created approval request {approval.id} for action: {action}")
        
        return approval
    
    async def approve(
        self,
        approval_id: str,
        approver_id: str,
        comment: Optional[str] = None
    ) -> bool:
        """
        Approve a pending request.
        
        Args:
            approval_id: Approval request ID
            approver_id: User ID of approver
            comment: Optional approval comment
        
        Returns:
            True if approved, False if not found or not authorized
        """
        approval = self.pending_approvals.get(approval_id)
        
        if not approval:
            logger.warning(f"Approval {approval_id} not found")
            return False
        
        if approver_id not in approval.approvers:
            logger.warning(f"User {approver_id} not authorized to approve {approval_id}")
            return False
        
        if approval.status != ApprovalStatus.PENDING:
            logger.warning(f"Approval {approval_id} already {approval.status}")
            return False
        
        # Approve
        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = approver_id
        approval.approved_at = datetime.now(timezone.utc)
        
        # Notify agent that approval granted
        await self._notify_agent_approved(approval)
        
        logger.info(f"Approval {approval_id} approved by {approver_id}")
        
        return True
    
    async def reject(
        self,
        approval_id: str,
        rejector_id: str,
        reason: str
    ) -> bool:
        """
        Reject a pending request.
        
        Args:
            approval_id: Approval request ID
            rejector_id: User ID of rejector
            reason: Rejection reason
        
        Returns:
            True if rejected, False if not found or not authorized
        """
        approval = self.pending_approvals.get(approval_id)
        
        if not approval:
            return False
        
        if rejector_id not in approval.approvers:
            return False
        
        if approval.status != ApprovalStatus.PENDING:
            return False
        
        # Reject
        approval.status = ApprovalStatus.REJECTED
        approval.approved_by = rejector_id  # Record who rejected
        approval.approved_at = datetime.now(timezone.utc)
        approval.rejection_reason = reason
        
        # Notify agent that request rejected
        await self._notify_agent_rejected(approval)
        
        logger.info(f"Approval {approval_id} rejected by {rejector_id}: {reason}")
        
        return True
    
    async def get_pending_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all pending approvals for a user."""
        return [
            approval.to_dict()
            for approval in self.pending_approvals.values()
            if user_id in approval.approvers and approval.status == ApprovalStatus.PENDING
        ]
    
    async def get_approval_status(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get status of approval request."""
        approval = self.pending_approvals.get(approval_id)
        return approval.to_dict() if approval else None
    
    async def cleanup_expired(self) -> int:
        """
        Mark expired approvals as expired.
        
        Returns:
            Number of approvals expired
        """
        now = datetime.now(timezone.utc)
        expired_count = 0
        
        for approval in self.pending_approvals.values():
            if approval.status == ApprovalStatus.PENDING and now > approval.expires_at:
                approval.status = ApprovalStatus.EXPIRED
                expired_count += 1
                logger.info(f"Approval {approval.id} expired")
        
        return expired_count
    
    async def _notify_approvers(self, approval: ApprovalRequest):
        """Notify approvers about new approval request."""
        for approver_id in approval.approvers:
            await self.notification_service.notify(
                user_id=approver_id,
                notification_type="approval_request",
                title=f"🔔 Approval Required: {approval.action}",
                body=f"{approval.agent_name} requests approval\n\n{approval.description}\n\nImpact: {approval.impact_level}",
                link=f"/approvals/{approval.id}"
            )
    
    async def _notify_agent_approved(self, approval: ApprovalRequest):
        """Notify that approval was granted."""
        # TODO: Implement agent notification mechanism
        logger.info(f"Agent {approval.agent_name} notified of approval {approval.id}")
    
    async def _notify_agent_rejected(self, approval: ApprovalRequest):
        """Notify that approval was rejected."""
        # TODO: Implement agent notification mechanism
        logger.info(f"Agent {approval.agent_name} notified of rejection {approval.id}")


# Global workflow service instance
hitl_service = HITLWorkflowService()
