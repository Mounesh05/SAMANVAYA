"""
HR role-specific dashboard endpoints.
Shows: Employee management, capacity, performance, team allocation.
"""

from fastapi import APIRouter, Depends
from core.dependencies import require_roles
from repositories.user_repository import UserRepository
from domain.schemas.hr_views import EmployeeHRView

router = APIRouter()


async def _employees_for_hr(user: dict) -> list[dict]:
    """Apply tenant scope before counting, then serialize only HR-safe fields."""
    scope = {"org_id": user["org_id"]} if user.get("org_id") else {"employee_id": user["employee_id"]}
    employees = await UserRepository().find_all({"is_active": True, **scope})
    return [EmployeeHRView.from_employee(employee).model_dump(mode="json") for employee in employees]


@router.get("/dashboard")
async def hr_dashboard(user: dict = Depends(require_roles("HR"))):
    """
    HR dashboard - People and capacity management.
    
    Returns:
        - Employee overview
        - Team capacity
        - Performance trends
        - Resource allocation
    """
    all_users = await _employees_for_hr(user)
    
    # Count by role
    role_distribution = {}
    for u in all_users:
        if u.get("role", "").upper() == "CEO" and u.get("dept") in ("Engineering", "", None):
            u["dept"] = "Executive"
        elif u.get("role", "").upper() == "HR" and u.get("dept") in ("Engineering", "", None):
            u["dept"] = "People & Culture"
        role = u.get("role", "UNKNOWN")
        role_distribution[role] = role_distribution.get(role, 0) + 1
    
    return {
        "role": "HR",
        "name": user["name"],
        "summary": {
            "total_employees": len(all_users),
            "role_distribution": role_distribution,
        },
        "employees": all_users,
    }


@router.get("/employees")
async def list_employees(user: dict = Depends(require_roles("HR"))):
    """Get all employees."""
    employees = await _employees_for_hr(user)
    
    return {
        "employees": employees,
        "total": len(employees),
    }


@router.get("/capacity")
async def team_capacity(user: dict = Depends(require_roles("HR"))):
    """Get team capacity and allocation."""
    return {
        "teams": [],
        "message": "Team capacity analysis"
    }
