"""
Transfer Management API Routes
Organizational transfer workflow.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from repositories.transfer_repository import TransferRepository
from services.transfer_service import TransferService
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.audit import log_audit, AuditAction
from domain.models.transfer import (
    Transfer,
    TransferCreate,
    TransferApproval,
    TransferFlag
)

router = APIRouter()


@router.post("/", response_model=Transfer, status_code=201)
async def create_transfer(
    transfer: TransferCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create a new transfer request.

    **Required Permission:** REQUEST_TRANSFER (all employees)

    Workflow determination:
    - Manager-initiated (LEAD/PM/CEO): Goes directly to receiving manager
    - Employee-initiated: Starts with HR validation
    - Grievance: HR validation → Skip current manager → Receiving manager
    """
    # All employees can request transfers
    service = TransferService()

    try:
        created_transfer = await service.create_transfer(transfer, user)

        # Audit log
        await log_audit(
            action=AuditAction.TRANSFER_CREATED,
            actor=user,
            resource_type="transfer",
            resource_id=created_transfer.id,
            details={
                "employee_id": transfer.employee_id,
                "requested_team_id": transfer.requested_team_id,
                "workflow_type": created_transfer.workflow_type,
                "reason": transfer.reason
            }
        )

        return created_transfer

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[Transfer])
async def list_transfers(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    employee_id: Optional[str] = Query(None, description="Filter by employee"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """
    List transfer requests.

    **Access Control:**
    - HR: See all transfers
    - PM/CEO: See all transfers
    - LEAD: See transfers for their team members
    - Others: See only their own transfers
    """
    repo = TransferRepository()
    role = user.get("role", "").upper()
    current_user_id = user["employee_id"]

    # Build query based on role
    if role in ("HR", "PM", "CEO"):
        # Full access
        if status:
            result = await repo.find_by_status(status, limit=limit, skip=skip)
            transfers = result["data"]
        elif employee_id:
            transfers = await repo.find_by_employee_id(employee_id)
        else:
            result = await repo.find_many({}, limit=limit, skip=skip, sort_field="created_at", sort_dir=-1)
            transfers = result["data"]

    elif role == "LEAD":
        # See transfers for team members and own transfers
        # For simplicity, show transfers where they're current or receiving manager, or their own
        transfers = await repo.find_all({
            "$or": [
                {"employee_id": current_user_id},
                {"current_manager_id": current_user_id},
                {"receiving_manager_id": current_user_id}
            ]
        })

    else:
        # Only see own transfers
        transfers = await repo.find_by_employee_id(current_user_id)

    return [Transfer(**t) for t in transfers]


@router.get("/{transfer_id}", response_model=Transfer)
async def get_transfer(
    transfer_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get transfer details.

    **Access Control:**
    - HR/PM/CEO: See all
    - LEAD: See if they're involved (current/receiving manager)
    - Others: See only their own
    """
    repo = TransferRepository()
    transfer = await repo.find_by_id(transfer_id)

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    # Check access
    role = user.get("role", "").upper()
    current_user_id = user["employee_id"]

    has_access = (
        role in ("HR", "PM", "CEO")
        or transfer["employee_id"] == current_user_id
        or transfer["current_manager_id"] == current_user_id
        or transfer["receiving_manager_id"] == current_user_id
        or transfer["initiated_by_id"] == current_user_id
    )

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    return Transfer(**transfer)


@router.patch("/{transfer_id}/approve", response_model=Transfer)
async def approve_transfer(
    transfer_id: str,
    approval: TransferApproval,
    user: dict = Depends(get_current_user)
):
    """
    Approve transfer at current stage.

    **Authorization:**
    - HR: Approve at HR validation and HR review stages
    - Current Manager: Approve release
    - Receiving Manager: Approve acceptance
    - PM/CEO: Approve management stage
    """
    service = TransferService()

    try:
        updated_transfer = await service.approve_transfer(
            transfer_id,
            user,
            approval.comments
        )

        # Audit log
        await log_audit(
            action=AuditAction.TRANSFER_APPROVED,
            actor=user,
            resource_type="transfer",
            resource_id=transfer_id,
            details={
                "stage": updated_transfer.status,
                "comments": approval.comments
            }
        )

        return updated_transfer

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{transfer_id}/reject", response_model=Transfer)
async def reject_transfer(
    transfer_id: str,
    approval: TransferApproval,
    user: dict = Depends(get_current_user)
):
    """
    Reject transfer.

    **Authorization:**
    - HR: Reject at HR stages
    - Current Manager: Reject release
    - Receiving Manager: Reject acceptance
    - PM/CEO: Reject at management stage
    """
    service = TransferService()

    try:
        updated_transfer = await service.reject_transfer(
            transfer_id,
            user,
            approval.comments
        )

        # Audit log
        await log_audit(
            action=AuditAction.TRANSFER_REJECTED,
            actor=user,
            resource_type="transfer",
            resource_id=transfer_id,
            details={
                "stage": updated_transfer.status,
                "comments": approval.comments
            }
        )

        return updated_transfer

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{transfer_id}/flag", response_model=Transfer)
async def flag_transfer(
    transfer_id: str,
    flag_data: TransferFlag,
    user: dict = Depends(require_permission(Permission.REVIEW_TRANSFER_REQUEST))
):
    """
    HR flags an issue with the transfer.

    **Required Permission:** REVIEW_TRANSFER_REQUEST (HR only)
    """
    service = TransferService()

    try:
        updated_transfer = await service.flag_transfer(
            transfer_id,
            user,
            flag_data.flag,
            flag_data.comments
        )

        # Audit log
        await log_audit(
            action=AuditAction.TRANSFER_FLAGGED,
            actor=user,
            resource_type="transfer",
            resource_id=transfer_id,
            details={
                "flag": flag_data.flag,
                "comments": flag_data.comments
            }
        )

        return updated_transfer

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{transfer_id}/execute", response_model=Transfer)
async def execute_transfer(
    transfer_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Execute approved transfer (update team membership).

    **Required Permission:** EXECUTE_TRANSFER (CEO or authorized technical authority)

    This operation updates:
    1. Employment records (HR concern - updated via UPDATE_EMPLOYMENT_RECORDS)
    2. Team membership (Engineering/organizational concern - requires EXECUTE_TRANSFER)
    
    **Note:** PM manages project-level resources, not permanent organizational team membership.
    """
    from core.permissions import get_user_permissions
    
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    
    if Permission.EXECUTE_TRANSFER not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only CEO or authorized technical authority can execute organizational transfers."
        )

    service = TransferService()

    try:
        updated_transfer = await service.execute_transfer(transfer_id, user)

        # Audit log
        await log_audit(
            action=AuditAction.TRANSFER_EXECUTED,
            actor=user,
            resource_type="transfer",
            resource_id=transfer_id,
            details={
                "employee_id": updated_transfer.employee_id,
                "from_team_id": updated_transfer.current_team_id,
                "to_team_id": updated_transfer.requested_team_id
            }
        )

        return updated_transfer

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
