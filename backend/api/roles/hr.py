"""
HR role-specific dashboard endpoints.
Shows: Employee management, capacity, performance, team allocation.
"""

from fastapi import APIRouter, Depends
from core.dependencies import require_roles
from repositories.user_repository import UserRepository

router = APIRouter()


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
    user_repo = UserRepository()
    
    # Get all active employees
    all_users = await user_repo.find_all({"is_active": True})
    
    # Count by role
    role_distribution = {}
    for u in all_users:
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
    user_repo = UserRepository()
    employees = await user_repo.find_all({"is_active": True})
    
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
