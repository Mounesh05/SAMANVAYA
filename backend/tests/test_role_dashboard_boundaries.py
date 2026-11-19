"""Dashboard aggregates must obey the same scope as project detail endpoints."""

import pytest

from api.roles import ceo, lead, pm


@pytest.fixture
def dashboard_db(mock_db, monkeypatch):
    monkeypatch.setattr("repositories.project_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.task_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.pr_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.sprint_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.risk_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr(ceo, "col", lambda name: mock_db[name])
    return mock_db


@pytest.mark.anyio
async def test_ceo_dashboard_counts_only_own_tenant_projects_and_incidents(dashboard_db):
    db = dashboard_db
    await db.projects.insert_many([{"id": "P-A", "org_id": "A", "status": "active"},
                                   {"id": "P-B", "org_id": "B", "status": "active"}])
    await db.incidents.insert_many([{"project_id": "P-A", "status": "open"}, {"project_id": "P-B", "status": "open"}])
    result = await ceo.ceo_dashboard(user={"name": "CEO", "org_id": "A"})
    assert result["organization_health"]["total_projects"] == 1
    assert result["active_incidents"] == 1


@pytest.mark.anyio
async def test_pm_dashboard_and_risks_exclude_unmanaged_and_foreign_projects(dashboard_db):
    db = dashboard_db
    for identifier, org in [("P-A", "A"), ("P-OTHER", "A"), ("P-B", "B")]:
        await db.projects.insert_one({"id": identifier, "org_id": org, "status": "active"})
        await db.risks.insert_one({"id": identifier, "project_id": identifier, "status": "open", "risk_level": "HIGH"})
    actor = {"name": "PM", "org_id": "A", "project_ids": ["P-A", "P-B"]}
    result = await pm.pm_dashboard(user=actor)
    assert result["summary"]["active_projects"] == 1
    result = await pm.pm_risks(user=actor)
    assert {r["project_id"] for r in result["risks"]} == {"P-A"}


@pytest.mark.anyio
async def test_lead_dashboard_excludes_foreign_team_records_and_secret_fields(dashboard_db):
    await dashboard_db.users.insert_many([
        {"employee_id": "D-A", "name": "Developer", "role": "DEVELOPER", "is_active": True,
         "team_id": "T", "org_id": "A", "organisation_password": "hash", "employee_password": "hash",
         "future_sensitive_field": "secret"},
        {"employee_id": "D-B", "name": "Foreign", "is_active": True, "team_id": "T", "org_id": "B"},
    ])
    result = await lead.lead_dashboard(user={"employee_id": "L", "name": "Lead", "org_id": "A", "team_id": "T"})
    assert result["summary"]["team_size"] == 1
    assert result["team_members"][0]["employee_id"] == "D-A"
    assert not {"organisation_password", "employee_password", "future_sensitive_field"}.intersection(result["team_members"][0])
