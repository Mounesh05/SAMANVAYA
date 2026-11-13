"""
Transfer service - orchestrates organizational transfer workflow.

Workflow types:
1. Manager-initiated: Current manager → Receiving manager → Management → HR review
2. Employee-initiated: HR validation → Current manager → Receiving manager → Management → HR review
3. Grievance bypass: HR validation → Receiving manager → Management → HR review (skips current manager)
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import secrets
from repositories.transfer_repository import TransferRepository
from repositories.user_repository import UserRepository
from domain.models.transfer import (
    TransferStatus,
    WorkflowType,
    Approval,
    Transfer,
    TransferCreate
)


class TransferService:
    """Service for managing organizational transfers."""

    def __init__(self):
        self.transfer_repo = TransferRepository()
        self.user_repo = UserRepository()

    async def create_transfer(
        self,
        transfer_data: TransferCreate,
        initiator: dict
    ) -> Transfer:
        """
        Create a new transfer request.

        Args:
            transfer_data: Transfer request data
            initiator: User creating the transfer

        Returns:
            Created transfer

        Raises:
            ValueError: If validation fails
        """
        # Fetch employee details
        employee = await self.user_repo.find_by_employee_id(transfer_data.employee_id)
        if not employee:
            raise ValueError("Employee not found")

        if not employee.get("is_active", False):
            raise ValueError("Cannot transfer inactive employee")

        # Check for concurrent transfers
        active_transfers = await self.transfer_repo.find_active_transfers_for_employee(
            transfer_data.employee_id
        )
        if active_transfers:
            raise ValueError(
                f"Employee already has an active transfer request (ID: {active_transfers[0]['id']})"
            )

        # Determine workflow type and initial status
        initiator_role = initiator.get("role", "").upper()
        is_manager_initiated = initiator_role in ("LEAD", "PM", "CEO")
        is_grievance = transfer_data.reason == "grievance_current_manager"

        if is_grievance:
            workflow_type = WorkflowType.GRIEVANCE_BYPASS
            initial_status = TransferStatus.PENDING_HR_VALIDATION
        elif is_manager_initiated:
            workflow_type = WorkflowType.MANAGER_INITIATED
            initial_status = TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE
        else:
            workflow_type = WorkflowType.EMPLOYEE_INITIATED
            initial_status = TransferStatus.PENDING_HR_VALIDATION

        # Get current manager (team lead)
        current_manager_id = None
        current_manager_name = None
        if employee.get("team_id"):
            # Find team lead for current team
            team_members = await self.user_repo.find_by_team(employee["team_id"])
            for member in team_members:
                if member.get("role", "").upper() == "LEAD":
                    current_manager_id = member["employee_id"]
                    current_manager_name = member["name"]
                    break

        # Get receiving manager (team lead of requested team)
        receiving_manager_id = None
        receiving_manager_name = None
        if transfer_data.requested_team_id:
            team_members = await self.user_repo.find_by_team(transfer_data.requested_team_id)
            for member in team_members:
                if member.get("role", "").upper() == "LEAD":
                    receiving_manager_id = member["employee_id"]
                    receiving_manager_name = member["name"]
                    break

        now = datetime.now(timezone.utc).isoformat()
        transfer_id = f"TRF-{secrets.token_hex(8).upper()}"

        transfer_doc = {
            "id": transfer_id,
            "employee_id": transfer_data.employee_id,
            "employee_name": employee["name"],
            "initiated_by": initiator["name"],
            "initiated_by_id": initiator["employee_id"],
            "current_team_id": employee.get("team_id"),
            "requested_team_id": transfer_data.requested_team_id,
            "current_manager_id": current_manager_id,
            "receiving_manager_id": receiving_manager_id,
            "reason": transfer_data.reason,
            "justification": transfer_data.justification,
            "status": initial_status.value,
            "workflow_type": workflow_type.value,
            "approvals": [],
            "hr_flags": [],
            "created_at": now,
            "updated_at": now,
            "effective_date": transfer_data.effective_date
        }

        await self.transfer_repo.insert(transfer_doc)

        return Transfer(**transfer_doc)

    async def approve_transfer(
        self,
        transfer_id: str,
        approver: dict,
        comments: Optional[str] = None
    ) -> Transfer:
        """
        Approve transfer at current stage.

        Args:
            transfer_id: Transfer ID
            approver: User approving the transfer
            comments: Optional approval comments

        Returns:
            Updated transfer

        Raises:
            ValueError: If approval is invalid
        """
        transfer = await self.transfer_repo.find_by_id(transfer_id)
        if not transfer:
            raise ValueError("Transfer not found")

        current_status = transfer["status"]
        approver_role = approver.get("role", "").upper()
        approver_id = approver["employee_id"]

        # Verify approver is authorized for current stage
        if not self._can_approve_at_stage(transfer, current_status, approver_id, approver_role, approver):
            raise ValueError(f"You are not authorized to approve at stage: {current_status}")

        # Record approval
        approval = Approval(
            stage=current_status,
            approver_id=approver_id,
            approver_name=approver["name"],
            approver_role=approver_role,
            decision="approved",
            comments=comments,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        await self.transfer_repo.add_approval(transfer_id, approval.model_dump())

        # Advance to next stage
        next_status = self._get_next_status(transfer, current_status)
        now = datetime.now(timezone.utc).isoformat()
        await self.transfer_repo.update_status(transfer_id, next_status.value, now)

        # Fetch updated transfer
        updated_transfer = await self.transfer_repo.find_by_id(transfer_id)
        return Transfer(**updated_transfer)

    async def reject_transfer(
        self,
        transfer_id: str,
        rejector: dict,
        comments: Optional[str] = None
    ) -> Transfer:
        """
        Reject transfer.

        Args:
            transfer_id: Transfer ID
            rejector: User rejecting the transfer
            comments: Rejection reason

        Returns:
            Updated transfer
        """
        transfer = await self.transfer_repo.find_by_id(transfer_id)
        if not transfer:
            raise ValueError("Transfer not found")

        current_status = transfer["status"]
        rejector_role = rejector.get("role", "").upper()
        rejector_id = rejector["employee_id"]

        # Verify rejector is authorized
        if not self._can_approve_at_stage(transfer, current_status, rejector_id, rejector_role, rejector):
            raise ValueError(f"You are not authorized to reject at stage: {current_status}")

        # Record rejection
        approval = Approval(
            stage=current_status,
            approver_id=rejector_id,
            approver_name=rejector["name"],
            approver_role=rejector_role,
            decision="rejected",
            comments=comments,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        await self.transfer_repo.add_approval(transfer_id, approval.model_dump())

        # Update status to rejected
        now = datetime.now(timezone.utc).isoformat()
        await self.transfer_repo.update_status(transfer_id, TransferStatus.REJECTED.value, now)

        updated_transfer = await self.transfer_repo.find_by_id(transfer_id)
        return Transfer(**updated_transfer)

    async def flag_transfer(
        self,
        transfer_id: str,
        hr_user: dict,
        flag: str,
        comments: Optional[str] = None
    ) -> Transfer:
        """
        HR flags an issue with the transfer.

        Args:
            transfer_id: Transfer ID
            hr_user: HR user flagging the issue
            flag: Flag description
            comments: Additional comments

        Returns:
            Updated transfer
        """
        transfer = await self.transfer_repo.find_by_id(transfer_id)
        if not transfer:
            raise ValueError("Transfer not found")

        # Add flag
        flag_entry = f"{flag} (by {hr_user['name']} at {datetime.now(timezone.utc).isoformat()})"
        if comments:
            flag_entry += f": {comments}"

        await self.transfer_repo.add_hr_flag(transfer_id, flag_entry)

        updated_transfer = await self.transfer_repo.find_by_id(transfer_id)
        return Transfer(**updated_transfer)

    async def execute_transfer(
        self,
        transfer_id: str,
        executor: dict
    ) -> Transfer:
        """
        Execute approved transfer (update team membership).

        This operation:
        1. Updates employment records (HR records)
        2. Updates team membership (Engineering records)

        Only CEO or authorized technical authority can execute organizational transfers.
        PM manages project-level resource assignment, not permanent team membership.

        Args:
            transfer_id: Transfer ID
            executor: CEO or authorized technical authority executing the transfer

        Returns:
            Updated transfer

        Raises:
            ValueError: If transfer is not approved or executor lacks permission
        """
        transfer = await self.transfer_repo.find_by_id(transfer_id)
        if not transfer:
            raise ValueError("Transfer not found")

        if transfer["status"] != TransferStatus.APPROVED.value:
            raise ValueError(f"Cannot execute transfer in status: {transfer['status']}")

        # Verify executor has EXECUTE_TRANSFER permission
        # API layer should enforce this, but service layer validates as defense-in-depth
        from core.permissions import Permission, get_user_permissions
        
        executor_permissions = get_user_permissions(
            executor.get("role", "").upper(),
            executor.get("is_admin", False),
            executor.get("designation")
        )
        
        if Permission.EXECUTE_TRANSFER not in executor_permissions:
            raise ValueError("Insufficient permissions to execute transfer. Only CEO or authorized technical authority can execute organizational transfers.")

        # Update employee's team
        employee = await self.user_repo.find_by_employee_id(transfer["employee_id"])
        if not employee:
            raise ValueError("Employee not found")

        await self.user_repo.update(
            {"employee_id": transfer["employee_id"]},
            {"team_id": transfer["requested_team_id"]}
        )

        # Mark transfer as effective
        now = datetime.now(timezone.utc).isoformat()
        await self.transfer_repo.update_status(transfer_id, TransferStatus.EFFECTIVE.value, now)

        # Record execution as approval
        approval = Approval(
            stage="execution",
            approver_id=executor["employee_id"],
            approver_name=executor["name"],
            approver_role=executor.get("role", "").upper(),
            decision="executed",
            comments="Transfer executed - team membership updated",
            timestamp=now
        )
        await self.transfer_repo.add_approval(transfer_id, approval.model_dump())

        updated_transfer = await self.transfer_repo.find_by_id(transfer_id)
        return Transfer(**updated_transfer)

    def _can_approve_at_stage(
        self,
        transfer: dict,
        stage: str,
        approver_id: str,
        approver_role: str,
        approver: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if user can approve at current stage.

        CR-006: HR and management stages are permission-based (they checked
        role names). Manager stages stay tied to the named manager.
        """
        from core.permissions import Permission, get_user_permissions
        permissions = get_user_permissions(
            approver_role,
            bool((approver or {}).get("is_admin", False)),
            (approver or {}).get("designation"),
        )
        hr_reviewer = bool(permissions & {Permission.REVIEW_TRANSFER_HR, Permission.REVIEW_TRANSFER_REQUEST})

        if stage == TransferStatus.PENDING_HR_VALIDATION.value:
            return hr_reviewer

        if stage == TransferStatus.PENDING_CURRENT_MANAGER_RELEASE.value:
            return approver_id == transfer.get("current_manager_id")

        if stage == TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE.value:
            return approver_id == transfer.get("receiving_manager_id")

        if stage == TransferStatus.PENDING_MANAGEMENT_APPROVAL.value:
            return Permission.APPROVE_TRANSFER_AS_MANAGEMENT in permissions

        if stage == TransferStatus.PENDING_HR_REVIEW.value:
            return hr_reviewer

        return False

    def _get_next_status(self, transfer: dict, current_status: str) -> TransferStatus:
        """Determine next status after approval."""
        workflow_type = transfer["workflow_type"]

        if current_status == TransferStatus.PENDING_HR_VALIDATION.value:
            # After HR validation
            if workflow_type == WorkflowType.GRIEVANCE_BYPASS.value:
                # Skip current manager for grievances
                return TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE
            else:
                return TransferStatus.PENDING_CURRENT_MANAGER_RELEASE

        if current_status == TransferStatus.PENDING_CURRENT_MANAGER_RELEASE.value:
            return TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE

        if current_status == TransferStatus.PENDING_RECEIVING_MANAGER_ACCEPTANCE.value:
            return TransferStatus.PENDING_MANAGEMENT_APPROVAL

        if current_status == TransferStatus.PENDING_MANAGEMENT_APPROVAL.value:
            return TransferStatus.PENDING_HR_REVIEW

        if current_status == TransferStatus.PENDING_HR_REVIEW.value:
            return TransferStatus.APPROVED

        # Default to approved (shouldn't reach here)
        return TransferStatus.APPROVED
