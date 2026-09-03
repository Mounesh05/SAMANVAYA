"""
Team Management API Routes
Create and manage teams, assign members and team leads.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from core.database import col
from repositories.user_repository import UserRepository
from core.dependencies import get_current_user, require_admin, require_permission
from core.permissions import Permission, get_user_permissions
from core.audit import log_audit, AuditAction

router = APIRouter()


class TeamCreate(BaseModel):
    """Request model for creating a new team."""
    team_id: str
    name: str
    description: Optional[str] = None
    team_lead_id: Optional[str] = None
    project_ids: Optional[List[str]] = []


class TeamUpdate(BaseModel):
    """Request model for updating a team."""
    name: Optional[str] = None
    description: Optional[str] = None
    team_lead_id: Optional[str] = None
    project_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TeamResponse(BaseModel):
    """Response model for team data."""
    team_id: str
    name: str
    description: Optional[str] = None
    team_lead_id: Optional[str] = None
    team_lead_name: Optional[str] = None
    member_count: int = 0
    project_ids: List[str] = []
    is_active: bool = True
    created_at: Optional[str] = None


class TeamMemberResponse(BaseModel):
    """Response model for team member."""
    employee_id: str
    name: str
    email: str
    role: str
    is_team_lead: bool = False


@router.post("/", response_model=TeamResponse, status_code=201)
async def create_team(
    team: TeamCreate,
    user: dict = Depends(require_permission(Permission.CREATE_TEAM))
):
    """
    Create a new team.
    
    **Required Permission:** CREATE_TEAM (HR role by default)
    
    Creates a team with:
    - Unique team ID and name
    - Optional team lead assignment
    - Optional project associations
    """
    try:
        teams_col = col("teams")
        
        # Check if team_id already exists
        existing = await teams_col.find_one({"team_id": team.team_id})
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Team ID {team.team_id} already exists"
            )
        
        # If team lead specified, verify they exist
        team_lead_name = None
        if team.team_lead_id:
            user_repo = UserRepository()
            lead = await user_repo.find_by_employee_id(team.team_lead_id)
            if not lead:
                raise HTTPException(
                    status_code=400,
                    detail=f"Team lead {team.team_lead_id} not found"
                )
            team_lead_name = lead.get("name", "Unknown")
            
            # Update the team lead's record
            await user_repo.update_one(
                {"employee_id": team.team_lead_id},
                {"$set": {"team_id": team.team_id}}
            )
        
        # Create team document
        team_doc = {
            "team_id": team.team_id,
            "name": team.name,
            "description": team.description,
            "team_lead_id": team.team_lead_id,
            "project_ids": team.project_ids or [],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get('employee_id')
        }
        
        await teams_col.insert_one(team_doc)
        
        # Audit log
        await log_audit(
            action=AuditAction.TEAM_CREATED,
            actor=user,
            resource_type="team",
            resource_id=team.team_id,
            details={"name": team.name}
        )
        
        return TeamResponse(
            team_id=team.team_id,
            name=team.name,
            description=team.description,
            team_lead_id=team.team_lead_id,
            team_lead_name=team_lead_name,
            member_count=1 if team.team_lead_id else 0,
            project_ids=team.project_ids or [],
            is_active=True,
            created_at=team_doc["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create team: {str(e)}")


@router.get("/", response_model=List[TeamResponse])
async def list_teams(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    user: dict = Depends(get_current_user)
):
    """
    List all teams.
    
    **Required Permission:** VIEW_ORGANIZATION_DATA (HR, CEO, or ADMIN)
    
    Returns list of teams with member counts.
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.VIEW_ORGANIZATION_DATA not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to list teams"
        )
    
    try:
        teams_col = col("teams")
        user_repo = UserRepository()
        
        # Build filter
        filter_query = {}
        if is_active is not None:
            filter_query["is_active"] = is_active
        
        # Get teams
        teams = []
        async for team_doc in teams_col.find(filter_query):
            # Get team lead name
            team_lead_name = None
            if team_doc.get("team_lead_id"):
                lead = await user_repo.find_by_employee_id(team_doc["team_lead_id"])
                if lead:
                    team_lead_name = lead.get("name")
            
            # Count team members
            members = await user_repo.find_all({"team_id": team_doc["team_id"]})
            
            teams.append(TeamResponse(
                team_id=team_doc["team_id"],
                name=team_doc["name"],
                description=team_doc.get("description"),
                team_lead_id=team_doc.get("team_lead_id"),
                team_lead_name=team_lead_name,
                member_count=len(members),
                project_ids=team_doc.get("project_ids", []),
                is_active=team_doc.get("is_active", True),
                created_at=team_doc.get("created_at")
            ))
        
        return teams
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list teams: {str(e)}")


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get team details by ID.
    
    **Permission Check:**
    - Own team: Requires VIEW_TEAM_DATA (LEAD)
    - Any team: Requires VIEW_ORGANIZATION_DATA (HR, CEO, ADMIN)
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    is_own_team = team_id == user.get('team_id')
    
    if not is_own_team and Permission.VIEW_ORGANIZATION_DATA not in user_permissions:
        if Permission.VIEW_TEAM_DATA not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to view this team"
            )
    
    try:
        teams_col = col("teams")
        user_repo = UserRepository()
        
        team_doc = await teams_col.find_one({"team_id": team_id})
        
        if not team_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Team {team_id} not found"
            )
        
        # Get team lead name
        team_lead_name = None
        if team_doc.get("team_lead_id"):
            lead = await user_repo.find_by_employee_id(team_doc["team_lead_id"])
            if lead:
                team_lead_name = lead.get("name")
        
        # Count team members
        members = await user_repo.find_all({"team_id": team_id})
        
        return TeamResponse(
            team_id=team_doc["team_id"],
            name=team_doc["name"],
            description=team_doc.get("description"),
            team_lead_id=team_doc.get("team_lead_id"),
            team_lead_name=team_lead_name,
            member_count=len(members),
            project_ids=team_doc.get("project_ids", []),
            is_active=team_doc.get("is_active", True),
            created_at=team_doc.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get team: {str(e)}")


@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
async def get_team_members(
    team_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get all members of a team.
    
    **Permission Check:**
    - Own team: Requires VIEW_TEAM_DATA (LEAD)
    - Any team: Requires VIEW_ORGANIZATION_DATA (HR, CEO, ADMIN)
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    is_own_team = team_id == user.get('team_id')
    
    if not is_own_team and Permission.VIEW_ORGANIZATION_DATA not in user_permissions:
        if Permission.VIEW_TEAM_DATA not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to view team members"
            )
    
    try:
        teams_col = col("teams")
        user_repo = UserRepository()
        
        # Verify team exists
        team_doc = await teams_col.find_one({"team_id": team_id})
        if not team_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Team {team_id} not found"
            )
        
        # Get team members
        members = await user_repo.find_all({"team_id": team_id, "is_active": True})
        
        team_lead_id = team_doc.get("team_lead_id")
        
        return [
            TeamMemberResponse(
                employee_id=member.get("employee_id", ""),
                name=member.get("name", "Unknown"),
                email=member.get("email", ""),
                role=member.get("role", "DEVELOPER"),
                is_team_lead=(member.get("employee_id") == team_lead_id)
            )
            for member in members
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get team members: {str(e)}")


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    updates: TeamUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update team information.
    
    **Permission Check:**
    - HR/ADMIN: Full edit (name, description, lead, members, active status)
    - LEAD: Technical scope only (name, description) for own team
    """
    user_role = user.get('role', '').upper()
    user_permissions = get_user_permissions(
        user_role,
        user.get('is_admin', False)
    )
    
    is_own_team = team_id == user.get('team_id')
    is_lead = user_role == 'LEAD'
    is_hr_admin = Permission.MANAGE_TEAMS in user_permissions
    
    # LEAD can only edit name/description on own team
    if is_lead and is_own_team:
        # Restrict LEAD to technical scope fields only
        blocked_fields = {'team_lead_id', 'project_ids', 'is_active'}
        if any(getattr(updates, f, None) is not None for f in blocked_fields):
            raise HTTPException(
                status_code=403,
                detail="LEAD can only update team name and description. Contact HR for membership/lead changes."
            )
    elif not is_hr_admin:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to update teams"
        )
    
    try:
        teams_col = col("teams")
        user_repo = UserRepository()
        
        # Verify team exists
        team_doc = await teams_col.find_one({"team_id": team_id})
        if not team_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Team {team_id} not found"
            )
        
        # Build update dict
        update_data = {}
        if updates.name is not None:
            update_data["name"] = updates.name
        if updates.description is not None:
            update_data["description"] = updates.description
        if updates.project_ids is not None:
            update_data["project_ids"] = updates.project_ids
        if updates.is_active is not None:
            update_data["is_active"] = updates.is_active
        
        # Handle team lead change
        if updates.team_lead_id is not None:
            # Verify new team lead exists
            new_lead = await user_repo.find_by_employee_id(updates.team_lead_id)
            if not new_lead:
                raise HTTPException(
                    status_code=400,
                    detail=f"Team lead {updates.team_lead_id} not found"
                )
            
            # Remove old team lead designation if exists
            old_lead_id = team_doc.get("team_lead_id")
            if old_lead_id:
                await user_repo.update_one(
                    {"employee_id": old_lead_id},
                    {"$unset": {"team_lead_of": ""}}
                )
            
            # Set new team lead
            await user_repo.update_one(
                {"employee_id": updates.team_lead_id},
                {"$set": {"team_id": team_id, "team_lead_of": team_id}}
            )
            
            update_data["team_lead_id"] = updates.team_lead_id
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No updates provided"
            )
        
        # Add metadata
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_data["updated_by"] = user.get('employee_id')
        
        # Update team
        await teams_col.update_one(
            {"team_id": team_id},
            {"$set": update_data}
        )
        
        # Get updated team
        updated_team = await teams_col.find_one({"team_id": team_id})
        
        # Get team lead name
        team_lead_name = None
        if updated_team.get("team_lead_id"):
            lead = await user_repo.find_by_employee_id(updated_team["team_lead_id"])
            if lead:
                team_lead_name = lead.get("name")
        
        # Count members
        members = await user_repo.find_all({"team_id": team_id})
        
        return TeamResponse(
            team_id=updated_team["team_id"],
            name=updated_team["name"],
            description=updated_team.get("description"),
            team_lead_id=updated_team.get("team_lead_id"),
            team_lead_name=team_lead_name,
            member_count=len(members),
            project_ids=updated_team.get("project_ids", []),
            is_active=updated_team.get("is_active", True),
            created_at=updated_team.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update team: {str(e)}")


@router.post("/{team_id}/members/{employee_id}")
async def add_team_member(
    team_id: str,
    employee_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Add a member to a team.
    
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
            detail="Insufficient permissions to assign team members"
        )
    
    try:
        teams_col = col("teams")
        user_repo = UserRepository()
        
        # Verify team exists
        team_doc = await teams_col.find_one({"team_id": team_id})
        if not team_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Team {team_id} not found"
            )
        
        # Verify employee exists
        employee = await user_repo.find_by_employee_id(employee_id)
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        # Add employee to team
        await user_repo.update_one(
            {"employee_id": employee_id},
            {
                "$set": {
                    "team_id": team_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user.get('employee_id')
                }
            }
        )
        
        return {"message": f"Employee {employee_id} added to team {team_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add team member: {str(e)}")


@router.delete("/{team_id}/members/{employee_id}")
async def remove_team_member(
    team_id: str,
    employee_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Remove a member from a team.
    
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
            detail="Insufficient permissions to remove team members"
        )
    
    try:
        user_repo = UserRepository()
        
        # Verify employee exists and is in this team
        employee = await user_repo.find_by_employee_id(employee_id)
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        if employee.get("team_id") != team_id:
            raise HTTPException(
                status_code=400,
                detail=f"Employee {employee_id} is not in team {team_id}"
            )
        
        # Remove from team
        await user_repo.update_one(
            {"employee_id": employee_id},
            {
                "$unset": {"team_id": ""},
                "$set": {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user.get('employee_id')
                }
            }
        )
        
        return {"message": f"Employee {employee_id} removed from team {team_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove team member: {str(e)}")


@router.post("/{team_id}/assign-lead")
async def assign_team_lead(
    team_id: str,
    employee_id: str = Body(..., embed=True),
    user: dict = Depends(get_current_user)
):
    """
    Assign or change team lead.
    
    **Required Permission:** ASSIGN_TEAM_LEAD (ADMIN or HR)
    """
    # Check permission
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.ASSIGN_TEAM_LEAD not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to assign team leads"
        )
    
    try:
        teams_col = col("teams")
        user_repo = UserRepository()
        
        # Verify team exists
        team_doc = await teams_col.find_one({"team_id": team_id})
        if not team_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Team {team_id} not found"
            )
        
        # Verify employee exists
        employee = await user_repo.find_by_employee_id(employee_id)
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found"
            )
        
        # Remove old team lead designation
        old_lead_id = team_doc.get("team_lead_id")
        if old_lead_id:
            await user_repo.update_one(
                {"employee_id": old_lead_id},
                {"$unset": {"team_lead_of": ""}}
            )
        
        # Update team with new lead
        await teams_col.update_one(
            {"team_id": team_id},
            {
                "$set": {
                    "team_lead_id": employee_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user.get('employee_id')
                }
            }
        )
        
        # Update employee record
        await user_repo.update_one(
            {"employee_id": employee_id},
            {
                "$set": {
                    "team_id": team_id,
                    "team_lead_of": team_id,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Audit log
        await log_audit(
            action=AuditAction.TEAM_LEAD_ASSIGNED,
            actor=user,
            resource_type="team",
            resource_id=team_id,
            details={"new_lead_id": employee_id}
        )
        
        return {"message": f"Employee {employee_id} assigned as team lead of {team_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign team lead: {str(e)}")
