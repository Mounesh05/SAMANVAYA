"""Local-only first administrator initialization."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from core.config import settings
from core.security import hash_password, validate_password_strength
from repositories.user_repository import UserRepository

router = APIRouter()
_setup_lock = asyncio.Lock()


class SetupStatus(BaseModel):
    available: bool
    reason: str | None = None


class SetupRequest(BaseModel):
    setup_secret: str
    employee_password: str
    organisation_password: str
    email: EmailStr = "demo.ceo@example.com"


@router.get("/status", response_model=SetupStatus)
async def setup_status():
    if not settings.is_development():
        return SetupStatus(available=False, reason="First-run setup is disabled outside development")
    if not settings.DEMO_SETUP_SECRET:
        return SetupStatus(available=False, reason="First-run setup is not configured")

    users = UserRepository()
    if await users.col.count_documents({}) > 0:
        return SetupStatus(available=False, reason="An account already exists")
    return SetupStatus(available=True)


@router.post("/initialize", response_model=SetupStatus, status_code=201)
async def initialize_demo_admin(payload: SetupRequest):
    if not settings.is_development() or not settings.DEMO_SETUP_SECRET:
        raise HTTPException(status_code=404, detail="First-run setup is unavailable")
    if payload.setup_secret != settings.DEMO_SETUP_SECRET:
        raise HTTPException(status_code=403, detail="Invalid setup secret")

    valid, message = validate_password_strength(payload.organisation_password)
    if not valid:
        raise HTTPException(status_code=422, detail=f"Organisation password: {message}")
    valid, message = validate_password_strength(payload.employee_password)
    if not valid:
        raise HTTPException(status_code=422, detail=f"Employee password: {message}")
    if payload.organisation_password == payload.employee_password:
        raise HTTPException(
            status_code=422,
            detail="Organisation and employee passwords must be different",
        )

    async with _setup_lock:
        users = UserRepository()
        if await users.col.count_documents({}) > 0:
            raise HTTPException(status_code=409, detail="An account already exists")

        await users.ensure_indexes()
        await users.insert(
            {
                "employee_id": "DEMO-CEO",
                "name": "Demo CEO",
                "email": str(payload.email),
                "role": "CEO",
                "dept": "Executive",
                "organisation_password": hash_password(payload.organisation_password),
                "employee_password": hash_password(payload.employee_password),
                "github_username": None,
                "team_id": None,
                "is_active": True,
                "is_admin": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "local-first-run-setup",
            }
        )

    return SetupStatus(available=False, reason="Initial administrator created")
