from fastapi import APIRouter, Depends

from core.dependencies import require_permission
from core.permissions import Permission
from domain.services.release_decision_service import DecisionRequest, record_decision
from domain.services.task_delivery_service import build_delivery_status

router = APIRouter()


@router.post("/{task_id}/release-decisions")
async def decide_release(
    task_id: str,
    request: DecisionRequest,
    user: dict = Depends(require_permission(Permission.SIGN_OFF_WORK, Permission.RECORD_RELEASE_DECISION)),
):
    """Record a review of current project evidence. Deployment remains a separate operation."""
    status = await build_delivery_status(task_id, user)
    return await record_decision(status, user, request)
