"""
Project API endpoints.
Provides complete CRUD operations for projects, fully dynamic with MongoDB,
and transparent role-based audit tracking.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Optional, List
from datetime import datetime, timezone
from core.database import col
from core.dependencies import get_current_user_optional

router = APIRouter()


@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict], include_in_schema=False)
async def list_projects(
    org_id: Optional[str] = Query(None, description="Organization or Company ID"),
    company_id: Optional[str] = Query(None, description="Company ID"),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    List all active projects directly from MongoDB.
    Optionally filter by company/org ID.
    """
    try:
        query = {}
        target_org = company_id or org_id
        if target_org:
            query["$or"] = [{"org_id": target_org}, {"company_id": target_org}]
            
        projects = await col("projects").find(query, {"_id": 0}).to_list(100)
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """Get project by ID from MongoDB."""
    project = await col("projects").find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", status_code=201)
@router.post("/", status_code=201, include_in_schema=False)
async def create_project(
    data: dict = Body(...),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Create a new project in MongoDB with transparent role attribution.
    Can be created by CEO, HR, PM, etc.
    """
    try:
        # Determine actor
        if user and user.get("name") and user.get("role"):
            actor = f"{user['name']} ({user['role']})"
            actor_role = user["role"]
        else:
            actor = data.get("created_by") or "Alexander Sterling (CEO)"
            actor_role = "CEO" if "CEO" in actor else "HR" if "HR" in actor else "PM"

        # Generate ID if not present
        count = await col("projects").count_documents({})
        new_id = data.get("id") or f"PRJ-{str(count + 1).zfill(2)}"
        
        project_doc = {
            "id": new_id,
            "name": data.get("name", "New Project"),
            "key": data.get("key") or new_id.replace("PRJ-", "PRJ"),
            "description": data.get("description", ""),
            "client": data.get("client", "Internal Enterprise"),
            "org_id": data.get("org_id") or data.get("company_id") or "ORG-001",
            "company_id": data.get("company_id") or data.get("org_id") or "ORG-001",
            "company_name": data.get("company_name", "Samanvaya Inc."),
            "sprint": data.get("sprint", "Sprint 24"),
            "assignedPM": data.get("assignedPM", "Rachel Zane"),
            "team_ids": data.get("team_ids", ["team-01"]),
            "team_names": data.get("team_names", ["Core Engineering Squad"]),
            "members": int(data.get("members") or 5),
            "createdDate": data.get("createdDate") or datetime.now().strftime("%b %d, %Y"),
            "status": data.get("status", "Active"),
            "created_by": actor,
            "updated_by": actor,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await col("projects").update_one({"id": new_id}, {"$set": project_doc}, upsert=True)

        # Transparent audit record
        audit_entry = {
            "id": f"audit-{int(datetime.now().timestamp())}",
            "action": "Project Created",
            "name": project_doc["name"],
            "by": actor,
            "role": actor_role,
            "time": datetime.now().strftime("%b %d, %Y %I:%M %p"),
            "details": f"Project {project_doc['name']} created and assigned to {project_doc['assignedPM']}"
        }
        await col("audit_logs").insert_one(audit_entry)

        project_doc.pop("_id", None)
        return project_doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    data: dict = Body(...),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Update an existing project in MongoDB with transparent role attribution.
    """
    try:
        # Determine actor
        if user and user.get("name") and user.get("role"):
            actor = f"{user['name']} ({user['role']})"
            actor_role = user["role"]
        else:
            actor = data.get("updated_by") or "Priya Sharma (HR)"
            actor_role = "HR" if "HR" in actor else "CEO" if "CEO" in actor else "PM"

        existing = await col("projects").find_one({"id": project_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Project not found")

        updates = {**data}
        updates["updated_by"] = actor
        updates["updated_at"] = datetime.now().strftime("%b %d, %Y %I:%M %p")
        updates.pop("_id", None)

        await col("projects").update_one({"id": project_id}, {"$set": updates})

        # Transparent audit record
        audit_entry = {
            "id": f"audit-{int(datetime.now().timestamp())}",
            "action": "Project Updated",
            "name": existing.get("name", project_id),
            "by": actor,
            "role": actor_role,
            "time": datetime.now().strftime("%b %d, %Y %I:%M %p"),
            "details": f"Project {existing.get('name', project_id)} updated (Status: {updates.get('status', existing.get('status'))})"
        }
        await col("audit_logs").insert_one(audit_entry)

        updated_project = await col("projects").find_one({"id": project_id}, {"_id": 0})
        return updated_project
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    performed_by: Optional[str] = Query(None),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Delete a project from MongoDB with transparent audit tracking.
    """
    try:
        if user and user.get("name") and user.get("role"):
            actor = f"{user['name']} ({user['role']})"
            actor_role = user["role"]
        else:
            actor = performed_by or "Priya Sharma (HR)"
            actor_role = "HR" if "HR" in actor else "CEO"

        existing = await col("projects").find_one({"id": project_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Project not found")

        await col("projects").delete_one({"id": project_id})

        # Transparent audit record
        audit_entry = {
            "id": f"audit-{int(datetime.now().timestamp())}",
            "action": "Project Deleted",
            "name": existing.get("name", project_id),
            "by": actor,
            "role": actor_role,
            "time": datetime.now().strftime("%b %d, %Y %I:%M %p"),
            "details": f"Project {existing.get('name', project_id)} removed from system"
        }
        await col("audit_logs").insert_one(audit_entry)

        return {"message": "Project deleted successfully", "id": project_id, "deleted_by": actor}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


@router.get("/team/{team_id}")
async def list_team_projects(
    team_id: str,
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """List all projects assigned to a team."""
    projects = await col("projects").find(
        {"$or": [{"team_id": team_id}, {"team_ids": team_id}]},
        {"_id": 0}
    ).to_list(100)
    return projects
