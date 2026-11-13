"""Local-only first-run setup: the Chief Executive and the platform administrator (CR-012)."""

import hmac
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from core.config import settings
from domain.services.first_accounts import FirstAccount, build_accounts, validate_pair
from repositories.user_repository import UserRepository

router = APIRouter()
_setup_lock = asyncio.Lock()


class SetupStatus(BaseModel):
    available: bool
    reason: str | None = None


class AccountSetup(BaseModel):
    email: EmailStr
    organisation_password: str
    employee_password: str


class SetupRequest(BaseModel):
    """CR-012: two separate accounts; the CEO has no admin rights."""
    setup_secret: str
    ceo: AccountSetup
    admin: AccountSetup


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
    if not hmac.compare_digest(payload.setup_secret.encode(), settings.DEMO_SETUP_SECRET.encode()):
        raise HTTPException(status_code=403, detail="Invalid setup secret")

    ceo = FirstAccount("DEMO-CEO", "Demo CEO", str(payload.ceo.email),
                       payload.ceo.organisation_password, payload.ceo.employee_password)
    admin = FirstAccount("DEMO-ADMIN", "Platform Admin", str(payload.admin.email),
                         payload.admin.organisation_password, payload.admin.employee_password)
    try:
        validate_pair(ceo, admin)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    async with _setup_lock:
        users = UserRepository()
        if await users.col.count_documents({}) > 0:
            raise HTTPException(status_code=409, detail="An account already exists")

        await users.ensure_indexes()
        records = build_accounts(ceo, admin, created_by="local-first-run-setup")
        try:
            await users.col.insert_many(records, ordered=True)
        except Exception:
            # All or nothing: never leave one of the two accounts behind.
            await users.col.delete_many({"employee_id": {"$in": [r["employee_id"] for r in records]},
                                         "created_by": "local-first-run-setup"})
            raise HTTPException(status_code=409, detail="Setup could not create both accounts; nothing was created")

    return SetupStatus(available=False, reason="Chief Executive and platform administrator created")
