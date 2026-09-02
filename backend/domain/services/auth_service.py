"""
Authentication service.
Handles user registration, login, and authentication logic.
"""

from datetime import datetime, timezone
from typing import Optional
from core.security import hash_password, verify_password, create_access_token
from repositories.user_repository import UserRepository
from domain.models.user import UserCreate, UserOut, LoginResponse


class AuthService:
    """Service for authentication operations."""

    def __init__(self):
        self.user_repo = UserRepository()

    async def register_user(self, user_data: UserCreate) -> UserOut:
        """
        Register a new user.
        
        Args:
            user_data: User registration data
        
        Returns:
            Created user (without passwords)
        
        Raises:
            ValueError: If employee_id or email already exists
        """
        # Check if user already exists
        existing = await self.user_repo.find_by_employee_id(user_data.employee_id)
        if existing:
            raise ValueError("Employee ID already registered")

        existing = await self.user_repo.find_by_email(user_data.email)
        if existing:
            raise ValueError("Email already registered")

        # Hash passwords
        hashed_org_pwd = hash_password(user_data.organisation_password)
        hashed_emp_pwd = hash_password(user_data.employee_password)

        # Create user document
        user_doc = {
            "employee_id": user_data.employee_id,
            "name": user_data.name,
            "email": user_data.email,
            "role": user_data.role,
            "dept": user_data.dept,
            "organisation_password": hashed_org_pwd,
            "employee_password": hashed_emp_pwd,
            "github_username": user_data.github_username,
            "team_id": user_data.team_id,
            "avatar": user_data.avatar,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.user_repo.insert(user_doc)

        # Return user without passwords
        return UserOut(
            employee_id=user_data.employee_id,
            name=user_data.name,
            email=user_data.email,
            role=user_data.role,
            dept=user_data.dept,
            avatar=user_data.avatar,
            is_active=True,
            github_username=user_data.github_username,
            team_id=user_data.team_id,
        )

    async def authenticate_user(
        self, employee_id: str, organisation_password: str, employee_password: str
    ) -> Optional[LoginResponse]:
        """
        Authenticate user with both organization and employee passwords.
        
        Args:
            employee_id: Employee ID
            organisation_password: Organization password
            employee_password: Employee password
        
        Returns:
            LoginResponse with token and user data, or None if auth fails
        """
        user = await self.user_repo.find_by_employee_id(employee_id)
        
        if not user:
            return None

        if not user.get("is_active", True):
            return None

        # Verify both passwords
        org_pwd_valid = verify_password(
            organisation_password, user.get("organisation_password", "")
        )
        emp_pwd_valid = verify_password(
            employee_password, user.get("employee_password", "")
        )

        if not (org_pwd_valid and emp_pwd_valid):
            return None

        # Create JWT token
        token_payload = {
            "sub": user.get("employee_id", ""),
            "employee_id": user.get("employee_id", ""),
            "email": user.get("email", ""),
            "name": user.get("name", "Unknown"),
            "organizational_role": user.get("role", "DEVELOPER").upper(),
            "system_access": "ADMIN" if user.get("is_admin", False) else "USER",
            "team_id": user.get("team_id"),
            "project_ids": user.get("project_ids", []),
        }
        access_token = create_access_token(token_payload)

        # Return response
        user_out = UserOut(
            employee_id=user.get("employee_id", ""),
            name=user.get("name", "Unknown"),
            email=user.get("email", ""),
            role=user.get("role", "DEVELOPER"),
            dept=user.get("dept", "Engineering"),
            avatar=user.get("avatar"),
            is_active=user.get("is_active", True),
            github_username=user.get("github_username"),
            team_id=user.get("team_id"),
        )

        return LoginResponse(token=access_token, user=user_out)

    async def authenticate_user_by_email(
        self, email: str, password: str
    ) -> Optional[LoginResponse]:
        """
        Authenticate user with email and password.
        Simplified authentication that uses the same password for both org and employee auth.
        
        Args:
            email: User email address
            password: Password (used for both org and employee verification)
        
        Returns:
            LoginResponse with token and user data, or None if auth fails
        """
        user = await self.user_repo.find_by_email(email)
        
        if not user:
            return None

        if not user.get("is_active", True):
            return None

        # For simplified auth, verify against employee_password
        pwd_valid = verify_password(password, user.get("employee_password", ""))

        if not pwd_valid:
            return None

        # Create JWT token with frontend-required fields
        token_payload = {
            "sub": user.get("employee_id", ""),
            "employee_id": user.get("employee_id", ""),
            "email": user.get("email", ""),
            "name": user.get("name", "Unknown"),
            "organizational_role": user.get("role", "DEVELOPER").upper(),
            "system_access": "ADMIN" if user.get("is_admin", False) else "USER",
            "team_id": user.get("team_id"),
            "team_lead_id": user.get("team_lead_id"),
            "project_ids": user.get("project_ids", []),
        }
        access_token = create_access_token(token_payload)

        # Return response - ALL fields use .get() with defaults
        user_out = UserOut(
            employee_id=user.get("employee_id", ""),
            name=user.get("name", "Unknown"),
            email=user.get("email", ""),
            role=user.get("role", "DEVELOPER"),
            dept=user.get("dept", "Engineering"),
            avatar=user.get("avatar"),
            is_active=user.get("is_active", True),
            github_username=user.get("github_username"),
            team_id=user.get("team_id"),
        )

        return LoginResponse(token=access_token, user=user_out)

    async def get_user_by_employee_id(self, employee_id: str) -> Optional[UserOut]:
        """Get user by employee ID (without passwords)."""
        user = await self.user_repo.find_by_employee_id(employee_id)
        
        if not user:
            return None

        return UserOut(
            employee_id=user.get("employee_id", ""),
            name=user.get("name", "Unknown"),
            email=user.get("email", ""),
            role=user.get("role", "DEVELOPER"),
            dept=user.get("dept", "Engineering"),
            avatar=user.get("avatar"),
            is_active=user.get("is_active", True),
            github_username=user.get("github_username"),
            team_id=user.get("team_id"),
        )
