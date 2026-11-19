"""HR role endpoints must not expose credentials or another tenant's employees."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.roles import hr
from core.dependencies import get_current_user


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/dashboard", "/employees"])
@pytest.mark.parametrize("organization", ["ORG-A", None])
async def test_hr_employee_views_are_scoped_and_allowlisted(mock_db, monkeypatch, path, organization):
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    await mock_db.users.insert_many([
        {"employee_id": "HR-A", "name": "HR", "role": "HR", "org_id": "ORG-A", "is_active": True},
        {"employee_id": "DEV-A", "name": "Developer", "role": "DEVELOPER", "org_id": "ORG-A",
         "is_active": True, "organisation_password": "stored-org-hash", "employee_password": "stored-employee-hash",
         "password_hash": "legacy-hash", "github_username": "private-identity", "project_ids": ["private-project"],
         "is_admin": False, "future_sensitive_field": {"secret": "private"}},
        {"employee_id": "DEV-B", "role": "DEVELOPER", "org_id": "ORG-B", "is_active": True},
    ])
    actor = {"employee_id": "HR-A", "name": "HR", "role": "HR", "org_id": organization}
    app = FastAPI()
    app.include_router(hr.router)
    app.dependency_overrides[get_current_user] = lambda: actor
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 200
    data = response.json()
    expected = {"HR-A", "DEV-A"} if organization else {"HR-A"}
    assert {p["employee_id"] for p in data["employees"]} == expected
    for person in data["employees"]:
        assert not {"organisation_password", "employee_password", "password_hash", "github_username",
                    "project_ids", "is_admin", "future_sensitive_field"}.intersection(person)
    count = data["summary"]["total_employees"] if path == "/dashboard" else data["total"]
    assert count == len(expected)
