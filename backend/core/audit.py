"""
Audit Logging System
Tracks all sensitive operations for compliance and security.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from core.database import col


class AuditAction(str, Enum):
    """Types of auditable actions."""
    
    # Authentication
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    
    # User management
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    USER_ACTIVATED = "USER_ACTIVATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    ADMIN_GRANTED = "ADMIN_GRANTED"
    ADMIN_REVOKED = "ADMIN_REVOKED"
    
    # Team management
    TEAM_CREATED = "TEAM_CREATED"
    TEAM_UPDATED = "TEAM_UPDATED"
    TEAM_MEMBER_ADDED = "TEAM_MEMBER_ADDED"
    TEAM_MEMBER_REMOVED = "TEAM_MEMBER_REMOVED"
    TEAM_LEAD_ASSIGNED = "TEAM_LEAD_ASSIGNED"
    
    # Performance evaluations
    EVALUATION_TRIGGERED = "EVALUATION_TRIGGERED"
    BULK_EVALUATION_TRIGGERED = "BULK_EVALUATION_TRIGGERED"
    FEEDBACK_SUBMITTED = "FEEDBACK_SUBMITTED"
    
    # Data access
    SENSITIVE_DATA_ACCESSED = "SENSITIVE_DATA_ACCESSED"
    EXPORT_DATA = "EXPORT_DATA"
    
    # Settings
    SETTINGS_CHANGED = "SETTINGS_CHANGED"
    INTEGRATION_ADDED = "INTEGRATION_ADDED"
    INTEGRATION_REMOVED = "INTEGRATION_REMOVED"


class AuditLogger:
    """Service for logging audit events."""
    
    def __init__(self):
        self.collection = col("audit_logs")
    
    async def log(
        self,
        action: AuditAction,
        actor_id: str,
        actor_name: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        Log an audit event.
        
        Args:
            action: Type of action performed
            actor_id: ID of user who performed the action
            actor_name: Name of user who performed the action
            resource_type: Type of resource affected (user, team, evaluation, etc.)
            resource_id: ID of the affected resource
            details: Additional context (before/after values, parameters, etc.)
            ip_address: IP address of the request
            user_agent: User agent string
            success: Whether the action succeeded
            error_message: Error message if action failed
        """
        try:
            audit_log = {
                "action": action.value,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details or {},
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "error_message": error_message,
                "timestamp": datetime.utcnow().isoformat(),
                "date": datetime.utcnow().strftime("%Y-%m-%d"),  # For easier querying
            }
            
            await self.collection.insert_one(audit_log)
            
        except Exception as e:
            # Audit logging should never break the main flow
            # Just log to console if it fails
            print(f"Audit logging failed: {str(e)}")
    
    async def get_logs(
        self,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """
        Query audit logs with filters.
        
        Args:
            actor_id: Filter by actor
            resource_type: Filter by resource type
            resource_id: Filter by specific resource
            action: Filter by action type
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum results to return
        
        Returns:
            List of audit log entries
        """
        query = {}
        
        if actor_id:
            query["actor_id"] = actor_id
        if resource_type:
            query["resource_type"] = resource_type
        if resource_id:
            query["resource_id"] = resource_id
        if action:
            query["action"] = action.value
        
        # Date range query
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["date"] = date_query
        
        # Query with sort by timestamp descending
        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
        
        logs = []
        async for log in cursor:
            # Remove MongoDB _id
            log.pop("_id", None)
            logs.append(log)
        
        return logs
    
    async def get_user_activity(self, actor_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get activity summary for a specific user.
        
        Args:
            actor_id: User ID
            days: Number of days to look back
        
        Returns:
            Activity summary with action counts and recent actions
        """
        from datetime import timedelta
        
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        logs = await self.get_logs(actor_id=actor_id, start_date=start_date, limit=1000)
        
        # Count actions by type
        action_counts = {}
        for log in logs:
            action = log.get("action")
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "actor_id": actor_id,
            "period_days": days,
            "total_actions": len(logs),
            "action_counts": action_counts,
            "recent_actions": logs[:10]  # Last 10 actions
        }
    
    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 50
    ) -> list:
        """
        Get complete history of changes to a specific resource.
        
        Args:
            resource_type: Type of resource (user, team, etc.)
            resource_id: Resource ID
            limit: Maximum results
        
        Returns:
            List of all actions performed on this resource
        """
        return await self.get_logs(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit
        )


# Global audit logger instance
audit_logger = AuditLogger()


async def log_audit(
    action: AuditAction,
    actor: dict,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None
):
    """
    Convenience function to log audit events.
    
    Args:
        action: Type of action
        actor: User dict from get_current_user()
        resource_type: Type of resource
        resource_id: ID of resource
        details: Additional details
        success: Whether action succeeded
        error_message: Error if failed
    """
    await audit_logger.log(
        action=action,
        actor_id=actor.get("employee_id", "unknown"),
        actor_name=actor.get("name", "Unknown"),
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        success=success,
        error_message=error_message
    )
