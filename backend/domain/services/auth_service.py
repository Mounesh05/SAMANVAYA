"""
Authentication service.
Handles user registration, login, and authentication logic.
"""

from datetime import datetime, timezone
from typing import Optional
from core.security import hash_password, verify_password, create_access_token

# Checked when no account matches, so a failed sign-in takes about as long
# whether or not the account exists (no account discovery by timing).
_UNUSED_HASH = hash_password("no-account-matches-this-sign-in")
from core.permissions import get_user_permissions
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

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _token_payload(user: dict) -> dict:
        """JWT claims built from the CURRENT database record."""
        role = (user.get("role") or "DEVELOPER").strip().upper()
        return {
            "sub": user.get("employee_id", ""),
            "employee_id": user.get("employee_id", ""),
            "email": user.get("email", ""),
            "name": user.get("name", "Unknown"),
            "organizational_role": role,
            "system_access": "ADMIN" if user.get("is_admin", False) else "USER",
            "team_id": user.get("team_id"),
            "team_lead_id": user.get("team_lead_id"),
            "project_ids": user.get("project_ids", []),
            "designation": user.get("designation"),
            "org_id": (
                user.get("org_id")
                or user.get("organization_id")
                or user.get("organisation_id")
            ),
        }

    @staticmethod
    def _user_out(user: dict) -> UserOut:
        # The permission list is computed by the backend so the frontend never
        # keeps its own copy of the role matrix (CR-001 single source of truth).
        is_admin = bool(user.get("is_admin", False))
        permissions = get_user_permissions(
            user.get("role") or "", is_admin, user.get("designation")
        )
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
            is_admin=is_admin,
            designation=user.get("designation"),
            permissions=sorted(permission.value for permission in permissions),
        )

    def _login_response(self, user: dict) -> LoginResponse:
        token = create_access_token(self._token_payload(user))
        return LoginResponse(token=token, user=self._user_out(user))

    async def refresh_session(self, employee_id: str) -> Optional[str]:
        """
        Issue a fresh access token from the current database record.

        Returns None if the user no longer exists or was deactivated, so a
        revoked account cannot keep extending its session, and role/team
        changes take effect on the next refresh.
        """
        user = await self.user_repo.find_by_employee_id(employee_id)
        if not user or not user.get("is_active", True):
            return None
        return create_access_token(self._token_payload(user))

    # ── Authentication ────────────────────────────────────────────────────────

    async def _find_by_identifier(self, identifier: str) -> Optional[dict]:
        """An employee ID or a work email (CR-016)."""
        value = (identifier or "").strip()
        if not value:
            return None
        if "@" in value:
            return (await self.user_repo.find_by_email(value)
                    or await self.user_repo.find_by_email(value.lower()))
        return (await self.user_repo.find_by_employee_id(value)
                or await self.user_repo.find_by_employee_id(value.upper()))

    async def authenticate_user(
        self, identifier: str, organisation_password: str, employee_password: str
    ) -> Optional[LoginResponse]:
        """
        CR-016: the only sign-in rule. `identifier` is an employee ID or a work
        email; both the organisation and the employee password are always
        checked. Returns None for every failure (unknown account, wrong
        password, inactive account) so callers give one message.
        """
        user = await self._find_by_identifier(identifier)

        org_valid = verify_password(organisation_password or "", (user or {}).get("organisation_password") or _UNUSED_HASH)
        emp_valid = verify_password(employee_password or "", (user or {}).get("employee_password") or _UNUSED_HASH)

        if not user or not (org_valid and emp_valid) or not user.get("is_active", True):
            return None
        return self._login_response(user)

    async def get_user_by_employee_id(self, employee_id: str) -> Optional[UserOut]:
        """Get user by employee ID (without passwords)."""
        user = await self.user_repo.find_by_employee_id(employee_id)
        
        if not user:
            return None

        return self._user_out(user)
