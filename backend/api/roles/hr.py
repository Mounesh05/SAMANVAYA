from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from core.dependencies import get_current_user_optional
from repositories.user_repository import UserRepository
from core.database import get_db

router = APIRouter()


@router.get("/dashboard")
async def hr_dashboard(user: Optional[dict] = Depends(get_current_user_optional)):
    """
    HR dashboard - People and capacity management.
    """
    user_repo = UserRepository()
    all_users = await user_repo.find_all({"is_active": True})
    
    role_distribution: Dict[str, int] = {}
    for u in all_users:
        role = u.get("role", "UNKNOWN")
        role_distribution[role] = role_distribution.get(role, 0) + 1
    
    user_name = user.get("name", "Priya Sharma") if user else "Priya Sharma"
    return {
        "role": "HR",
        "name": user_name,
        "summary": {
            "total_employees": len(all_users),
            "role_distribution": role_distribution,
        },
        "employees": all_users,
    }


@router.get("/employees")
async def list_employees(
    user: Optional[dict] = Depends(get_current_user_optional),
    company_id: Optional[str] = Query(None)
):
    """Get all employees with team and performance details."""
    db = get_db()
    query = {"is_active": True}
    if company_id:
        query["company_id"] = company_id
    employees = await db.users.find(query).to_list(length=100)
    for emp in employees:
        emp["_id"] = str(emp["_id"])
    return {
        "employees": employees,
        "total": len(employees),
    }


@router.get("/organization")
async def organization_overview(user: Optional[dict] = Depends(get_current_user_optional)):
    """Get organization overview for performance & HR dashboards."""
    db = get_db()
    users = await db.users.find({"is_active": True}).to_list(length=100)
    teams = await db.teams.find({}).to_list(length=100)
    companies = await db.companies.find({}).to_list(length=20)
    
    for u in users:
        u["_id"] = str(u["_id"])
    for t in teams:
        t["_id"] = str(t["_id"])
    for c in companies:
        c["_id"] = str(c["_id"])

    return {
        "companies": companies,
        "teams": teams,
        "total_employees": len(users),
        "departments": list(set(u.get("dept", "Engineering") for u in users if u.get("dept"))),
        "users": users
    }


@router.get("/teams")
async def hr_teams(
    user: Optional[dict] = Depends(get_current_user_optional),
    company_id: Optional[str] = Query(None)
):
    """Get all teams with assigned members."""
    db = get_db()
    query = {}
    if company_id:
        query["company_id"] = company_id
    teams = await db.teams.find(query).to_list(length=50)
    for t in teams:
        t["_id"] = str(t["_id"])
    return teams


@router.get("/capacity")
async def team_capacity(user: Optional[dict] = Depends(get_current_user_optional)):
    """Get team capacity and allocation."""
    db = get_db()
    teams = await db.teams.find({}).to_list(length=50)
    for t in teams:
        t["_id"] = str(t["_id"])
    return {
        "teams": teams,
        "message": "Team capacity analysis"
    }

