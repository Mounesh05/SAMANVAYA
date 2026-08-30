"""
User/Employee domain models.
Users represent employees with roles in the organization.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    """Request model for creating a new user/employee."""
    
    employee_id: str
    name: str
    email: EmailStr
    role: str  # CEO|HR|PM|LEAD|DEVELOPER|DEVOPS|QA
    dept: str
    organisation_password: str
    employee_password: str
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    avatar: Optional[str] = None


class UserOut(BaseModel):
    """Response model for user data (excludes passwords)."""
    
    employee_id: str
    name: str
    email: str
    role: str
    dept: str
    avatar: Optional[str] = None
    is_active: bool = True
    github_username: Optional[str] = None
    team_id: Optional[str] = None


class LoginRequest(BaseModel):
    """Request model for user login."""
    
    employee_id: str
    organisation_password: str
    employee_password: str


class LoginResponse(BaseModel):
    """Response model for successful login."""
    
    token: str  # Changed from access_token to match frontend
    token_type: str = "bearer"
    user: UserOut
