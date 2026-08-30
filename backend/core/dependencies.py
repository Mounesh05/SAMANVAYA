"""
FastAPI dependency injection.
Every protected route uses Depends(get_current_user).
Role-restricted routes use Depends(require_roles(...)).
Permission-restricted routes use decorators from core.permissions.
"""

from fastapi import Depends, HTTPException, Header
from typing import Optional
from .security import decode_token


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
