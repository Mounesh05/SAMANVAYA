"""
Authentication API endpoints.
Handles user registration and login.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.security import HTTPBearer
from domain.models.user import UserCreate, UserOut, LoginRequest, LoginResponse
from domain.services.auth_service import AuthService
from core.dependencies import get_current_user
from core.security import revoke_token
from pymongo.errors import PyMongoError
from core.rate_limiting import auth_rate_limit, limiter
from core.config import settings
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
auth_service = AuthService()
oauth2_scheme = HTTPBearer()


# CR-016: one message for every failed sign-in, so it never tells an
# attacker whether an account exists or is inactive.
SIGN_IN_FAILED = "Sign-in failed. Check your ID and both passwords, or contact your administrator."

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


async def _record_sign_in(request: Request, actor: dict, success: bool, login_id: str) -> None:
    """Audit every sign-in attempt (CR-016). Never blocks or fails a sign-in."""
    try:
        from core.audit import AuditAction, log_audit
        await log_audit(
            AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED,
            actor,
            resource_type="session",
            details={"login_id": login_id[:254], "ip": getattr(request.client, "host", None)},
            success=success,
        )
    except Exception:  # pragma: no cover - audit storage problems must not lock people out
        logger.warning("Could not record a sign-in attempt", exc_info=True)


async def _sign_in(request: Request, credentials: LoginRequest) -> LoginResponse:
    login_id = (credentials.login_id or "").strip()
    result = await auth_service.authenticate_user(
        login_id,
        credentials.organisation_password,
        credentials.employee_password,
    )
    if not result:
        await _record_sign_in(request, {"employee_id": "anonymous", "name": "Unknown"}, False, login_id)
        raise HTTPException(status_code=401, detail=SIGN_IN_FAILED)
    await _record_sign_in(request, {"employee_id": result.user.employee_id, "name": result.user.name}, True, login_id)
    return result


@router.post("/login", response_model=LoginResponse)
@auth_rate_limit()
async def login(request: Request, credentials: LoginRequest):
    """
    Sign in with an employee ID or work email and both passwords (CR-016).

    The earlier email-and-one-password form is gone: every sign-in checks
    the organisation password and the employee password.
    """
    return await _sign_in(request, credentials)


@router.post("/login/full", response_model=LoginResponse)
@auth_rate_limit()
async def login_full(request: Request, credentials: LoginRequest):
    """Same rule as /login; kept for existing scripts and clients."""
    return await _sign_in(request, credentials)


@router.post("/logout")
async def logout(
    authorization: str = Header(...),
    user: dict = Depends(get_current_user)
):
    """
    Logout by revoking the current access token.
    
    This revokes the JWT token server-side by adding its JTI to a revocation list.
    The token will be rejected on all subsequent requests until it expires naturally.
    
    Revocations are persisted in the shared MongoDB store across restarts and
    server instances. The response is successful only after persistence.
    """
    try:
        # Authentication already validated and decoded this exact session.
        await revoke_token(user["jti"], datetime.fromtimestamp(user["exp"], tz=timezone.utc))
        return {"message": "Successfully logged out"}
    except PyMongoError:
        logger.exception("Logout persistence unavailable")
        raise HTTPException(status_code=503, detail="Logout temporarily unavailable")
    except Exception:
        logger.exception("Logout failed")
        raise HTTPException(
            status_code=500,
            detail="Logout failed"
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
