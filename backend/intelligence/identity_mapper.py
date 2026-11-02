"""
Identity Mapper — Resolves and normalizes employee identity across systems:
    employee_id <-> GitHub username <-> email <-> organization identity

Ensures that GitHub activity, CI runs, and Jira tasks are attributed accurately
without relying solely on a single username.
"""

from typing import Dict, Any, Optional, List
import logging
from repositories.user_repository import UserRepository
from core.database import col

logger = logging.getLogger("samanvaya.identity_mapper")


class EmployeeIdentity:
    """Canonical representation of an employee's multi-system identity."""

    def __init__(
        self,
        employee_id: str,
        name: str,
        email: str,
        github_username: Optional[str] = None,
        role: str = "DEVELOPER",
        dept: str = "Engineering",
        company_id: str = "ORG-001",
        team_id: Optional[str] = None,
        aliases: Optional[List[str]] = None,
    ):
        self.employee_id = employee_id
        self.name = name
        self.email = email.lower() if email else ""
        self.github_username = (github_username or "").lower().strip()
        self.role = role
        self.dept = dept
        self.company_id = company_id
        self.team_id = team_id
        self.aliases = [a.lower().strip() for a in (aliases or []) if a]

    def matches_author(self, author_name: Optional[str], author_email: Optional[str], author_login: Optional[str]) -> bool:
        """
        Check if a given commit or PR author matches this employee.
        Considers email, GitHub login, full name, and registered aliases.
        """
        if author_email and author_email.lower() == self.email:
            return True

        if author_login and self.github_username and author_login.lower().strip() == self.github_username:
            return True

        if author_name:
            norm_author = author_name.lower().strip()
            if norm_author == self.name.lower().strip():
                return True
            for alias in self.aliases:
                if norm_author == alias:
                    return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "name": self.name,
            "email": self.email,
            "github_username": self.github_username,
            "role": self.role,
            "dept": self.dept,
            "company_id": self.company_id,
            "team_id": self.team_id,
            "aliases": self.aliases,
        }


class IdentityMapper:
    """Service to look up and cache employee identities."""

    def __init__(self):
        self.user_repo = UserRepository()

    async def get_identity(self, identifier: str) -> Optional[EmployeeIdentity]:
        """
        Resolves an employee identity by employee_id, email, or github_username.
        """
        if not identifier:
            return None

        # 1. Look up in users collection
        user = await self.user_repo.find_by_employee_id(identifier)
        if not user:
            user = await self.user_repo.find_by_email(identifier)
        if not user:
            user = await self.user_repo.find_one({"github_username": identifier})
        if not user:
            # Try case-insensitive email or ID match
            user = await col("users").find_one({
                "$or": [
                    {"employee_id": {"$regex": f"^{identifier}$", "$options": "i"}},
                    {"email": {"$regex": f"^{identifier}$", "$options": "i"}},
                    {"github_username": {"$regex": f"^{identifier}$", "$options": "i"}},
                ]
            })

        if not user:
            logger.warning("[IDENTITY] Could not resolve identity for identifier='%s'", identifier)
            return None

        return EmployeeIdentity(
            employee_id=user.get("employee_id") or str(user.get("_id")),
            name=user.get("name", "Unknown"),
            email=user.get("email", ""),
            github_username=user.get("github_username"),
            role=user.get("role", "DEVELOPER"),
            dept=user.get("dept", "Engineering"),
            company_id=user.get("company_id") or user.get("org_id", "ORG-001"),
            team_id=user.get("team_id"),
            aliases=user.get("aliases", []),
        )
