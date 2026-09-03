"""
FastAPI dependency injection.
Every protected route uses Depends(get_current_user).
Role-restricted routes use Depends(require_roles(...)).
Permission-restricted routes use Depends(require_permission(...)).
"""

from fastapi import Depends, HTTPException, Header
from typing import Optional
from .security import decode_token
from .permissions import Permission, get_user_permissions


async def get_current_user(authorization: str = Header(...)) -> dict:
    """
    Validates Bearer JWT on every protected request.
    
    Args:
        authorization: Authorization header with Bearer token
    
    Returns:
        Decoded user payload dict containing:
            - sub: str (user ID)
            - employee_id: str
            - role: str (CEO|HR|PM|LEAD|DEVELOPER|DEVOPS|QA)
            - email: str
            - name: str
            - is_admin: bool (from system_access == "ADMIN")
            - team_id: Optional[str]
            - project_ids: Optional[List[str]]
    
    Raises:
        HTTPException 401: If token is invalid or expired
    
    Example:
        @router.get("/profile")
        async def get_profile(user: dict = Depends(get_current_user)):
            return {"employee_id": user["employee_id"]}
    """
    try:
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_token(token)
        
        # Add is_admin flag from system_access field
        payload['is_admin'] = payload.get('system_access') == 'ADMIN'
        
        # Normalize role field (JWT has organizational_role, but we want role)
        if 'organizational_role' in payload and 'role' not in payload:
            payload['role'] = payload['organizational_role']
        
        return payload
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """
    Optional authentication - returns user if authenticated, None otherwise.
    Useful for endpoints that work with or without authentication.
    
    Args:
        authorization: Optional Authorization header with Bearer token
    
    Returns:
        Decoded user payload dict or None
    """
    if not authorization:
        return None
    
    try:
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_token(token)
        payload['is_admin'] = payload.get('system_access') == 'ADMIN'
        
        # Normalize role field
        if 'organizational_role' in payload and 'role' not in payload:
            payload['role'] = payload['organizational_role']
            
        return payload
    except ValueError:
        return None


def require_roles(*roles: str):
    """
    Factory that returns a dependency enforcing role access.
    
    Args:
        *roles: Allowed role names (CEO, HR, PM, LEAD, DEVELOPER, DEVOPS, QA)
    
    Returns:
        Dependency function that validates user role
    
    Raises:
        HTTPException 403: If user role not in allowed roles
    
    Example:
        @router.get("/admin")
        async def admin_only(user: dict = Depends(require_roles("CEO", "HR"))):
            return {"message": "Admin access granted"}
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        # Check both role and organizational_role fields for compatibility
        user_role = user.get("role", user.get("organizational_role", "")).upper()
        allowed_roles = [r.upper() for r in roles]
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Insufficient permissions. Required role: {', '.join(roles)} (user has: {user_role})"
            )
        return user

    return _check


def require_admin():
    """
    Dependency that requires admin access.
    
    Returns:
        Dependency function that validates admin status
    
    Raises:
        HTTPException 403: If user is not admin
    
    Example:
        @router.post("/admin/users")
        async def create_user(user: dict = Depends(require_admin())):
            return {"message": "Admin access granted"}
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if not user.get("is_admin", False):
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        return user

    return _check


def require_permission(*permissions: Permission):
    """
    Factory that returns a dependency enforcing permission-based access.
    
    This is the PRIMARY authorization mechanism. Use this instead of require_roles
    for granular permission checks.
    
    Args:
        *permissions: Required Permission enum values (user must have AT LEAST ONE)
    
    Returns:
        Dependency function that validates user has required permission(s)
    
    Raises:
        HTTPException 403: If user lacks all required permissions
    
    Example:
        @router.post("/projects")
        async def create_project(
            project: ProjectCreate,
            user: dict = Depends(require_permission(Permission.CREATE_PROJECT))
        ):
            return {"message": "Project created"}
    
    Example (multiple permissions - OR logic):
        @router.put("/tasks/{task_id}/status")
        async def update_status(
            task_id: str,
            user: dict = Depends(require_permission(
                Permission.MOVE_TASK, 
                Permission.TRANSITION_TASK
            ))
        ):
            # User needs EITHER MOVE_TASK OR TRANSITION_TASK
            return {"message": "Status updated"}
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", user.get("organizational_role", ""))
        is_admin = user.get("is_admin", False)
        
        # Get user's permissions based on role and admin status
        user_permissions = get_user_permissions(user_role, is_admin)
        
        # Check if user has at least one of the required permissions
        required_perms = set(permissions)
        if not required_perms.intersection(user_permissions):
            perm_names = ", ".join([p.value for p in permissions])
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {perm_names}"
            )
        
        return user

    return _check


def require_all_permissions(*permissions: Permission):
    """
    Factory that returns a dependency enforcing ALL permissions are required (AND logic).
    
    Use this when user must have ALL listed permissions, not just one.
    
    Args:
        *permissions: Required Permission enum values (user must have ALL)
    
    Returns:
        Dependency function that validates user has all permissions
    
    Raises:
        HTTPException 403: If user lacks any required permission
    
    Example:
        @router.delete("/projects/{project_id}")
        async def delete_project(
            project_id: str,
            user: dict = Depends(require_all_permissions(
                Permission.MANAGE_PROJECTS,
                Permission.VIEW_AUDIT_LOGS
            ))
        ):
            # User needs BOTH permissions
            return {"message": "Project deleted"}
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", user.get("organizational_role", ""))
        is_admin = user.get("is_admin", False)
        
        # Get user's permissions
        user_permissions = get_user_permissions(user_role, is_admin)
        
        # Check if user has ALL required permissions
        required_perms = set(permissions)
        if not required_perms.issubset(user_permissions):
            missing = required_perms - user_permissions
            missing_names = ", ".join([p.value for p in missing])
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Missing: {missing_names}"
            )
        
        return user

    return _check
