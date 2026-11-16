"""Resolve organization context without inventing tenant identities."""

from fastapi import HTTPException


def resolve_organization(user: dict, requested: str | None) -> str:
    own = user.get("org_id")
    if own and requested is not None and requested != own:
        raise HTTPException(403, "You can only view your own organisation")
    resolved = own or requested
    if not isinstance(resolved, str) or not resolved.strip():
        raise HTTPException(422, "An organisation must be assigned to this account or explicitly selected")
    return resolved
