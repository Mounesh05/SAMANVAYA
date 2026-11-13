"""
Employee Management API Routes
HR and Admin functionality for managing employees.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, model_validator
from repositories.user_repository import UserRepository
from core.dependencies import get_current_user, require_admin
from core.permissions import Permission, get_user_permissions
from core.security import hash_password, validate_password_strength
from core.audit import log_audit, AuditAction
from domain.schemas.hr_views import EmployeeHRView

router = APIRouter()


class EmployeeCreate(BaseModel):
    """Request model for creating a new employee."""
    employee_id: str
    name: str
    email: EmailStr
    role: str  # CEO|HR|PM|LEAD|DEVELOPER|DEVOPS|QA
    dept: str
    # `password` remains accepted for older API clients. New clients should
    # provide separate credentials so the two authentication factors differ.
    password: Optional[str] = None
    organisation_password: Optional[str] = None
    employee_password: Optional[str] = None
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    is_admin: bool = False

    @model_validator(mode="after")
    def validate_credentials(self):
        organisation_password = self.organisation_password or self.password
        employee_password = self.employee_password or self.password
        if not organisation_password or not employee_password:
            raise ValueError(
                "Organisation and employee passwords are required"
            )
        for label, value in (
            ("Organisation", organisation_password),
            ("Employee", employee_password),
        ):
            valid, message = validate_password_strength(value)
            if not valid:
                raise ValueError(f"{label} password: {message}")
        if self.organisation_password and self.employee_password:
            if self.organisation_password == self.employee_password:
                raise ValueError(
                    "Organisation and employee passwords must be different"
                )
        self.organisation_password = organisation_password
        self.employee_password = employee_password
        return self


class EmployeeUpdate(BaseModel):
    """Request model for updating an employee."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    dept: Optional[str] = None
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class EmployeeResponse(BaseModel):
    """Response model for employee data."""
    employee_id: str
    name: str
    email: str
    role: str
    dept: str
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: Optional[str] = None


@router.post("/", response_model=Union[EmployeeResponse, EmployeeHRView], status_code=201)
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
    
    **HR users receive filtered response without technical fields.**
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    
    if Permission.MANAGE_EMPLOYEES not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only HR or ADMIN can create employees."
        )

    # Policy checks run before any lookup so a forbidden request never reveals
    # whether an employee ID or email already exists.
    # Protect CEO role from creation through employee administration
    if employee.role.upper() == "CEO":
        raise HTTPException(
            status_code=403,
            detail="Cannot create a CEO account through employee administration."
        )

    # Only admins can create admins
    if employee.is_admin and not user.get('is_admin', False):
        raise HTTPException(
            status_code=403,
            detail="Only admins can create admin accounts"
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

        # Create employee document
        employee_doc = {
            "employee_id": employee.employee_id,
            "name": employee.name,
            "email": employee.email,
            "role": employee.role.upper(),
            "dept": employee.dept,
            "organisation_password": hash_password(employee.organisation_password),
            "employee_password": hash_password(employee.employee_password),
            "github_username": employee.github_username,
            "team_id": employee.team_id,
            "is_active": True,
            "is_admin": employee.is_admin,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get('employee_id')
        }
        
        await repo.insert(employee_doc)
        
        # Audit log
        await log_audit(
            action=AuditAction.USER_CREATED,
            actor=user,
            resource_type="employee",
            resource_id=employee.employee_id,
            details={"role": employee.role, "dept": employee.dept}
        )
        
        # Return filtered view for HR users
        if user.get('role', '').upper() == 'HR':
            return EmployeeHRView.from_employee(employee_doc)
        
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
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=Union[List[EmployeeResponse], List[EmployeeHRView]])
async def list_employees(
    role: Optional[str] = Query(None, description="Filter by role"),
    dept: Optional[str] = Query(None, description="Filter by department"),
    team_id: Optional[str] = Query(None, description="Filter by team"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(get_current_user)
):
    """
    List all employees with optional filters.
    
    **Required Permission:** VIEW_ORGANIZATION_DATA (HR, CEO, or ADMIN)
    
    Returns list of employees matching the filters.
    **HR users receive filtered response without technical fields.**
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    
    if not (
        Permission.VIEW_ORGANIZATION_DATA in user_permissions
        or Permission.VIEW_PROJECT_DATA in user_permissions
        or Permission.VIEW_TEAM_DATA in user_permissions
        or Permission.VIEW_EMPLOYEE_DIRECTORY in user_permissions
    ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view employees."
        )
    
    try:
        repo = UserRepository()
        
        # Build filter
        filter_query = {}
        if role:
            filter_query["role"] = role.upper()
        if dept:
            filter_query["dept"] = dept
        if team_id:
            filter_query["team_id"] = team_id
        if is_active is not None:
            filter_query["is_active"] = is_active
        
        # Authorization: LEAD can only see their own team
        if user.get("role", "").upper() == "LEAD":
            filter_query["team_id"] = user["team_id"]
        
        # Get employees
        employees = await repo.find_all(filter_query)
        
        # Return filtered view for HR users
        if user.get('role', '').upper() == 'HR':
            return [EmployeeHRView.from_employee(emp) for emp in employees]
        
        return [
            EmployeeResponse(
                employee_id=emp.get("employee_id", ""),
                name=emp.get("name", "Unknown"),
                email=emp.get("email", ""),
                role=emp.get("role", "DEVELOPER"),
                dept=(
                    "Executive" if emp.get("role", "").upper() == "CEO" and emp.get("dept") in ("Engineering", "", None)
                    else "People & Culture" if emp.get("role", "").upper() == "HR" and emp.get("dept") in ("Engineering", "", None)
                    else emp.get("dept", "Engineering")
                ),
                github_username=emp.get("github_username"),
                team_id=emp.get("team_id"),
                is_active=emp.get("is_active", True),
                is_admin=emp.get("is_admin", False),
                created_at=emp.get("created_at")
            )
            for emp in employees
        ]
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{employee_id}", response_model=Union[EmployeeResponse, EmployeeHRView])
async def get_employee(
    employee_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get employee details by ID.
    
    **Permission Check:**
    - Own data: Any authenticated user
    - Other's data: Requires VIEW_ORGANIZATION_DATA (HR, CEO, ADMIN)
    
    **HR users receive filtered response without technical fields.**
    """
    # Check if viewing own data
    is_own_data = employee_id == user.get('employee_id')
    
    if not is_own_data:
        # Check permission for viewing others' data
        user_permissions = get_user_permissions(
            user.get('role', '').upper(),
            user.get('is_admin', False),
            user.get('designation')
        )
        
        if not (
            Permission.VIEW_ORGANIZATION_DATA in user_permissions
            or Permission.VIEW_EMPLOYEE_DIRECTORY in user_permissions
        ):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to view other employees' data"
            )
    
    try:
        repo = UserRepository()
        employee = await repo.find_by_employee_id(employee_id)
        
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        # Return filtered view for HR users
        if user.get('role', '').upper() == 'HR':
            return EmployeeHRView.from_employee(employee)
        
        return EmployeeResponse(
            employee_id=employee.get("employee_id", ""),
            name=employee.get("name", "Unknown"),
            email=employee.get("email", ""),
            role=employee.get("role", "DEVELOPER"),
            dept=employee.get("dept", "Engineering"),
            github_username=employee.get("github_username"),
            team_id=employee.get("team_id"),
            is_active=employee.get("is_active", True),
            is_admin=employee.get("is_admin", False),
            created_at=employee.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


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
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.MANAGE_EMPLOYEES not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only HR or ADMIN can update employees."
        )
    
    try:
        repo = UserRepository()
        
        # Get existing employee
        employee = await repo.find_by_employee_id(employee_id)
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )

        # Protect CEO account: HR cannot modify the CEO's profile or account
        is_acting_admin = user.get('is_admin', False) or user.get('role', '').upper() == 'CEO'
        if employee.get("role", "").upper() == "CEO" and not is_acting_admin:
            raise HTTPException(
                status_code=403,
                detail="The CEO account cannot be modified by HR."
            )

        # Prevent assigning or elevating to CEO role
        if updates.role is not None and updates.role.upper() == "CEO":
            raise HTTPException(
                status_code=403,
                detail="Cannot assign or promote an employee to CEO through employee administration."
            )

        # HR cannot directly modify engineering team membership
        if updates.team_id is not None and user.get('role', '').upper() == 'HR':
            raise HTTPException(
                status_code=403,
                detail="HR cannot directly modify engineering team membership. Team transfers must be processed through the organizational transfer workflow."
            )
        
        # Build update dict (only include provided fields)
        update_data = {}
        if updates.name is not None:
            update_data["name"] = updates.name
        if updates.email is not None:
            # Check if new email is already taken
            existing = await repo.find_by_email(updates.email)
            if existing and existing.get("employee_id") != employee_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Email {updates.email} is already taken"
                )
            update_data["email"] = updates.email
        if updates.role is not None:
            update_data["role"] = updates.role.upper()
        if updates.dept is not None:
            update_data["dept"] = updates.dept
        if updates.github_username is not None:
            update_data["github_username"] = updates.github_username
        if updates.team_id is not None:
            update_data["team_id"] = updates.team_id
        if updates.is_active is not None and updates.is_active != employee.get("is_active", True):
            # CR-008: activating or deactivating is an admin action with the
            # same protections as DELETE (not the CEO account, not yourself).
            if not user.get('is_admin', False):
                raise HTTPException(
                    status_code=403,
                    detail="Only admins can activate or deactivate accounts"
                )
            if employee.get("role", "").upper() == "CEO":
                raise HTTPException(status_code=403, detail="The CEO account cannot be deactivated.")
            if employee_id == user.get("employee_id"):
                raise HTTPException(status_code=400, detail="You cannot change the active status of your own account.")
            if not updates.is_active:
                await _refuse_if_last_admin(repo, employee)
            update_data["is_active"] = updates.is_active
        
        # Only admins can change admin status
        if updates.is_admin is not None:
            if not user.get('is_admin', False):
                raise HTTPException(
                    status_code=403,
                    detail="Only admins can change admin status"
                )
            if not updates.is_admin:
                await _refuse_if_last_admin(repo, employee)  # CR-008
            update_data["is_admin"] = updates.is_admin
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No updates provided"
            )
        
        # Add metadata
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_data["updated_by"] = user.get('employee_id')
        
        # Update employee
        await repo.update_one(
            {"employee_id": employee_id},
            {"$set": update_data}
        )
        
        # CR-008: record admin-right and active-status changes in the audit log.
        if "is_admin" in update_data and update_data["is_admin"] != bool(employee.get("is_admin", False)):
            await log_audit(
                action=AuditAction.ADMIN_GRANTED if update_data["is_admin"] else AuditAction.ADMIN_REVOKED,
                actor=user, resource_type="employee", resource_id=employee_id,
            )
        if "is_active" in update_data:
            await log_audit(
                action=AuditAction.USER_ACTIVATED if update_data["is_active"] else AuditAction.USER_DEACTIVATED,
                actor=user, resource_type="employee", resource_id=employee_id,
            )

        # Get updated employee
        updated_employee = await repo.find_by_employee_id(employee_id)
        
        return EmployeeResponse(
            employee_id=updated_employee.get("employee_id", ""),
            name=updated_employee.get("name", "Unknown"),
            email=updated_employee.get("email", ""),
            role=updated_employee.get("role", "DEVELOPER"),
            dept=updated_employee.get("dept", "Engineering"),
            github_username=updated_employee.get("github_username"),
            team_id=updated_employee.get("team_id"),
            is_active=updated_employee.get("is_active", True),
            is_admin=updated_employee.get("is_admin", False),
            created_at=updated_employee.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


async def _refuse_if_last_admin(repo: UserRepository, employee: dict) -> None:
    """CR-008: never remove admin rights from, or deactivate, the last active admin."""
    if not employee.get("is_admin") or employee.get("is_active", True) is False:
        return
    others = await repo.col.count_documents({
        "is_admin": True,
        "is_active": {"$ne": False},
        "employee_id": {"$ne": employee.get("employee_id")},
    })
    if others == 0:
        raise HTTPException(
            status_code=409,
            detail="This is the last active admin. Make another employee an admin first.",
        )


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
        
        if employee.get("role", "").upper() == "CEO":
            raise HTTPException(
                status_code=403,
                detail="The CEO account cannot be deactivated."
            )

        if employee_id == user.get("employee_id"):
            raise HTTPException(
                status_code=400,
                detail="You cannot deactivate your own account."
            )

        await _refuse_if_last_admin(repo, employee)  # CR-008

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
        
        # Audit log
        await log_audit(
            action=AuditAction.USER_DEACTIVATED,
            actor=user,
            resource_type="employee",
            resource_id=employee_id
        )
        
        return {"message": f"Employee {employee_id} deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


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
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
