"""
Permission system for RBAC.
Defines permissions and role-based access control decorators.
"""

from enum import Enum
from typing import List, Set
from functools import wraps
from fastapi import HTTPException, Depends
from core.dependencies import get_current_user


class Permission(str, Enum):
    """Granular permissions for system operations."""
    
    # Data visibility
    VIEW_OWN_DATA = "VIEW_OWN_DATA"
    VIEW_TEAM_DATA = "VIEW_TEAM_DATA"
    VIEW_PROJECT_DATA = "VIEW_PROJECT_DATA"
    VIEW_ORGANIZATION_DATA = "VIEW_ORGANIZATION_DATA"
    VIEW_ALL_DATA = "VIEW_ALL_DATA"
    
    # Performance
    VIEW_OWN_PERFORMANCE = "VIEW_OWN_PERFORMANCE"
    VIEW_TEAM_PERFORMANCE = "VIEW_TEAM_PERFORMANCE"
    VIEW_PROJECT_PERFORMANCE = "VIEW_PROJECT_PERFORMANCE"
    VIEW_ORGANIZATION_PERFORMANCE = "VIEW_ORGANIZATION_PERFORMANCE"
    VIEW_AI_EVALUATION = "VIEW_AI_EVALUATION"
    TRIGGER_AI_EVALUATION = "TRIGGER_AI_EVALUATION"
    TRIGGER_BULK_EVALUATION = "TRIGGER_BULK_EVALUATION"
    
    # Feedback
    SUBMIT_LEAD_FEEDBACK = "SUBMIT_LEAD_FEEDBACK"
    SUBMIT_PM_FEEDBACK = "SUBMIT_PM_FEEDBACK"
    SUBMIT_QA_FEEDBACK = "SUBMIT_QA_FEEDBACK"
    SUBMIT_DEVOPS_FEEDBACK = "SUBMIT_DEVOPS_FEEDBACK"
    SUBMIT_HR_FEEDBACK = "SUBMIT_HR_FEEDBACK"
    SUBMIT_CEO_FEEDBACK = "SUBMIT_CEO_FEEDBACK"
    VIEW_OWN_SUBMITTED_FEEDBACK = "VIEW_OWN_SUBMITTED_FEEDBACK"
    VIEW_ROLE_FEEDBACK = "VIEW_ROLE_FEEDBACK"
    
    # Administration (ADMIN only)
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_TEAMS = "MANAGE_TEAMS"
    MANAGE_EMPLOYEES = "MANAGE_EMPLOYEES"
    ASSIGN_TEAM_LEAD = "ASSIGN_TEAM_LEAD"
    ASSIGN_PROJECT = "ASSIGN_PROJECT"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    EXPORT_DATA = "EXPORT_DATA"
    MANAGE_SETTINGS = "MANAGE_SETTINGS"
    MANAGE_INTEGRATIONS = "MANAGE_INTEGRATIONS"


class OrganizationalRole(str, Enum):
    """Organizational roles (business functions)."""
    CEO = "CEO"
    HR = "HR"
    PM = "PM"
    LEAD = "LEAD"
    DEVELOPER = "DEVELOPER"
    QA = "QA"
    DEVOPS = "DEVOPS"


class SystemAccess(str, Enum):
    """System access levels."""
    USER = "USER"
    ADMIN = "ADMIN"


# Role permissions mapping
ROLE_PERMISSIONS: dict[OrganizationalRole, Set[Permission]] = {
    OrganizationalRole.DEVELOPER: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
    },
    
    OrganizationalRole.LEAD: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_TEAM_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_TEAM_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_LEAD_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    
    OrganizationalRole.PM: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_PM_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    
    OrganizationalRole.QA: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_QA_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    
    OrganizationalRole.DEVOPS: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_DEVOPS_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    
    OrganizationalRole.HR: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_ORGANIZATION_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    
    OrganizationalRole.CEO: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_ALL_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_CEO_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRIGGER_AI_EVALUATION,
    },
}

# Admin permissions (added on top of role permissions)
ADMIN_PERMISSIONS: Set[Permission] = {
    Permission.MANAGE_USERS,
    Permission.MANAGE_TEAMS,
    Permission.MANAGE_EMPLOYEES,
    Permission.ASSIGN_TEAM_LEAD,
    Permission.ASSIGN_PROJECT,
    Permission.TRIGGER_AI_EVALUATION,
    Permission.TRIGGER_BULK_EVALUATION,
    Permission.VIEW_AUDIT_LOGS,
    Permission.EXPORT_DATA,
    Permission.MANAGE_SETTINGS,
    Permission.MANAGE_INTEGRATIONS,
}


def get_user_permissions(role: str, is_admin: bool = False) -> Set[Permission]:
    """
    Get all permissions for a user based on role and admin status.
    
    Args:
        role: Organizational role
        is_admin: Whether user has admin access
    
    Returns:
        Set of permissions
    """
    try:
        org_role = OrganizationalRole(role.upper())
        permissions = ROLE_PERMISSIONS.get(org_role, set()).copy()
        
        # Add admin permissions if user is admin
        if is_admin:
            permissions.update(ADMIN_PERMISSIONS)
        
        return permissions
    except (ValueError, KeyError):
        return set()


def require_permission(*required_permissions: Permission):
    """
    Decorator to require specific permissions for an endpoint.
    
    Usage:
        @router.get("/endpoint")
        @require_permission(Permission.VIEW_TEAM_DATA)
        async def endpoint(user: dict = Depends(get_current_user)):
            ...
    
    Args:
        *required_permissions: One or more permissions required (user needs ANY)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user from dependency
            user = kwargs.get('user') or kwargs.get('current_user')
            
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            # Get user permissions
            role = user.get('role', '').upper()
            is_admin = user.get('is_admin', False)
            user_permissions = get_user_permissions(role, is_admin)
            
            # Check if user has any of the required permissions
            has_permission = any(
                perm in user_permissions 
                for perm in required_permissions
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required: {', '.join(p.value for p in required_permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_admin():
    """
    Decorator to require admin access for an endpoint.
    
    Usage:
        @router.post("/admin/endpoint")
        @require_admin()
        async def endpoint(user: dict = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user from dependency
            user = kwargs.get('user') or kwargs.get('current_user')
            
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            # Check admin status
            if not user.get('is_admin', False):
                raise HTTPException(
                    status_code=403,
                    detail="Admin access required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(*required_roles: OrganizationalRole):
    """
    Decorator to require specific roles for an endpoint.
    
    Usage:
        @router.get("/endpoint")
        @require_role(OrganizationalRole.LEAD, OrganizationalRole.PM)
        async def endpoint(user: dict = Depends(get_current_user)):
            ...
    
    Args:
        *required_roles: One or more roles required (user needs ANY)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user from dependency
            user = kwargs.get('user') or kwargs.get('current_user')
            
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            # Check role
            user_role = user.get('role', '').upper()
            has_role = any(
                user_role == role.value 
                for role in required_roles
            )
            
            if not has_role:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient role. Required: {', '.join(r.value for r in required_roles)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_resource_access(user: dict, resource_owner_id: str, permission: Permission) -> bool:
    """
    Check if user can access a specific resource.
    
    Args:
        user: Current user dict
        resource_owner_id: ID of the resource owner
        permission: Permission to check
    
    Returns:
        True if user has access, False otherwise
    """
    # Admin can access everything
    if user.get('is_admin', False):
        return True
    
    # Get user permissions
    role = user.get('role', '').upper()
    user_permissions = get_user_permissions(role, False)
    
    # Check if user has the permission
    if permission not in user_permissions:
        return False
    
    # Check scope
    if permission == Permission.VIEW_OWN_DATA or permission == Permission.VIEW_OWN_PERFORMANCE:
        # Can only view own data
        return user.get('employee_id') == resource_owner_id
    
    if permission == Permission.VIEW_TEAM_DATA or permission == Permission.VIEW_TEAM_PERFORMANCE:
        # Can view team data if same team
        return user.get('team_id') == resource_owner_id
    
    # For broader permissions, grant access
    return True
