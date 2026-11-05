"""
Permission system for RBAC.
Defines permissions and role-based access control.
"""

from enum import Enum
from typing import Optional, Set


class Permission(str, Enum):
    """Granular permissions for system operations."""

    # Data visibility
    VIEW_OWN_DATA = "VIEW_OWN_DATA"
    VIEW_TEAM_DATA = "VIEW_TEAM_DATA"
    VIEW_PROJECT_DATA = "VIEW_PROJECT_DATA"
    VIEW_ORGANIZATION_DATA = "VIEW_ORGANIZATION_DATA"
    VIEW_ALL_DATA = "VIEW_ALL_DATA"

    # HR-specific permissions
    VIEW_EMPLOYEE_DIRECTORY = "VIEW_EMPLOYEE_DIRECTORY"
    VIEW_EMPLOYEE_PROFILE = "VIEW_EMPLOYEE_PROFILE"
    VIEW_ORG_CHART = "VIEW_ORG_CHART"
    VIEW_PERFORMANCE_OUTCOMES = "VIEW_PERFORMANCE_OUTCOMES"
    CREATE_EMPLOYEE = "CREATE_EMPLOYEE"
    UPDATE_EMPLOYEE_PROFILE = "UPDATE_EMPLOYEE_PROFILE"
    DEACTIVATE_EMPLOYEE = "DEACTIVATE_EMPLOYEE"
    VIEW_TRANSFER_REQUESTS = "VIEW_TRANSFER_REQUESTS"
    REVIEW_TRANSFER_REQUEST = "REVIEW_TRANSFER_REQUEST"
    UPDATE_EMPLOYMENT_RECORDS = "UPDATE_EMPLOYMENT_RECORDS"
    MANAGE_CANDIDATES = "MANAGE_CANDIDATES"
    VIEW_COMPENSATION = "VIEW_COMPENSATION"
    VIEW_GRIEVANCES = "VIEW_GRIEVANCES"

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

    # CRUD Operations
    CREATE_PROJECT = "CREATE_PROJECT"
    CREATE_TASK = "CREATE_TASK"
    CREATE_SPRINT = "CREATE_SPRINT"
    CREATE_STORY = "CREATE_STORY"
    CREATE_TEAM = "CREATE_TEAM"
    CREATE_BUG = "CREATE_BUG"
    CREATE_INCIDENT = "CREATE_INCIDENT"
    
    # Task Management
    MOVE_TASK = "MOVE_TASK"
    TRANSITION_TASK = "TRANSITION_TASK"
    
    # Code Analysis & Integration
    TRIGGER_CODE_ANALYSIS = "TRIGGER_CODE_ANALYSIS"
    SYNC_PR = "SYNC_PR"

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
        Permission.TRANSITION_TASK,
        # CRUD permissions
        Permission.CREATE_BUG,
        Permission.CREATE_STORY,
        # Integration
        Permission.SYNC_PR,
    },

    OrganizationalRole.LEAD: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_TEAM_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_TEAM_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_LEAD_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        # CRUD permissions
        Permission.CREATE_TASK,
        Permission.CREATE_STORY,
        Permission.CREATE_BUG,
        # Task management
        Permission.MOVE_TASK,
        Permission.TRANSITION_TASK,
        # AI
        Permission.TRIGGER_AI_EVALUATION,
    },

    OrganizationalRole.PM: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_PM_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        # CRUD permissions
        Permission.CREATE_PROJECT,
        Permission.CREATE_TASK,
        Permission.CREATE_SPRINT,
        Permission.CREATE_STORY,
        # Task management
        Permission.MOVE_TASK,
        Permission.TRANSITION_TASK,
    },

    OrganizationalRole.QA: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_QA_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRANSITION_TASK,
        # CRUD permissions
        Permission.CREATE_BUG,
        # Code analysis
        Permission.TRIGGER_CODE_ANALYSIS,
    },

    OrganizationalRole.DEVOPS: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PROJECT_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_DEVOPS_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRANSITION_TASK,
        # CRUD permissions
        Permission.CREATE_INCIDENT,
        # Code analysis
        Permission.TRIGGER_CODE_ANALYSIS,
    },

    OrganizationalRole.HR: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_ORGANIZATION_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        # Admin permissions (HR gets some admin capabilities)
        Permission.MANAGE_EMPLOYEES,
        Permission.MANAGE_TEAMS,
        Permission.ASSIGN_TEAM_LEAD,
        Permission.ASSIGN_PROJECT,
        Permission.TRIGGER_AI_EVALUATION,
        Permission.VIEW_AUDIT_LOGS,
        # CRUD permissions
        Permission.CREATE_TEAM,
    },

    OrganizationalRole.CEO: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_ALL_DATA,
        Permission.VIEW_ORGANIZATION_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_CEO_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRIGGER_AI_EVALUATION,
        Permission.TRIGGER_BULK_EVALUATION,
        Permission.EXPORT_DATA,
        Permission.VIEW_AUDIT_LOGS,
        # CRUD permissions
        Permission.CREATE_INCIDENT,
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


# HR Designation-based permissions
HR_DESIGNATION_PERMISSIONS: dict[str, Set[Permission]] = {
    "HR_MANAGER": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_ORG_CHART,
        Permission.VIEW_PERFORMANCE_OUTCOMES,
        Permission.CREATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE_PROFILE,
        Permission.DEACTIVATE_EMPLOYEE,
        Permission.VIEW_TRANSFER_REQUESTS,
        Permission.REVIEW_TRANSFER_REQUEST,
        Permission.UPDATE_EMPLOYMENT_RECORDS,
        Permission.MANAGE_CANDIDATES,
        Permission.VIEW_COMPENSATION,
        Permission.VIEW_GRIEVANCES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    "RECRUITER": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.CREATE_EMPLOYEE,
        Permission.MANAGE_CANDIDATES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
    },
    "HR_OPERATIONS": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.CREATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE_PROFILE,
        Permission.DEACTIVATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYMENT_RECORDS,
        Permission.VIEW_TRANSFER_REQUESTS,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
    },
    "HRBP": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_ORG_CHART,
        Permission.VIEW_PERFORMANCE_OUTCOMES,
        Permission.VIEW_TRANSFER_REQUESTS,
        Permission.REVIEW_TRANSFER_REQUEST,
        Permission.VIEW_GRIEVANCES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    "EMPLOYEE_RELATIONS": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_GRIEVANCES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
    },
    "COMPENSATION_BENEFITS": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_COMPENSATION,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
    },
}


def get_user_permissions(role: str, is_admin: bool = False, designation: Optional[str] = None) -> Set[Permission]:
    """
    Get all permissions for a user based on role, admin status, and HR designation.

    Args:
        role: Organizational role
        is_admin: Whether user has admin access
        designation: HR designation (for HR role only)

    Returns:
        Set of permissions
    """
    try:
        org_role = OrganizationalRole(role.upper())
        permissions = set(ROLE_PERMISSIONS.get(org_role, set()))
    except (ValueError, KeyError):
        return set()

    # Add HR designation-specific permissions
    if org_role == OrganizationalRole.HR and designation:
        designation_perms = HR_DESIGNATION_PERMISSIONS.get(designation, set())
        permissions.update(designation_perms)

    if is_admin:
        permissions.update(ADMIN_PERMISSIONS)

    return permissions
