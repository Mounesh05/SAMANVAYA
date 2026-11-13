"""
CR-012: the first two accounts of a new installation.

A new install starts with the Chief Executive and the platform administrator
as separate accounts (existing roles only): the CEO has no admin rights, and
the administrator is a DevOps employee with the admin flag (D1-A). Used by the
development first-run setup and by the production bootstrap script.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from core.security import hash_password, validate_password_strength

ADMIN_ROLE = "DEVOPS"


@dataclass(frozen=True)
class FirstAccount:
    employee_id: str
    name: str
    email: str
    organisation_password: str
    employee_password: str


def validate_pair(ceo: FirstAccount, admin: FirstAccount) -> None:
    """Raise ValueError with a readable message when the pair is not acceptable."""
    for label, account in (("Chief Executive", ceo), ("Platform administrator", admin)):
        for field in ("employee_id", "name", "email"):
            if not getattr(account, field).strip():
                raise ValueError(f"{label}: {field.replace('_', ' ')} is required")
        for kind, password in (("organisation", account.organisation_password),
                               ("employee", account.employee_password)):
            valid, message = validate_password_strength(password)
            if not valid:
                raise ValueError(f"{label} {kind} password: {message}")
        if account.organisation_password == account.employee_password:
            raise ValueError(f"{label}: organisation and employee passwords must be different")
    if ceo.employee_id.strip().upper() == admin.employee_id.strip().upper():
        raise ValueError("The two accounts need different employee IDs")
    if ceo.email.strip().lower() == admin.email.strip().lower():
        raise ValueError("The two accounts need different email addresses")
    if {ceo.organisation_password, ceo.employee_password} & {admin.organisation_password, admin.employee_password}:
        raise ValueError("The two accounts must not share a password")


def build_accounts(ceo: FirstAccount, admin: FirstAccount, created_by: str) -> List[dict]:
    """User records for the pair (passwords hashed). Call validate_pair first."""
    now = datetime.now(timezone.utc).isoformat()

    def record(account: FirstAccount, role: str, dept: str, is_admin: bool) -> dict:
        return {
            "employee_id": account.employee_id.strip().upper(),
            "name": account.name.strip(),
            "email": account.email.strip().lower(),
            "role": role,
            "dept": dept,
            "organisation_password": hash_password(account.organisation_password),
            "employee_password": hash_password(account.employee_password),
            "github_username": None,
            "team_id": None,
            "is_active": True,
            "is_admin": is_admin,
            "created_at": now,
            "created_by": created_by,
        }

    return [
        record(ceo, "CEO", "Executive", False),
        record(admin, ADMIN_ROLE, "Platform", True),
    ]
