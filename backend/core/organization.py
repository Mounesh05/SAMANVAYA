"""Resolve organization context without inventing tenant identities."""

from fastapi import HTTPException


def project_child_tenant_filter(user: dict) -> dict:
    """Legacy child documents inherit a verified project's organization."""
    org = user.get("org_id")
    fields = ("org_id", "organization_id")
    if user.get("organization_id", org) != org:
        raise HTTPException(403, "Conflicting organization on this account")
    if org is None:
        return {field: {"$exists": False} for field in fields}
    if not isinstance(org, str) or not org.strip():
        raise HTTPException(403, "Invalid organization on this account")
    return {"$and": [
        {"$or": [{field: {"$exists": False}}, {field: {"$eq": org, "$not": {"$type": "array"}}}]}
        for field in fields
    ]}


def resolve_organization(user: dict, requested: str | None) -> str:
    own = user.get("org_id")
    if own and requested is not None and requested != own:
        raise HTTPException(403, "You can only view your own organisation")
    resolved = own or requested
    if not isinstance(resolved, str) or not resolved.strip():
        raise HTTPException(422, "An organisation must be assigned to this account or explicitly selected")
    return resolved
