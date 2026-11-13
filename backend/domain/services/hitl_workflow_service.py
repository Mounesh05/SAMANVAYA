"""
Human-in-the-Loop (HITL) Approval Workflow - Phase 3.2

Allows agents to request human approval for high-impact actions.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid
import logging
from core.database import col

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
        expires_in_hours: int = 24,
        requested_by: Optional[str] = None,
        kind: Optional[str] = None,
        change: Optional[Dict[str, Any]] = None,
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
        # CR-010: who asked (can never approve), and for typed requests the
        # exact change that is applied on approval.
        self.requested_by = requested_by
        self.kind = kind
        self.change = change
    
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
            "rejection_reason": self.rejection_reason,
            "requested_by": self.requested_by,
            "kind": self.kind,
            "change": self.change,
        }


class HITLWorkflowService:
    """
    Service for managing human-in-the-loop approval workflows.
    """
    
    def __init__(self):
        self.collection = col("approvals")
        from domain.services.enhanced_notification_service import EnhancedNotificationService
        self.notification_service = EnhancedNotificationService()
    
    async def _ensure_indexes(self):
        """Ensure MongoDB indexes are created."""
        await self.collection.create_index([("id", 1)], unique=True)
        await self.collection.create_index([("status", 1), ("approvers", 1)])
    
    async def request_approval(
        self,
        action: str,
        description: str,
        agent_name: str,
        context: Dict[str, Any],
        impact_level: str,
        priority: ApprovalPriority,
        approvers: List[str],
        requested_by: Optional[str] = None,
        kind: Optional[str] = None,
        change: Optional[Dict[str, Any]] = None,
        expires_in_hours: int = 24,
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
        # CR-010: the requester can never be an approver, and a request needs
        # at least one other approver.
        eligible = list(dict.fromkeys(a for a in approvers if a and a != requested_by))
        if not eligible:
            raise ValueError("An approval request needs at least one approver other than the requester")
        approval = ApprovalRequest(
            action=action,
            description=description,
            agent_name=agent_name,
            context=context,
            impact_level=impact_level,
            priority=priority,
            approvers=eligible,
            expires_in_hours=expires_in_hours,
            requested_by=requested_by,
            kind=kind,
            change=change,
        )
        
        await self.collection.insert_one(approval.to_dict())
        
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
        approval_doc = await self.claim(approval_id, approver_id, comment)
        if not approval_doc:
            logger.warning(f"Approval {approval_id} not found or user {approver_id} not authorized")
            return False
        
        # Notify agent that approval granted
        approval = ApprovalRequest(
            action=approval_doc["action"],
            description=approval_doc["description"],
            agent_name=approval_doc["agent_name"],
            context=approval_doc["context"],
            impact_level=approval_doc["impact_level"],
            priority=ApprovalPriority(approval_doc["priority"]),
            approvers=approval_doc["approvers"]
        )
        approval.id = approval_doc["id"]
        approval.status = ApprovalStatus.APPROVED
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
        approval_doc = await self.collection.find_one_and_update(
            self._actionable(approval_id, rejector_id),
            {
                "$set": {
                    "status": ApprovalStatus.REJECTED.value,
                    "approved_by": rejector_id,
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                    "rejection_reason": reason
                }
            }
        )
        
        if not approval_doc:
            return False
        
        # Notify agent that request rejected
        approval = ApprovalRequest(
            action=approval_doc["action"],
            description=approval_doc["description"],
            agent_name=approval_doc["agent_name"],
            context=approval_doc["context"],
            impact_level=approval_doc["impact_level"],
            priority=ApprovalPriority(approval_doc["priority"]),
            approvers=approval_doc["approvers"]
        )
        approval.id = approval_doc["id"]
        approval.status = ApprovalStatus.REJECTED
        approval.rejection_reason = reason
        await self._notify_agent_rejected(approval)
        
        logger.info(f"Approval {approval_id} rejected by {rejector_id}: {reason}")
        
        return True
    
    @staticmethod
    def _actionable(approval_id: str, user_id: str) -> Dict[str, Any]:
        """CR-010: a pending, unexpired request that names this user as an
        approver and that this user did not raise."""
        return {
            "id": approval_id,
            "approvers": user_id,
            "status": ApprovalStatus.PENDING.value,
            "requested_by": {"$ne": user_id},
            "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()},
        }

    async def claim(self, approval_id: str, approver_id: str, comment: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Atomically mark a request approved; returns it, or None if it can't be."""
        changes = {
            "status": ApprovalStatus.APPROVED.value,
            "approved_by": approver_id,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approval_comment": comment,
        }
        # Take the document as it was and merge the change, rather than asking
        # for the updated one (works the same on MongoDB and in-memory mocks).
        before = await self.collection.find_one_and_update(
            self._actionable(approval_id, approver_id), {"$set": changes}, projection={"_id": 0})
        return {**before, **changes} if before else None

    async def mark_failed(self, approval_id: str, reason: str) -> None:
        """CR-010: an approved change that could not be applied (rules re-checked)."""
        await self.collection.update_one({"id": approval_id}, {"$set": {"status": "failed", "failure_reason": reason}})

    async def get_requested_by(self, user_id: str) -> List[Dict[str, Any]]:
        """Pending requests raised by this user."""
        cursor = self.collection.find({"requested_by": user_id, "status": "pending"}, {"_id": 0})
        return await cursor.to_list(length=None)

    async def get_pending_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all pending approvals for a user."""
        cursor = self.collection.find(
            {"approvers": user_id, "status": "pending", "requested_by": {"$ne": user_id},
             "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}},
            {"_id": 0}
        )
        return await cursor.to_list(length=None)
    
    async def get_approval_status(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get status of approval request."""
        return await self.collection.find_one({"id": approval_id}, {"_id": 0})
    
    async def cleanup_expired(self) -> int:
        """
        Mark expired approvals as expired.
        
        Returns:
            Number of approvals expired
        """
        now = datetime.now(timezone.utc).isoformat()
        
        result = await self.collection.update_many(
            {
                "status": ApprovalStatus.PENDING.value,
                "expires_at": {"$lt": now}
            },
            {"$set": {"status": ApprovalStatus.EXPIRED.value}}
        )
        
        expired_count = result.modified_count
        if expired_count > 0:
            logger.info(f"Expired {expired_count} approvals")
        
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
