"""
Authentication API endpoints.
Handles user registration and login.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from domain.models.user import UserCreate, UserOut, LoginRequest, LoginResponse
from domain.services.auth_service import AuthService
from core.dependencies import get_current_user

router = APIRouter()
auth_service = AuthService()


from typing import Optional

class UniversalLoginRequest(BaseModel):
    """Universal login request accepting email, employee_id, or user_id."""
    email: Optional[str] = None
    employee_id: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    organisation_password: Optional[str] = None
    employee_password: Optional[str] = None
    company_password: Optional[str] = None
    personal_password: Optional[str] = None


@router.post("/register", response_model=UserOut, status_code=201)
async def register(user_data: UserCreate):
    """
    Register a new user/employee.
    """
    try:
        user = await auth_service.register_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=LoginResponse)
async def login(credentials: UniversalLoginRequest):
    """
    Authenticate user with flexible identifier (email, employee_id, user_id)
    and password (single password or dual organization/employee password).
    Returns JWT token and user information.
    """
    identifier = (
        credentials.employee_id
        or credentials.user_id
        or credentials.email
        or credentials.username
        or ""
    )
    personal_pwd = (
        credentials.employee_password
        or credentials.personal_password
        or credentials.password
        or ""
    )
    org_pwd = (
        credentials.organisation_password
        or credentials.company_password
        or credentials.password
    )

    result = await auth_service.authenticate_user_flexible(
        identifier=identifier,
        password=personal_pwd,
        organisation_password=org_pwd,
    )

    if not result:
        raise HTTPException(
            status_code=401, 
            detail="Invalid credentials"
        )

    return result


@router.post("/login/full", response_model=LoginResponse)
async def login_full(credentials: LoginRequest):
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
    
    # Create new token with same payload
    new_token = create_access_token({
        "employee_id": user["employee_id"],
        "role": user["role"],
        "email": user["email"],
        "name": user["name"],
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
