import pytest
import asyncio
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch, MagicMock

from api.routes.admin import (
    verify_admin_access,
    CompanyProvisionRequest,
    LeaderAssignment,
    provision_company_with_leaders,
    get_admin_profile,
    get_admin_companies,
)
from core.security import create_access_token


@pytest.mark.asyncio
async def test_verify_admin_access_with_master_secret():
    """Verify master admin secret grants access."""
    request = MagicMock()
    request.query_params = {}
    auth_res = await verify_admin_access(request, authorization=None, x_admin_secret="samanvaya-admin-2026")
    assert auth_res["authenticated"] is True
    assert auth_res["role"] == "SUPERADMIN"


@pytest.mark.asyncio
async def test_verify_admin_access_with_ceo_token():
    """Verify CEO JWT grants access."""
    token = create_access_token({
        "employee_id": "EMP-CEO-001",
        "role": "CEO",
        "name": "Alexander Sterling",
        "email": "ceo@samanvaya.io",
        "is_admin": True,
    })
    request = MagicMock()
    request.query_params = {}
    auth_res = await verify_admin_access(request, authorization=f"Bearer {token}", x_admin_secret=None)
    assert auth_res["authenticated"] is True
    assert auth_res["role"] == "CEO"


@pytest.mark.asyncio
async def test_verify_admin_access_rejects_developer():
    """Verify non-admin roles (e.g. DEVELOPER) are rejected with 403."""
    token = create_access_token({
        "employee_id": "EMP-DEV-001",
        "role": "DEVELOPER",
        "name": "Sarah Connor",
        "email": "dev@samanvaya.io",
        "is_admin": False,
    })
    request = MagicMock()
    request.query_params = {}
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_access(request, authorization=f"Bearer {token}", x_admin_secret=None)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_admin_access_rejects_unauthenticated():
    """Verify unauthenticated requests are rejected with 401."""
    request = MagicMock()
    request.query_params = {}
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_access(request, authorization=None, x_admin_secret=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@patch("api.routes.admin.col")
async def test_provision_company_with_leaders(mock_col):
    """Verify company provisioning creates company, CEO, HR, settings, and audit log."""
    mock_db = {}
    def get_collection(name):
        if name not in mock_db:
            m = MagicMock()
            m.find_one = AsyncMock(return_value=None)
            m.count_documents = AsyncMock(return_value=1)
            m.insert_one = AsyncMock()
            m.update_one = AsyncMock()
            mock_db[name] = m
        return mock_db[name]

    mock_col.side_effect = get_collection

    req = CompanyProvisionRequest(
        code="VAL",
        name="Valence Autonomous Systems",
        domain="valence.io",
        industry="Autonomous Robotics",
        location="Bengaluru, Karnataka",
        company_password="Valence@org123",
        ceo=LeaderAssignment(
            name="Vikram Malhotra",
            email="vikram@valence.io",
            employee_id="EMP-CEO-VAL-001",
            password="Emp@ceo123",
            phone="+91 98450 11223",
            bio="Strategic robotics executive"
        ),
        hr=LeaderAssignment(
            name="Ananya Sen",
            email="ananya@valence.io",
            employee_id="EMP-HR-VAL-001",
            password="Emp@hr123",
            phone="+91 98450 44556"
        )
    )

    admin_caller = {"name": "SuperAdmin", "role": "SUPERADMIN"}
    res = await provision_company_with_leaders(req, admin_caller)

    assert res["success"] is True
    assert res["company"]["code"] == "VAL"
    assert res["assigned_leaders"]["ceo"]["employee_id"] == "EMP-CEO-VAL-001"
    assert res["assigned_leaders"]["hr"]["employee_id"] == "EMP-HR-VAL-001"

    # Verify company was inserted
    assert mock_db["companies"].insert_one.called
    inserted_co = mock_db["companies"].insert_one.call_args[0][0]
    assert inserted_co["code"] == "VAL"
    assert "Valence@org123" not in inserted_co["organisation_password"]  # Must be hashed!

    # Verify CEO was inserted
    assert mock_db["users"].insert_one.call_count >= 2
    user_calls = [c[0][0] for c in mock_db["users"].insert_one.call_args_list]
    ceo_user = next((u for u in user_calls if u["role"] == "CEO"), None)
    hr_user = next((u for u in user_calls if u["role"] == "HR"), None)
    
    assert ceo_user is not None
    assert ceo_user["employee_id"] == "EMP-CEO-VAL-001"
    assert "Emp@ceo123" not in ceo_user["employee_password"]  # Must be hashed!

    assert hr_user is not None
    assert hr_user["employee_id"] == "EMP-HR-VAL-001"
    assert "Emp@hr123" not in hr_user["employee_password"]  # Must be hashed!

    # Verify audit log was recorded
    assert mock_db["audit_logs"].insert_one.called
    audit_entry = mock_db["audit_logs"].insert_one.call_args[0][0]
    assert "VAL" in audit_entry["name"]
    assert "Tenant Provisioned with Leadership" == audit_entry["action"]
