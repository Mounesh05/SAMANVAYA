"""
Authentication API endpoints.
Handles user registration and login.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from domain.models.user import UserCreate, UserOut, LoginRequest, LoginResponse
from domain.services.auth_service import AuthService
from core.dependencies import get_current_user
from core.security import decode_token, revoke_token
from core.rate_limiting import limiter
from core.config import settings
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
auth_service = AuthService()
oauth2_scheme = HTTPBearer()


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
async def logout(
    authorization: str = Header(...),
    user: dict = Depends(get_current_user)
):
    """
    Logout by revoking the current access token.
    
    This revokes the JWT token server-side by adding its JTI to a revocation list.
    The token will be rejected on all subsequent requests until it expires naturally.
    
    Note: For production multi-instance deployments, the revocation list must be
    moved to Redis to share state across instances.
    """
    try:
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if jti and exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            revoke_token(jti, exp_datetime)
            return {"message": "Successfully logged out"}
        else:
            # Token without jti (shouldn't happen with new tokens, but handle gracefully)
            return {"message": "Logged out successfully"}
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
    except Exception as e:
        logger.exception("Logout failed")
        raise HTTPException(
            status_code=500,
            detail=f"Logout failed: {str(e)}"
        )


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
