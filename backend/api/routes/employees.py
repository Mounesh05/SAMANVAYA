"""
Employee Management API Routes
HR and Admin functionality for managing employees.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr
from repositories.user_repository import UserRepository
from core.dependencies import get_current_user, require_admin, get_current_user_optional
from core.permissions import Permission, get_user_permissions
from core.security import hash_password
from core.database import col

router = APIRouter()


class EmployeeCreate(BaseModel):
    """Request model for creating a new employee."""
    employee_id: str
    name: str
    email: EmailStr
    role: str  # CEO|HR|PM|LEAD|DEVELOPER|DEVOPS|QA
    dept: str
    password: str  # Will be hashed
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    is_admin: bool = False


class EmployeeUpdate(BaseModel):
    """Request model for updating an employee."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    dept: Optional[str] = None
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    avatar: Optional[str] = None
    status: Optional[str] = None
    perfScore: Optional[float] = None
    behaviour: Optional[float] = None
    risk: Optional[str] = None
    sprintContrib: Optional[str] = None
    projects: Optional[List[str]] = None
    alignment: Optional[float] = None
    onTime: Optional[float] = None
    rejection: Optional[float] = None
    behaviourScores: Optional[dict] = None
    riskData: Optional[dict] = None
    promotion: Optional[dict] = None
    alignmentHistory: Optional[List[dict]] = None
    sprintTrend: Optional[List[dict]] = None
    managerComment: Optional[str] = None


class EmployeeResponse(BaseModel):
    """Response model for employee data with rich dashboard fields."""
    employee_id: str
    id: Optional[str] = None
    name: str
    email: str
    role: str
    dept: str
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    org_id: Optional[str] = None
    company_id: Optional[str] = None
    perfScore: Optional[float] = 85.0
    behaviour: Optional[float] = 8.5
    risk: Optional[str] = "Low"
    sprintContrib: Optional[str] = "20 SP"
    projects: Optional[List[str]] = []
    status: Optional[str] = "Active"
    avatar: Optional[str] = None
    transferred_by: Optional[str] = None
    transfer_reason: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    created_at: Optional[str] = None
    alignment: Optional[float] = 88.0
    onTime: Optional[float] = 92.0
    rejection: Optional[float] = 5.0
    behaviourScores: Optional[dict] = None
    riskData: Optional[dict] = None
    promotion: Optional[dict] = None
    alignmentHistory: Optional[List[dict]] = None
    sprintTrend: Optional[List[dict]] = None
    managerComment: Optional[str] = None


@router.post("/", response_model=EmployeeResponse, status_code=201)
async def create_employee(
    employee: EmployeeCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create a new employee.
    
    **Required Permission:** MANAGE_EMPLOYEES (HR or ADMIN)
    
    Creates employee account with:
    - Basic information (name, email, role, dept)
    - Authentication credentials (password is hashed)
    - Optional GitHub username for integration
    - Optional team assignment
    - Admin status (can only be set by existing admins)
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.MANAGE_EMPLOYEES not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only HR or ADMIN can create employees."
        )
    
    try:
        repo = UserRepository()
        
        # Check if employee_id or email already exists
        existing = await repo.find_by_employee_id(employee.employee_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Employee ID {employee.employee_id} already exists"
            )
        
        existing = await repo.find_by_email(employee.email)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Email {employee.email} already exists"
            )
        
        # Only admins can create admins
        if employee.is_admin and not user.get('is_admin', False):
            raise HTTPException(
                status_code=403,
                detail="Only admins can create admin accounts"
            )
        
        # Hash password
        password_hash = hash_password(employee.password)
        
        # Create employee document
        employee_doc = {
            "employee_id": employee.employee_id,
            "name": employee.name,
            "email": employee.email,
            "role": employee.role.upper(),
            "dept": employee.dept,
            "organisation_password": password_hash,
            "employee_password": password_hash,
            "github_username": employee.github_username,
            "team_id": employee.team_id,
            "is_active": True,
            "is_admin": employee.is_admin,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get('employee_id')
        }
        
        await repo.insert(employee_doc)
        
        return EmployeeResponse(
            employee_id=employee.employee_id,
            name=employee.name,
            email=employee.email,
            role=employee.role.upper(),
            dept=employee.dept,
            github_username=employee.github_username,
            team_id=employee.team_id,
            is_active=True,
            is_admin=employee.is_admin,
            created_at=employee_doc["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create employee: {str(e)}")


@router.get("", response_model=List[EmployeeResponse])
@router.get("/", response_model=List[EmployeeResponse], include_in_schema=False)
async def list_employees(
    role: Optional[str] = Query(None, description="Filter by role"),
    dept: Optional[str] = Query(None, description="Filter by department"),
    team_id: Optional[str] = Query(None, description="Filter by team"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=1000),
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    List all employees directly from MongoDB with optional filters.
    """
    try:
        filter_query = {}
        if role and role != "All":
            filter_query["role"] = role.upper()
        if dept and dept != "All":
            filter_query["dept"] = dept
        if team_id and team_id != "All":
            filter_query["team_id"] = team_id
        if is_active is not None:
            filter_query["is_active"] = is_active
        
        employees = await col("users").find(filter_query, {"_id": 0}).limit(limit).to_list(limit)
        
        results = []
        for emp in employees:
            results.append(EmployeeResponse(
                employee_id=emp.get("employee_id", ""),
                id=str(emp.get("employee_id", "")),
                name=emp.get("name", "Unknown"),
                email=emp.get("email", ""),
                role=emp.get("role", "DEVELOPER"),
                dept=emp.get("dept", "Engineering"),
                github_username=emp.get("github_username"),
                team_id=emp.get("team_id"),
                team_name=emp.get("team_name") or ("Core Engineering Squad" if emp.get("team_id") == "team-01" else "Engineering Team"),
                org_id=emp.get("org_id", "ORG-001"),
                company_id=emp.get("company_id", "ORG-001"),
                perfScore=float(emp.get("perfScore", 85.0)),
                behaviour=float(emp.get("behaviour", 8.5)),
                risk=emp.get("risk", "Low"),
                sprintContrib=emp.get("sprintContrib", "20 SP"),
                projects=emp.get("projects") or ["Samanvaya AI Platform"],
                status=emp.get("status", "Active"),
                avatar=emp.get("avatar") or "".join([w[0] for w in emp.get("name", "U").split()][:2]).upper(),
                transferred_by=emp.get("transferred_by"),
                transfer_reason=emp.get("transfer_reason"),
                is_active=emp.get("is_active", True),
                is_admin=emp.get("is_admin", False),
                created_at=emp.get("created_at")
            ))
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list employees: {str(e)}")


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: str,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Get employee details by ID from MongoDB.
    """
    try:
        employee = await col("users").find_one(
            {"$or": [{"employee_id": employee_id}, {"id": employee_id}]},
            {"_id": 0}
        )
        
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        perf_score = float(employee.get("perfScore", 85.0))
        behaviour_score = float(employee.get("behaviour", 8.5))
        risk_level = employee.get("risk", "Low")
        
        default_b_val = min(10, max(1, round(behaviour_score)))
        default_behaviour_scores = {
            "communication": default_b_val,
            "ownership": default_b_val,
            "teamwork": default_b_val,
            "leadership": max(4, default_b_val - 1),
            "discipline": default_b_val
        }
        default_risk_data = {
            "overloadFreq": 4 if risk_level == "High" else 2 if risk_level == "Medium" else 1,
            "escalationInvolvement": 3 if risk_level == "High" else 1 if risk_level == "Medium" else 0,
            "perfDrop": -6.8 if risk_level == "High" else -2.4 if risk_level == "Medium" else 2.1
        }
        default_promotion = {
            "eligible": perf_score >= 80 and risk_level != "High",
            "aiVerdict": "Strongly Recommend" if perf_score >= 88 else "Recommend" if perf_score >= 78 else "Not Recommended",
            "managerReview": "Approved" if perf_score >= 85 else "Pending" if perf_score >= 75 else "Hold",
            "finalDecision": "Promoted" if perf_score >= 88 else "Pending" if perf_score >= 78 else "Hold",
            "lastReview": "Sprint 24 Cycle Review",
            "reviewedBy": "Engineering Lead"
        }

        return EmployeeResponse(
            employee_id=employee.get("employee_id", ""),
            id=str(employee.get("employee_id", "")),
            name=employee.get("name", "Unknown"),
            email=employee.get("email", ""),
            role=employee.get("role", "DEVELOPER"),
            dept=employee.get("dept", "Engineering"),
            github_username=employee.get("github_username"),
            team_id=employee.get("team_id"),
            team_name=employee.get("team_name") or "Core Engineering Squad",
            org_id=employee.get("org_id", "ORG-001"),
            company_id=employee.get("company_id", "ORG-001"),
            perfScore=perf_score,
            behaviour=behaviour_score,
            risk=risk_level,
            sprintContrib=employee.get("sprintContrib", "20 SP"),
            projects=employee.get("projects") or ["Samanvaya AI Platform"],
            status=employee.get("status", "Active"),
            avatar=employee.get("avatar") or "".join([w[0] for w in employee.get("name", "U").split()][:2]).upper(),
            transferred_by=employee.get("transferred_by"),
            transfer_reason=employee.get("transfer_reason"),
            is_active=employee.get("is_active", True),
            is_admin=employee.get("is_admin", False),
            created_at=employee.get("created_at"),
            alignment=float(employee.get("alignment", round(perf_score * 0.98))),
            onTime=float(employee.get("onTime", min(99.0, round(perf_score * 1.04)))),
            rejection=float(employee.get("rejection", 12.0 if perf_score < 75 else 6.0 if perf_score < 85 else 3.0)),
            behaviourScores=employee.get("behaviourScores") or default_behaviour_scores,
            riskData=employee.get("riskData") or default_risk_data,
            promotion=employee.get("promotion") or default_promotion,
            alignmentHistory=employee.get("alignmentHistory"),
            sprintTrend=employee.get("sprintTrend"),
            managerComment=employee.get("managerComment")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get employee: {str(e)}")


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: str,
    updates: EmployeeUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update employee information.
    
    **Required Permission:** MANAGE_EMPLOYEES (HR or ADMIN)
    
    Updates employee details. Only admins can change admin status.
    """
    # Check permission: User can update their own profile (with alias & email support), or HR/ADMIN can update anyone
    alias_map = {
        "EMP-DEV-001": "EMP-001", "EMP-001": "EMP-DEV-001",
        "EMP-LEAD-001": "EMP-002", "EMP-002": "EMP-LEAD-001",
        "EMP-PM-001": "EMP-003", "EMP-003": "EMP-PM-001",
        "EMP-QA-001": "EMP-004", "EMP-004": "EMP-QA-001",
        "EMP-OPS-001": "EMP-005", "EMP-005": "EMP-OPS-001",
        "EMP-HR-001": "EMP-006", "EMP-006": "EMP-HR-001",
        "EMP-CEO-001": "EMP-007", "EMP-007": "EMP-CEO-001",
    }
    user_emp_id = (user.get("employee_id") or user.get("id") or "").upper()
    req_emp_id = employee_id.upper()
    is_self = (
        user_emp_id == req_emp_id or
        alias_map.get(user_emp_id) == req_emp_id or
        alias_map.get(req_emp_id) == user_emp_id
    )

    # Also resolve employee from MongoDB by ID or alias
    employee = await col("users").find_one(
        {"$or": [
            {"employee_id": employee_id},
            {"id": employee_id},
            {"employee_id": alias_map.get(employee_id, employee_id)}
        ]},
        {"_id": 0}
    )
    if employee:
        user_email = (user.get("email") or "").strip().lower()
        target_email = (employee.get("email") or "").strip().lower()
        if user_email and target_email and user_email == target_email:
            is_self = True

    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    has_manage = Permission.MANAGE_EMPLOYEES in user_permissions
    
    if not is_self and not has_manage:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only HR, ADMIN, or the employee themselves can update this profile."
        )
    
    try:
        repo = UserRepository()
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        # Build update dict (only include provided fields)
        update_data = {}
        for field in [
            "name", "role", "dept", "github_username", "team_id", "team_name",
            "is_active", "avatar", "status", "perfScore", "behaviour", "risk",
            "sprintContrib", "projects", "alignment", "onTime", "rejection",
            "behaviourScores", "riskData", "promotion", "alignmentHistory",
            "sprintTrend", "managerComment"
        ]:
            val = getattr(updates, field, None)
            if val is not None:
                if field == "role":
                    val = val.upper()
                update_data[field] = val

        if updates.email is not None:
            # Check if new email is already taken
            existing = await repo.find_by_email(updates.email)
            if existing and existing.get("employee_id") != employee_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Email {updates.email} is already taken"
                )
            update_data["email"] = updates.email

        # Only admins can change admin status
        if updates.is_admin is not None:
            if not user.get('is_admin', False):
                raise HTTPException(
                    status_code=403,
                    detail="Only admins can change admin status"
                )
            update_data["is_admin"] = updates.is_admin
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No updates provided"
            )
        
        # Add metadata
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_data["updated_by"] = user.get('employee_id')
        
        # Update employee safely in MongoDB
        target_ids = list({employee_id, alias_map.get(employee_id, employee_id)})
        await col("users").update_many(
            {"$or": [{"employee_id": {"$in": target_ids}}, {"id": {"$in": target_ids}}]},
            {"$set": update_data}
        )
        
        return await get_employee(employee.get("employee_id") or employee_id, user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update employee: {str(e)}")


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: str,
    user: dict = Depends(require_admin())
):
    """
    Delete (deactivate) an employee.
    
    **Required Permission:** ADMIN only
    
    This actually deactivates the employee rather than deleting.
    Use for offboarding employees.
    """
    try:
        repo = UserRepository()
        
        # Get employee
        employee = await repo.find_by_employee_id(employee_id)
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        # Deactivate instead of delete
        await repo.update_one(
            {"employee_id": employee_id},
            {
                "$set": {
                    "is_active": False,
                    "deactivated_at": datetime.now(timezone.utc).isoformat(),
                    "deactivated_by": user.get('employee_id')
                }
            }
        )
        
        return {"message": f"Employee {employee_id} deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete employee: {str(e)}")


@router.post("/{employee_id}/assign-team")
async def assign_employee_to_team(
    employee_id: str,
    team_id: str = Body(..., embed=True),
    user: dict = Depends(get_current_user)
):
    """
    Assign an employee to a team.
    
    **Required Permission:** ASSIGN_PROJECT (ADMIN or HR)
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.ASSIGN_PROJECT not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to assign teams"
        )
    
    try:
        repo = UserRepository()
        
        # Update employee's team
        result = await repo.update_one(
            {"employee_id": employee_id},
            {
                "$set": {
                    "team_id": team_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user.get('employee_id')
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        return {"message": f"Employee {employee_id} assigned to team {team_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign team: {str(e)}")
