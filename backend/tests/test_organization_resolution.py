"""Organization defaults come from current account provenance, never demo IDs."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from api.roles import ceo
from api.routes import projects
from core.dependencies import get_current_user
from domain.services.auth_service import AuthService
from domain.services.project_service import ProjectService


@pytest.mark.anyio
async def test_project_list_uses_authenticated_org_and_rejects_cross_org(monkeypatch):
    actor = {"employee_id": "A", "role": "CEO", "org_id": "ORG-CURRENT"}
    load = AsyncMock(return_value=[])
    monkeypatch.setattr(ProjectService, "get_active_projects", load)
    app = FastAPI()
    app.include_router(projects.router, prefix="/projects")
    app.dependency_overrides[get_current_user] = lambda: actor
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get('/projects/')).status_code == 200
        load.assert_awaited_once_with('ORG-CURRENT')
        assert (await client.get('/projects/', params={'org_id': 'ORG-OTHER'})).status_code == 403
        actor['org_id'] = None
        assert (await client.get('/projects/')).status_code == 422
    assert load.await_count == 1


def test_ceo_health_resolves_current_org_without_weakening_tenant_check():
    assert ceo._own_org({'org_id': 'ORG-CURRENT'}, None) == 'ORG-CURRENT'
    with pytest.raises(Exception) as error:
        ceo._own_org({'org_id': 'ORG-CURRENT'}, 'ORG-OTHER')
    assert error.value.status_code == 403


def test_auth_profile_includes_actual_organization():
    user = AuthService._user_out({'employee_id': 'A', 'email': 'a@example.com', 'name': 'Account',
        'role': 'DEVELOPER', 'dept': 'Engineering', 'org_id': 'ORG-CURRENT'})
    assert user.org_id == 'ORG-CURRENT'
