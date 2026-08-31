"""
Permission system for RBAC.
Defines permissions and role-based access control.
"""

from enum import Enum
from typing import Set


class Permission(str, Enum):
    """Granular permissions for system operations."""

    # Data visibility
    VIEW_OWN_DATA = "VIEW_OWN_DATA"
    VIEW_TEAM_DATA = "VIEW_TEAM_DATA"
    VIEW_PROJECT_DATA = "VIEW_PROJECT_DATA"
    VIEW_ORGANIZATION_DATA = "VIEW_ORGANIZATION_DATA"
    VIEW_ALL_DATA = "VIEW_ALL_DATA"

    # Performance
    VIEW_OWN_PERFORMANCE = "VIEW_OWN_PERFORMANCE"
    VIEW_TEAM_PERFORMANCE = "VIEW_TEAM_PERFORMANCE"
    VIEW_PROJECT_PERFORMANCE = "VIEW_PROJECT_PERFORMANCE"
    VIEW_ORGANIZATION_PERFORMANCE = "VIEW_ORGANIZATION_PERFORMANCE"
    VIEW_AI_EVALUATION = "VIEW_AI_EVALUATION"
    TRIGGER_AI_EVALUATION = "TRIGGER_AI_EVALUATION"
    TRIGGER_BULK_EVALUATION = "TRIGGER_BULK_EVALUATION"

    # Feedback
    SUBMIT_LEAD_FEEDBACK = "SUBMIT_LEAD_FEEDBACK"
    SUBMIT_PM_FEEDBACK = "SUBMIT_PM_FEEDBACK"
    SUBMIT_QA_FEEDBACK = "SUBMIT_QA_FEEDBACK"
    SUBMIT_DEVOPS_FEEDBACK = "SUBMIT_DEVOPS_FEEDBACK"
    SUBMIT_HR_FEEDBACK = "SUBMIT_HR_FEEDBACK"
    SUBMIT_CEO_FEEDBACK = "SUBMIT_CEO_FEEDBACK"
    VIEW_OWN_SUBMITTED_FEEDBACK = "VIEW_OWN_SUBMITTED_FEEDBACK"
    VIEW_ROLE_FEEDBACK = "VIEW_ROLE_FEEDBACK"

    # Administration (ADMIN only)
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_TEAMS = "MANAGE_TEAMS"
    MANAGE_EMPLOYEES = "MANAGE_EMPLOYEES"
    ASSIGN_TEAM_LEAD = "ASSIGN_TEAM_LEAD"
    ASSIGN_PROJECT = "ASSIGN_PROJECT"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    EXPORT_DATA = "EXPORT_DATA"
    MANAGE_SETTINGS = "MANAGE_SETTINGS"
    MANAGE_INTEGRATIONS = "MANAGE_INTEGRATIONS"


class OrganizationalRole(str, Enum):
    """Organizational roles (business functions)."""
    CEO = "CEO"
    HR = "HR"
    PM = "PM"
    LEAD = "LEAD"
    DEVELOPER = "DEVELOPER"
    QA = "QA"
    DEVOPS = "DEVOPS"


class SystemAccess(str, Enum):
    """System access levels."""
    USER = "USER"
    ADMIN = "ADMIN"


# Role permissions mapping
ROLE_PERMISSIONS: dict[OrganizationalRole, Set[Permission]] = {
    OrganizationalRole.DEVELOPER: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.VIEW_ORGANIZATION_DATA,
    },

    OrganizationalRole.LEAD: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_TEAM_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_TEAM_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_LEAD_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },

    OrganizationalRole.PM: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_PM_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },

    OrganizationalRole.QA: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_QA_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },

    OrganizationalRole.DEVOPS: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_DEVOPS_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },

    OrganizationalRole.HR: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_ORGANIZATION_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },

    OrganizationalRole.CEO: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_ALL_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_CEO_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRIGGER_AI_EVALUATION,
    },
}

# Admin permissions (added on top of role permissions)
ADMIN_PERMISSIONS: Set[Permission] = {
    Permission.MANAGE_USERS,
    Permission.MANAGE_TEAMS,
    Permission.MANAGE_EMPLOYEES,
    Permission.ASSIGN_TEAM_LEAD,
    Permission.ASSIGN_PROJECT,
    Permission.TRIGGER_AI_EVALUATION,
    Permission.TRIGGER_BULK_EVALUATION,
    Permission.VIEW_AUDIT_LOGS,
    Permission.EXPORT_DATA,
    Permission.MANAGE_SETTINGS,
    Permission.MANAGE_INTEGRATIONS,
}


def get_user_permissions(role: str, is_admin: bool = False) -> Set[Permission]:
    """
    Get all permissions for a user based on role and admin status.

    Args:
        role: Organizational role
        is_admin: Whether user has admin access

    Returns:
        Set of permissions
    """
    try:
        org_role = OrganizationalRole(role.upper())
        permissions = set(ROLE_PERMISSIONS.get(org_role, set()))
    except (ValueError, KeyError):
        return set()

    if is_admin:
        permissions.update(ADMIN_PERMISSIONS)

    return permissions
