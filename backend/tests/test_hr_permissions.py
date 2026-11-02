import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch

from core.permissions import Permission, get_user_permissions, OrganizationalRole
from api.routes.platform_routes import create_company, delete_company

def test_hr_permissions_matrix():
    """Verify HR has permissions to manage teams and employees, but not company admin."""
    hr_permissions = get_user_permissions("HR", is_admin=False)
    
    # HR must have MANAGE_TEAMS, ASSIGN_PROJECT, ASSIGN_TEAM_LEAD, MANAGE_EMPLOYEES
    assert Permission.MANAGE_TEAMS in hr_permissions
    assert Permission.ASSIGN_PROJECT in hr_permissions
    assert Permission.ASSIGN_TEAM_LEAD in hr_permissions
    assert Permission.MANAGE_EMPLOYEES in hr_permissions
    
    # HR must NOT have MANAGE_SETTINGS or VIEW_AUDIT_LOGS or MANAGE_USERS
    assert Permission.MANAGE_SETTINGS not in hr_permissions
    assert Permission.MANAGE_USERS not in hr_permissions

def test_ceo_permissions_matrix():
    """Verify CEO has full management capabilities."""
    ceo_permissions = get_user_permissions("CEO", is_admin=True)
    assert Permission.MANAGE_TEAMS in ceo_permissions
    assert Permission.MANAGE_USERS in ceo_permissions
    assert Permission.MANAGE_SETTINGS in ceo_permissions

@pytest.mark.asyncio
async def test_hr_cannot_create_company():
    """Verify HR is forbidden from creating companies (returns 403)."""
    hr_user = {"name": "Claire Underwood", "role": "HR", "employee_id": "EMP-004"}
    payload = {"name": "Unauthorized Company", "domain": "unauth.io"}
    
    with pytest.raises(HTTPException) as exc_info:
        await create_company(data=payload, user=hr_user)
    
    assert exc_info.value.status_code == 403
    assert "HR does not have permission to add companies" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_hr_cannot_delete_company():
    """Verify HR is forbidden from deleting companies (returns 403)."""
    hr_user = {"name": "Claire Underwood", "role": "HR", "employee_id": "EMP-004"}
    
    with pytest.raises(HTTPException) as exc_info:
        await delete_company(company_id="ORG-001", performed_by="Claire Underwood (HR)", user=hr_user)
    
    assert exc_info.value.status_code == 403
    assert "HR does not have permission to delete companies" in str(exc_info.value.detail)
