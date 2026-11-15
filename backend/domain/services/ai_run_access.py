"""AI-run resource boundary, using the current authenticated account and project rows."""

from typing import Any

from fastapi import HTTPException

from core.permissions import Permission, get_user_permissions
from repositories.project_repository import ProjectRepository

ACCESS_VERSION = "ai-run-access-v1"


def actor_id(user):
    identity = user.get("employee_id")
    if not isinstance(identity, str) or not identity:
        raise HTTPException(403, "An authenticated employee identity is required")
    return identity


def permissions(user):
    return get_user_permissions(user.get("role", "").upper(), user.get("is_admin", False), user.get("designation"))


async def accessible_projects(user):
    """Resolve current tenant and membership without the legacy PM tenant bypass."""
    actor_id(user)
    role = user.get("role", "").upper()
    organization = user.get("org_id")
    query: dict[str, Any] = {"org_id": {"$type": "string", "$ne": ""}}
    if isinstance(organization, str) and organization:
        query["org_id"] = organization
    if role != "CEO":
        if not isinstance(organization, str) or not organization:
            return []
        query["org_id"] = organization
        assigned = user.get("project_ids") or []
        assigned = [key for key in assigned if isinstance(key, str)] if isinstance(assigned, list) else []
        if role == "PM":
            query["id"] = {"$in": assigned}
        else:
            membership: list[dict[str, Any]] = [{"id": {"$in": assigned}}]
            team = user.get("team_id")
            if isinstance(team, str) and team:
                membership.append({"team_id": team})
            query["$or"] = membership
    projects = await ProjectRepository().find_all(query)
    return [row for row in projects if isinstance(row.get("org_id"), str) and row["org_id"]
            and isinstance(row.get("id"), str) and row["id"]]


async def read_filter(user):
    allowed = permissions(user)
    required = Permission.VIEW_EMPLOYEE_DIRECTORY if user.get("role", "").upper() == "HR" else Permission.VIEW_AI_EVALUATION
    if required not in allowed:
        raise HTTPException(403, "Insufficient permissions")
    private = {
        "owner_id": actor_id(user),
        "project_id": None,
        "$or": [{"organization_id": None}, {"organization_id": user.get("org_id")}],
    }
    scopes = [{"project_id": row["id"], "organization_id": row["org_id"]}
              for row in await accessible_projects(user)]
    return {"access_version": ACCESS_VERSION, "owner_id": {"$type": "string", "$ne": ""},
            "$or": [private, *scopes]}


async def invocation_scope(user, context):
    identity = actor_id(user)
    project_id = context.get("project_id")
    if project_id is not None and (not isinstance(project_id, str) or not project_id):
        raise HTTPException(422, "project_id must be a nonempty string")
    organization = user.get("org_id")
    if project_id:
        projects = await accessible_projects(user)
        project = next((row for row in projects if row.get("id") == project_id), None)
        if project is None:
            raise HTTPException(404, "Authorized project not found")
        organization = project["org_id"]
    for key in ("org_id", "organization_id", "organisation_id"):
        if key in context and context[key] != organization:
            raise HTTPException(403, "Requested organization does not match the authorized scope")
    return {"access_version": ACCESS_VERSION, "owner_id": identity,
            "project_id": project_id, "organization_id": organization}
