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
    Register a new user/employee.
    
    Restricted roles: CEO and HR cannot self-register.
    Only DEVELOPER, LEAD, PM, QA, DEVOPS can register.
    HR/CEO accounts must be created by HR via the employees endpoint.
    """
    # Block privileged role self-registration
    restricted_roles = {"CEO", "HR"}
    if user_data.role.upper() in restricted_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{user_data.role}' cannot self-register. Contact HR to create this account."
        )
    
    try:
        user = await auth_service.register_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
    Logout user (token invalidation handled by frontend).
    Backend can log the logout event here if needed.
    """
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(user: dict = Depends(get_current_user)):
    """
    Refresh access token.
    Returns a new JWT token for the authenticated user.
    """
    from core.security import create_access_token
    
    # Preserve ALL claims from the original token so admin rights,
    # team_id, project_ids, etc. are not silently dropped
    new_token = create_access_token({
        "sub": user.get("sub", user.get("employee_id")),
        "employee_id": user["employee_id"],
        "role": user.get("role", user.get("organizational_role")),
        "organizational_role": user.get("organizational_role", user.get("role")),
        "email": user["email"],
        "name": user["name"],
        "system_access": user.get("system_access", "USER"),
        "team_id": user.get("team_id"),
        "team_lead_id": user.get("team_lead_id"),
        "project_ids": user.get("project_ids", []),
    })
    
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
