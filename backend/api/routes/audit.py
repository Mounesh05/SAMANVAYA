"""
Audit Log API
Provides access to audit logs with role-based filtering.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta

from core.audit import audit_logger, AuditAction
from core.dependencies import get_current_user
from core.permissions import get_user_permissions, Permission, OrganizationalRole


router = APIRouter()


# HR-relevant audit actions that HR users are allowed to see
HR_AUDIT_ACTIONS = {
    # Employee lifecycle
    AuditAction.USER_CREATED,
    AuditAction.USER_UPDATED,
    AuditAction.USER_DELETED,
    AuditAction.USER_ACTIVATED,
    AuditAction.USER_DEACTIVATED,
    
    # Team management (organizational structure)
    AuditAction.TEAM_CREATED,
    AuditAction.TEAM_UPDATED,
    AuditAction.TEAM_MEMBER_ADDED,
    AuditAction.TEAM_MEMBER_REMOVED,
    AuditAction.TEAM_LEAD_ASSIGNED,

    # Transfers (HR reviews and executes them)
    AuditAction.TRANSFER_CREATED,
    AuditAction.TRANSFER_APPROVED,
    AuditAction.TRANSFER_REJECTED,
    AuditAction.TRANSFER_FLAGGED,
    AuditAction.TRANSFER_EXECUTED,

    # Performance management (outcomes only, not raw evaluations)
    AuditAction.FEEDBACK_SUBMITTED,
}

# Actions that should NEVER be visible to HR (engineering/security/system)
RESTRICTED_AUDIT_ACTIONS = {
    AuditAction.ADMIN_GRANTED,
    AuditAction.ADMIN_REVOKED,
    AuditAction.SETTINGS_CHANGED,
    AuditAction.INTEGRATION_ADDED,
    AuditAction.INTEGRATION_REMOVED,
    AuditAction.EVALUATION_TRIGGERED,
    AuditAction.BULK_EVALUATION_TRIGGERED,
    AuditAction.CREDIT_APPEALED,
    AuditAction.SENSITIVE_DATA_ACCESSED,
    AuditAction.EXPORT_DATA,
}


@router.get("/logs")
async def get_audit_logs(
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get audit logs with role-based filtering.
    
    HR users see only HR-relevant events (employee lifecycle, team structure).
    Engineering/Management users see all events based on their permissions.
    """
    # Check permission
    user_permissions = get_user_permissions(
        OrganizationalRole(current_user.get('role', 'DEVELOPER')),
        current_user.get('is_admin', False),
        current_user.get('designation')
    )
    
    if Permission.VIEW_AUDIT_LOGS not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view audit logs"
        )
    
    # Parse action filter if provided
    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    # Fetch logs from audit system
    logs = await audit_logger.get_logs(
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action_enum,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    # Apply domain-based filtering for HR users
    user_role = current_user.get('role', 'DEVELOPER').upper()
    if user_role == 'HR':
        # HR users see ONLY HR-relevant events
        filtered_logs = []
        for log in logs:
            log_action = log.get('action')
            try:
                log_action_enum = AuditAction(log_action)
                if log_action_enum in HR_AUDIT_ACTIONS:
                    filtered_logs.append(log)
            except (ValueError, KeyError):
                # Skip malformed log entries
                continue
        
        return {
            "total": len(filtered_logs),
            "logs": filtered_logs,
            "filtered_for_role": "HR",
            "allowed_actions": [action.value for action in HR_AUDIT_ACTIONS]
        }
    
    # Non-HR users see all logs (based on their VIEW_AUDIT_LOGS permission)
    return {
        "total": len(logs),
        "logs": logs,
        "filtered_for_role": user_role
    }


@router.get("/logs/user/{user_id}/activity")
async def get_user_activity_summary(
    user_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get activity summary for a specific user.
    
    HR can see activity for HR-relevant actions only.
    Management/Engineering can see full activity based on permissions.
    """
    # Check permission
    user_permissions = get_user_permissions(
        OrganizationalRole(current_user.get('role', 'DEVELOPER')),
        current_user.get('is_admin', False),
        current_user.get('designation')
    )
    
    if Permission.VIEW_AUDIT_LOGS not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view audit logs"
        )
    
    # Get activity summary
    activity = await audit_logger.get_user_activity(actor_id=user_id, days=days)
    
    # Apply HR filtering if necessary
    user_role = current_user.get('role', 'DEVELOPER').upper()
    if user_role == 'HR':
        # Filter action counts to HR-relevant actions only
        filtered_counts = {}
        hr_action_values = {action.value for action in HR_AUDIT_ACTIONS}
        
        for action, count in activity.get('action_counts', {}).items():
            if action in hr_action_values:
                filtered_counts[action] = count
        
        # Filter recent actions
        filtered_recent = []
        for log in activity.get('recent_actions', []):
            log_action = log.get('action')
            if log_action in hr_action_values:
                filtered_recent.append(log)
        
        return {
            "actor_id": user_id,
            "period_days": days,
            "total_actions": sum(filtered_counts.values()),
            "action_counts": filtered_counts,
            "recent_actions": filtered_recent[:10],
            "filtered_for_role": "HR"
        }
    
    return activity


@router.get("/logs/resource/{resource_type}/{resource_id}")
async def get_resource_history(
    resource_type: str,
    resource_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """
    Get complete history of changes to a specific resource.
    
    HR users see only HR-relevant changes (e.g., employee updates, team membership).
    """
    # Check permission
    user_permissions = get_user_permissions(
        OrganizationalRole(current_user.get('role', 'DEVELOPER')),
        current_user.get('is_admin', False),
        current_user.get('designation')
    )
    
    if Permission.VIEW_AUDIT_LOGS not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view audit logs"
        )
    
    # Get resource history
    history = await audit_logger.get_resource_history(
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit
    )
    
    # Apply HR filtering
    user_role = current_user.get('role', 'DEVELOPER').upper()
    if user_role == 'HR':
        filtered_history = []
        for log in history:
            log_action = log.get('action')
            try:
                log_action_enum = AuditAction(log_action)
                if log_action_enum in HR_AUDIT_ACTIONS:
                    filtered_history.append(log)
            except (ValueError, KeyError):
                continue
        
        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "total_events": len(filtered_history),
            "history": filtered_history,
            "filtered_for_role": "HR"
        }
    
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "total_events": len(history),
        "history": history
    }
