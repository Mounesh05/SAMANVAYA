"""
Authentication API endpoints.
Handles user registration and login.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from domain.models.user import UserCreate, UserOut, LoginRequest, LoginResponse
from domain.services.auth_service import AuthService
from core.dependencies import get_current_user
from core.rate_limiting import limiter
from core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
auth_service = AuthService()


class SimpleLoginRequest(BaseModel):
    """Simplified login request for email + password authentication."""
    email: EmailStr
    password: str


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit("3/minute")
async def register(request: Request, user_data: UserCreate):
    """
    Public self-registration (disabled unless ALLOW_SELF_REGISTRATION=true).

    Even when enabled, only the DEVELOPER role can self-register and team
    assignment is ignored. All other roles are created by HR/admin through
    POST /api/employees.
    """
    if not settings.ALLOW_SELF_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Self-registration is disabled. Ask HR to create your account.",
        )

    role = (user_data.role or "").strip().upper()
    if role != "DEVELOPER":
        raise HTTPException(
            status_code=403,
            detail="Only the DEVELOPER role can self-register. Contact HR for other roles.",
        )
    user_data = user_data.model_copy(update={"role": role, "team_id": None})

    try:
        user = await auth_service.register_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Registration failed")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, credentials: SimpleLoginRequest):
    """
    Authenticate user with email and password.
    Returns JWT token and user information.
    
    This is a simplified login endpoint that accepts email + password.
    The password is used for both organization and employee authentication.
    """
    # Use email to find user and password for both auth fields
    result = await auth_service.authenticate_user_by_email(
        credentials.email,
        credentials.password
    )

    if not result:
        raise HTTPException(
            status_code=401, 
            detail="Invalid email or password"
        )

    return result


@router.post("/login/full", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login_full(request: Request, credentials: LoginRequest):
    """
    Authenticate user with employee_id and both passwords.
    
    Requires both organization password and employee password.
    This is the original authentication method.
    """
    result = await auth_service.authenticate_user(
        credentials.employee_id,
        credentials.organisation_password,
        credentials.employee_password,
    )

    if not result:
        raise HTTPException(
            status_code=401, detail="Invalid credentials or user not active"
        )

    return result


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """
    Logout user (token invalidation handled client-side).
    
    IMPORTANT: This is currently a no-op endpoint. JWT tokens are stateless
    and cannot be revoked server-side without additional infrastructure.
    
    Current Implementation:
    - Token invalidation is handled by the frontend by removing the token
      from browser storage
    - The backend does not maintain a session or token registry
    
    Security Implications:
    - A stolen JWT remains valid until expiry, even after logout
    - Tokens cannot be revoked immediately (e.g., for compromised accounts)
    - Users who logout remain authenticated for the token lifetime
    
    Recommended Architecture:
    - Implement a token blacklist using a 'revoked_tokens' MongoDB collection
      or Redis cache with TTL matching token expiry
    - On logout, add the token's JTI claim to the blacklist
    - Modify get_current_user dependency to check blacklist before accepting
      any token
    - For high-security requirements, consider short-lived access tokens
      (15 minutes) with refresh tokens
    
    Current Mitigation:
    - Tokens expire after a short period (configured in JWT_EXPIRY)
    - Keep token lifetime minimal to reduce exposure window
    - Consider token refresh mechanism for legitimate long-lived sessions
    
    Backend can log the logout event here if audit trail is needed.
    """
    return {"message": "Logged out successfully"}


@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh_token(request: Request, user: dict = Depends(get_current_user)):
    """
    Refresh access token.

    Claims are rebuilt from the current database record, not copied from the
    old token. Deactivated or deleted accounts are rejected, and role/team
    changes take effect on refresh.
    """
    new_token = await auth_service.refresh_session(user.get("employee_id", ""))
    if not new_token:
        raise HTTPException(status_code=401, detail="Account is inactive or no longer exists")
    return {"token": new_token}


@router.get("/me", response_model=UserOut)
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information.
    Requires valid JWT token in Authorization header.
    """
    user_data = await auth_service.get_user_by_employee_id(user["employee_id"])
    
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return user_data
