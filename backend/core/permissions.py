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
    VIEW_APPROVED_PERFORMANCE_OUTCOMES = "VIEW_PERFORMANCE_OUTCOMES"  # Alias
    VIEW_HR_PERFORMANCE_ASSESSMENT = "VIEW_HR_PERFORMANCE_ASSESSMENT"
    CREATE_HR_PERFORMANCE_ASSESSMENT = "CREATE_HR_PERFORMANCE_ASSESSMENT"
    SUBMIT_HR_PERFORMANCE_ASSESSMENT = "SUBMIT_HR_PERFORMANCE_ASSESSMENT"
    REVIEW_HUMAN_EVALUATION_COMPLETENESS = "REVIEW_HUMAN_EVALUATION_COMPLETENESS"
    MANAGE_EVALUATION_POLICY = "MANAGE_EVALUATION_POLICY"
    CREATE_EMPLOYEE = "CREATE_EMPLOYEE"
    UPDATE_EMPLOYEE_PROFILE = "UPDATE_EMPLOYEE_PROFILE"
    DEACTIVATE_EMPLOYEE = "DEACTIVATE_EMPLOYEE"
    VIEW_TRANSFER_REQUESTS = "VIEW_TRANSFER_REQUESTS"
    REVIEW_TRANSFER_REQUEST = "REVIEW_TRANSFER_REQUEST"
    UPDATE_EMPLOYMENT_RECORDS = "UPDATE_EMPLOYMENT_RECORDS"
    MANAGE_CANDIDATES = "MANAGE_CANDIDATES"
    VIEW_COMPENSATION = "VIEW_COMPENSATION"
    VIEW_GRIEVANCES = "VIEW_GRIEVANCES"
    
    # Transfer workflow permissions
    REQUEST_TRANSFER = "REQUEST_TRANSFER"
    APPROVE_TRANSFER_AS_MANAGER = "APPROVE_TRANSFER_AS_MANAGER"
    APPROVE_TRANSFER_AS_MANAGEMENT = "APPROVE_TRANSFER_AS_MANAGEMENT"
    REVIEW_TRANSFER_HR = "REVIEW_TRANSFER_HR"
    EXECUTE_TRANSFER = "EXECUTE_TRANSFER"

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
    VIEW_INCIDENTS = "VIEW_INCIDENTS"  # read all incidents in accessible projects
    
    # Task Management
    MOVE_TASK = "MOVE_TASK"
    TRANSITION_TASK = "TRANSITION_TASK"
    # Accept a contributor's draft story into the backlog (backlog owners).
    ACCEPT_STORY = "ACCEPT_STORY"
    # QA (CR-002)
    SIGN_OFF_WORK = "SIGN_OFF_WORK"                 # pass/fail work waiting in Review
    MANAGE_TEST_CASES = "MANAGE_TEST_CASES"         # test suites, cases, executions
    VERIFY_DEFECTS = "VERIFY_DEFECTS"               # verify, reopen, close defects
    VIEW_DEFECTS = "VIEW_DEFECTS"                   # defect lists and the Bugs page
    VIEW_CODE_QUALITY = "VIEW_CODE_QUALITY"         # the Code Quality page
    MANAGE_TEST_AUTOMATION = "MANAGE_TEST_AUTOMATION"  # enable/disable the CI test workflow
    # DevOps (CR-003)
    MANAGE_REPOSITORY_LINK = "MANAGE_REPOSITORY_LINK"      # link a project to its GitHub repository
    VIEW_PIPELINES = "VIEW_PIPELINES"                      # CI/CD pipeline runs of own projects
    VIEW_DEPLOYMENTS = "VIEW_DEPLOYMENTS"                  # deployment history of own projects
    ANALYZE_DEPLOYMENT_RISK = "ANALYZE_DEPLOYMENT_RISK"    # rule-based deployment risk analysis
    MANAGE_RISK_CONFIG = "MANAGE_RISK_CONFIG"              # project risk weights (own projects)
    MANAGE_GLOBAL_RISK_CONFIG = "MANAGE_GLOBAL_RISK_CONFIG"  # organisation-wide risk defaults
    CLEAR_RISK_CACHE = "CLEAR_RISK_CACHE"                  # operational cache reset
    # Lead (CR-004)
    SYNC_REPOSITORY_PRS = "SYNC_REPOSITORY_PRS"            # sync every PR of a project's repository
    ANALYZE_SPRINT_RISK = "ANALYZE_SPRINT_RISK"            # rule-based sprint risk analysis
    
    # Code Analysis & Integration
    TRIGGER_CODE_ANALYSIS = "TRIGGER_CODE_ANALYSIS"
    # Rule-based analysis helpers for engineers (were role-name checks).
    ANALYZE_CICD_LOGS = "ANALYZE_CICD_LOGS"
    ANALYZE_PR_RISK = "ANALYZE_PR_RISK"
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
    MANAGE_HR_DESIGNATIONS = "MANAGE_HR_DESIGNATIONS"  # CR-009: assign HR specialisms
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
    # CR-001: Developers work only inside their assigned projects.
    # - CREATE_TASK: sub-tasks for themselves (assignee must be self)
    # - CREATE_STORY: proposes a DRAFT story; a Lead/PM accepts it (ACCEPT_STORY)
    # - CREATE_BUG: reports defects; QA owns verification and closure
    # - CREATE_INCIDENT: reports incidents; DevOps triages them (CR-003)
    # - REQUEST_TRANSFER: their own transfer only
    OrganizationalRole.DEVELOPER: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_CODE_QUALITY,
        Permission.VIEW_DEFECTS,
        Permission.ANALYZE_CICD_LOGS,
        Permission.ANALYZE_PR_RISK,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.TRANSITION_TASK,
        # CRUD permissions
        Permission.CREATE_TASK,
        Permission.CREATE_BUG,
        Permission.CREATE_STORY,
        Permission.CREATE_INCIDENT,  # report only; DevOps triages
        # Integration
        Permission.SYNC_PR,
        # Transfer
        Permission.REQUEST_TRANSFER,
    },

    # CR-004: a Lead manages one team. People data (performance, evaluations,
    # feedback) is team-scoped; work is scoped to the team's projects.
    OrganizationalRole.LEAD: {
        Permission.VIEW_OWN_DATA,
        Permission.SYNC_REPOSITORY_PRS,
        Permission.ANALYZE_SPRINT_RISK,
        Permission.CREATE_SPRINT,
        Permission.VIEW_DEPLOYMENTS,
        Permission.ANALYZE_DEPLOYMENT_RISK,
        Permission.VIEW_PIPELINES,
        Permission.MANAGE_REPOSITORY_LINK,
        Permission.MANAGE_RISK_CONFIG,
        Permission.MANAGE_TEST_AUTOMATION,
        Permission.VIEW_CODE_QUALITY,
        Permission.VIEW_DEFECTS,
        Permission.VIEW_INCIDENTS,
        Permission.ANALYZE_CICD_LOGS,
        Permission.ANALYZE_PR_RISK,
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
        Permission.ACCEPT_STORY,
        # Task management
        Permission.MOVE_TASK,
        Permission.TRANSITION_TASK,
        # AI
        Permission.TRIGGER_AI_EVALUATION,
        # Transfer
        Permission.REQUEST_TRANSFER,
        Permission.APPROVE_TRANSFER_AS_MANAGER,
    },

    OrganizationalRole.PM: {
        Permission.VIEW_OWN_DATA,
        Permission.SYNC_REPOSITORY_PRS,
        Permission.ANALYZE_SPRINT_RISK,
        Permission.MANAGE_REPOSITORY_LINK,
        Permission.MANAGE_RISK_CONFIG,
        Permission.MANAGE_TEST_AUTOMATION,
        Permission.VIEW_DEFECTS,
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
        Permission.ACCEPT_STORY,
        # Task management
        Permission.MOVE_TASK,
        Permission.TRANSITION_TASK,
        # Transfer - PM can initiate and approve but NOT execute organizational transfers
        Permission.REQUEST_TRANSFER,
        Permission.APPROVE_TRANSFER_AS_MANAGER,
        Permission.APPROVE_TRANSFER_AS_MANAGEMENT,
        # Note: EXECUTE_TRANSFER removed - PM manages projects, not permanent team membership
    },

    # CR-002: QA owns testing, the defect lifecycle and sign-off in assigned
    # projects; sees only their own performance.
    OrganizationalRole.QA: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_PIPELINES,
        Permission.SIGN_OFF_WORK,
        Permission.MANAGE_TEST_CASES,
        Permission.VERIFY_DEFECTS,
        Permission.VIEW_DEFECTS,
        Permission.VIEW_CODE_QUALITY,
        Permission.MANAGE_TEST_AUTOMATION,
        Permission.CREATE_INCIDENT,
        Permission.ANALYZE_CICD_LOGS,
        Permission.ANALYZE_PR_RISK,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_QA_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRANSITION_TASK,
        # CRUD permissions
        Permission.CREATE_BUG,
        # Code analysis
        Permission.TRIGGER_CODE_ANALYSIS,
        # Transfer
        Permission.REQUEST_TRANSFER,
    },

    # CR-003: DevOps own pipelines, deployments, repository links and CI in
    # their projects; own performance only.
    OrganizationalRole.DEVOPS: {
        Permission.VIEW_OWN_DATA,
        Permission.MANAGE_REPOSITORY_LINK,
        Permission.VIEW_PIPELINES,
        Permission.VIEW_DEPLOYMENTS,
        Permission.ANALYZE_DEPLOYMENT_RISK,
        Permission.MANAGE_RISK_CONFIG,
        Permission.CLEAR_RISK_CACHE,
        Permission.MANAGE_TEST_AUTOMATION,
        Permission.CREATE_BUG,
        Permission.VIEW_CODE_QUALITY,
        Permission.VIEW_DEFECTS,
        Permission.VIEW_INCIDENTS,
        Permission.ANALYZE_CICD_LOGS,
        Permission.ANALYZE_PR_RISK,
        Permission.VIEW_PROJECT_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.SUBMIT_DEVOPS_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRANSITION_TASK,
        # CRUD permissions
        Permission.CREATE_INCIDENT,
        # Code analysis
        Permission.TRIGGER_CODE_ANALYSIS,
        # Transfer
        Permission.REQUEST_TRANSFER,
    },

    OrganizationalRole.HR: {
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_ORG_CHART,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_PERFORMANCE_OUTCOMES,
        Permission.VIEW_HR_PERFORMANCE_ASSESSMENT,
        Permission.CREATE_HR_PERFORMANCE_ASSESSMENT,
        Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT,
        Permission.REVIEW_HUMAN_EVALUATION_COMPLETENESS,
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        # HR employee management
        Permission.MANAGE_EMPLOYEES,
        Permission.CREATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE_PROFILE,
        Permission.DEACTIVATE_EMPLOYEE,
        # Transfer workflow
        Permission.REQUEST_TRANSFER,
        Permission.VIEW_TRANSFER_REQUESTS,
        Permission.REVIEW_TRANSFER_REQUEST,
        Permission.REVIEW_TRANSFER_HR,
        # CR-006 (Decision 1): HR records an approved transfer (alongside the CEO).
        Permission.EXECUTE_TRANSFER,
        # HR administration
        Permission.VIEW_AUDIT_LOGS,
        # Note: HR does NOT have:
        # - MANAGE_TEAMS (engineering)
        # - ASSIGN_TEAM_LEAD (engineering)
        # - ASSIGN_PROJECT (engineering)
        # - CREATE_TEAM (engineering)
        # - TRIGGER_AI_EVALUATION (restricted)
        # - VIEW_AI_EVALUATION (no raw technical data)
        # - VIEW_ORGANIZATION_DATA (too broad, use VIEW_EMPLOYEE_DIRECTORY)
        # - VIEW_ORGANIZATION_PERFORMANCE (too broad, use VIEW_PERFORMANCE_OUTCOMES)
    },

    # CR-007: executive oversight, approvals and organisation design. Hands-on
    # delivery rights (repository links, CI automation, story acceptance, risk
    # cache and project risk weights) belong to DevOps, QA, Lead and PM.
    OrganizationalRole.CEO: {
        Permission.VIEW_OWN_DATA,
        Permission.MANAGE_GLOBAL_RISK_CONFIG,
        Permission.VIEW_DEFECTS,
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_ALL_DATA,
        Permission.VIEW_ORGANIZATION_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AI_EVALUATION,
        Permission.VIEW_HR_PERFORMANCE_ASSESSMENT,
        Permission.REVIEW_HUMAN_EVALUATION_COMPLETENESS,
        Permission.MANAGE_EVALUATION_POLICY,
        Permission.SUBMIT_CEO_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.TRIGGER_AI_EVALUATION,
        Permission.TRIGGER_BULK_EVALUATION,
        Permission.EXPORT_DATA,
        Permission.VIEW_AUDIT_LOGS,
        # CRUD permissions
        Permission.CREATE_INCIDENT,
        Permission.CREATE_TEAM,
        Permission.MANAGE_TEAMS,
        Permission.ASSIGN_PROJECT,
        Permission.ASSIGN_TEAM_LEAD,
        # Transfer
        Permission.REQUEST_TRANSFER,
        Permission.APPROVE_TRANSFER_AS_MANAGER,
        Permission.APPROVE_TRANSFER_AS_MANAGEMENT,
        Permission.EXECUTE_TRANSFER,
    },
}

# Admin permissions (added on top of role permissions).
# CR-008: admins run the platform (accounts, teams, projects, audit). People
# decisions such as evaluations and evaluation policy stay with the roles
# that own them.
ADMIN_PERMISSIONS: Set[Permission] = {
    Permission.MANAGE_USERS,
    Permission.MANAGE_TEAMS,
    Permission.CREATE_TEAM,
    Permission.MANAGE_EMPLOYEES,
    Permission.ASSIGN_TEAM_LEAD,
    Permission.ASSIGN_PROJECT,
    Permission.VIEW_AUDIT_LOGS,
    Permission.EXPORT_DATA,
    Permission.MANAGE_HR_DESIGNATIONS,  # CR-009 D1-A: admins appoint HR specialists
    # Reserved: no settings or integrations screens check these yet.
    Permission.MANAGE_SETTINGS,
    Permission.MANAGE_INTEGRATIONS,
}


# HR Designation-based permissions
# CR-009: a designation REPLACES the base HR set (least privilege by
# specialism). HR users without one keep the base HR set ("HR generalist").
HR_DESIGNATION_PERMISSIONS: dict[str, Set[Permission]] = {
    "HR_MANAGER": {
        Permission.MANAGE_HR_DESIGNATIONS,  # CR-009 D1-A
        Permission.EXECUTE_TRANSFER,  # CR-006
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_ORG_CHART,
        Permission.VIEW_PERFORMANCE_OUTCOMES,
        Permission.VIEW_HR_PERFORMANCE_ASSESSMENT,
        Permission.CREATE_HR_PERFORMANCE_ASSESSMENT,
        Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT,
        Permission.REVIEW_HUMAN_EVALUATION_COMPLETENESS,
        Permission.CREATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE_PROFILE,
        Permission.DEACTIVATE_EMPLOYEE,
        Permission.VIEW_TRANSFER_REQUESTS,
        Permission.REVIEW_TRANSFER_REQUEST,
        Permission.UPDATE_EMPLOYMENT_RECORDS,
        Permission.MANAGE_CANDIDATES,
        Permission.MANAGE_EMPLOYEES,
        Permission.VIEW_COMPENSATION,
        Permission.VIEW_GRIEVANCES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.REQUEST_TRANSFER,  # CR-009: everyone may request their own transfer
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
        Permission.VIEW_AUDIT_LOGS,  # HR Manager can view HR-relevant audit logs
    },
    "RECRUITER": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.CREATE_EMPLOYEE,
        Permission.MANAGE_CANDIDATES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.REQUEST_TRANSFER,  # CR-009: everyone may request their own transfer
        # No VIEW_AUDIT_LOGS for recruiter
    },
    "HR_OPERATIONS": {
        Permission.EXECUTE_TRANSFER,  # CR-006
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.CREATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE_PROFILE,
        Permission.DEACTIVATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYMENT_RECORDS,
        Permission.VIEW_TRANSFER_REQUESTS,
        Permission.VIEW_AUDIT_LOGS,  # HR Operations can view audit logs
        Permission.MANAGE_EMPLOYEES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.REQUEST_TRANSFER,  # CR-009: everyone may request their own transfer
    },
    "HRBP": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_ORG_CHART,
        Permission.VIEW_PERFORMANCE_OUTCOMES,
        Permission.VIEW_HR_PERFORMANCE_ASSESSMENT,
        Permission.CREATE_HR_PERFORMANCE_ASSESSMENT,
        Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT,
        Permission.VIEW_TRANSFER_REQUESTS,
        Permission.REVIEW_TRANSFER_REQUEST,
        Permission.VIEW_GRIEVANCES,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.REQUEST_TRANSFER,  # CR-009: everyone may request their own transfer
        Permission.SUBMIT_HR_FEEDBACK,
        Permission.VIEW_ROLE_FEEDBACK,
    },
    "EMPLOYEE_RELATIONS": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_GRIEVANCES,
        Permission.VIEW_HR_PERFORMANCE_ASSESSMENT,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.REQUEST_TRANSFER,  # CR-009: everyone may request their own transfer
    },
    "COMPENSATION_BENEFITS": {
        Permission.VIEW_EMPLOYEE_DIRECTORY,
        Permission.VIEW_EMPLOYEE_PROFILE,
        Permission.VIEW_COMPENSATION,
        Permission.VIEW_OWN_DATA,
        Permission.VIEW_OWN_PERFORMANCE,
        Permission.REQUEST_TRANSFER,  # CR-009: everyone may request their own transfer
    },
}


HR_DESIGNATIONS = tuple(HR_DESIGNATION_PERMISSIONS)  # CR-009: allowed designation codes


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
        
        # An HR designation replaces the base HR set; everyone else uses the role set.
        if org_role == OrganizationalRole.HR and designation and designation in HR_DESIGNATION_PERMISSIONS:
            permissions = set(HR_DESIGNATION_PERMISSIONS[designation])
        else:
            permissions = set(ROLE_PERMISSIONS.get(org_role, set()))
    except (ValueError, KeyError):
        return set()

    if is_admin:
        permissions.update(ADMIN_PERMISSIONS)

    return permissions
