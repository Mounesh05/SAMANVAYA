"""The merged AI boundary must preserve current testing-branch tenant/PM policy."""

import pytest

from core import database
from domain.services.ai_run_access import accessible_projects
from core.permissions import Permission, get_user_permissions


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["PM", "CEO"])
async def test_ai_project_scope_preserves_managed_projects_and_organization(mock_db, monkeypatch, role):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.projects.insert_many([
        {"id": "P1", "org_id": "O1"}, {"id": "P2", "org_id": "O1"}, {"id": "P3", "org_id": "O2"}])
    actor = {"employee_id": "A", "role": role, "org_id": "O1", "project_ids": ["P1"]}
    rows = await accessible_projects(actor)
    assert {row["id"] for row in rows} == ({"P1"} if role == "PM" else {"P1", "P2"})


@pytest.mark.parametrize("role", ["CEO", "HR", "DEVELOPER"])
def test_admin_status_does_not_restore_engineering_ai_trigger(role):
    assert Permission.TRIGGER_AI_EVALUATION not in get_user_permissions(role, is_admin=True)
