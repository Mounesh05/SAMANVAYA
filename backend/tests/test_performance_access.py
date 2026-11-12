"""Scoring-specific historical read migration must not trust JWT roles or prose."""

import copy
import importlib

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from core import database
from core.dependencies import get_current_user
from test_performance_scoring_compatibility import assessment

pytestmark = pytest.mark.anyio


def service():
    assert importlib.util.find_spec("domain.services.performance_access_service"), "Phase 5 scoped access is missing"
    return importlib.import_module("domain.services.performance_access_service").PerformanceAccessService()


@pytest.fixture
async def records(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.users.insert_many([dict(employee_id=key, role=role, org_id=org, is_active=True,
        project_ids=["AUDIT-PROJECT"] if org == "O1" else [], designation="HR_MANAGER" if role == "HR" else None)
        for key, role, org in (("AUDIT-DEV", "DEVELOPER", "O1"), ("L", "LEAD", "O1"),
                             ("H", "HR", "O1"), ("C", "CEO", "O1"), ("X", "CEO", "OTHER"))])
    await mock_db.projects.insert_one({"id": "AUDIT-PROJECT", "org_id": "O1"})
    document = assessment().model_dump()
    document["id"] = "legacy-id"
    document["role_evaluation"]["hr"] = {"normalized_score": 80, "comments": "CONFIDENTIAL WORKPLACE CASE"}
    document["ai_evaluation"]["reasoning"] = "PRIVATE ENGINEERING EVIDENCE"
    document["manager_notes"] = "PRIVATE MANAGER NOTE"
    await mock_db.developer_performances.insert_one(document)
    return mock_db


async def test_foreign_org_stale_admin_and_other_engineer_cannot_read(records):
    with pytest.raises(HTTPException) as error:
        await service().detail("AUDIT-DEV", {"employee_id": "X", "role": "CEO", "is_admin": True})
    assert error.value.status_code == 403
    await records.users.insert_one({"employee_id": "D2", "role": "DEVELOPER", "org_id": "O1", "is_active": True})
    with pytest.raises(HTTPException):
        await service().detail("AUDIT-DEV", {"employee_id": "D2", "role": "LEAD", "is_admin": True})


@pytest.mark.parametrize("actor", ["H", "C"])
async def test_hr_ceo_get_only_allowlisted_legacy_summary(records, actor):
    before = copy.deepcopy(await records.developer_performances.find_one({}))
    result = await service().detail("AUDIT-DEV", {"employee_id": actor})
    data = result.model_dump(mode="json")
    assert data["overall_score"] == 85.4 and data["scoring"]["mode"] == "LEGACY_READ_ONLY"
    assert "PRIVATE" not in str(data) and "CONFIDENTIAL" not in str(data)
    assert data["hr_assessment"] is None and not data["role_feedback_summary"]
    assert await records.developer_performances.find_one({}) == before


async def test_engineering_own_read_preserves_numbers_but_not_confidential_hr(records):
    result = await service().detail("AUDIT-DEV", {"employee_id": "AUDIT-DEV"})
    data = result.model_dump(mode="json")
    assert data["final_score"] == 85.4
    assert "PRIVATE ENGINEERING" in str(data) and "CONFIDENTIAL" not in str(data)


async def test_legacy_trend_is_not_a_methodology_or_coverage_comparable_claim(records):
    data = await service().trend("AUDIT-DEV", {"employee_id": "L"})
    assert data["trend"] == "not_comparable" and data["comparison_limitations"]
    assert data["current_score"] == 85.4


async def test_appeals_are_append_only_and_cannot_overwrite_legacy_assessment(records):
    record = await records.developer_performances.find_one({})
    key = str(record["_id"])
    body = {"reason": "Please review the factual attribution in this historical assessment", "evidence": ["task:1"]}
    first = await service().appeal_legacy(key, body, {"employee_id": "AUDIT-DEV"})
    second = await service().appeal_legacy(key, body, {"employee_id": "AUDIT-DEV"})
    assert first == second and first["credit_status"] == "appealed"
    assert await records.developer_performances.find_one({}) == record
    assert await records.ai_runs.count_documents({"agent_type": "performance_legacy_appeal"}) == 1


async def test_case_specific_hr_detail_and_purpose_scoped_export_are_audited(records):
    await records.hr_assessments.insert_one({"performance_id": "AUDIT-DEV", "developer_id": "AUDIT-DEV",
                                            "evaluator_id": "H", "general_comments": "CONFIDENTIAL"})
    result = await service().hr_case("AUDIT-DEV", {"employee_id": "H"})
    assert result["general_comments"] == "CONFIDENTIAL"
    with pytest.raises(HTTPException):
        await service().hr_case("AUDIT-DEV", {"employee_id": "C", "is_admin": True})
    report = await service().export("AUDIT-DEV", {"purpose": "Employee requested their historical summary"}, {"employee_id": "AUDIT-DEV"})
    assert "CONFIDENTIAL" not in str(report) and "PRIVATE" not in str(report)
    assert await records.ai_runs.count_documents({"agent_type": "performance_access_audit"}) >= 2


async def test_shadow_comparison_does_not_fabricate_missing_canonical_scores(records):
    before = await records.developer_performances.find_one({})
    report = await service().shadow("AUDIT-DEV", {"employee_id": "L"})
    assert report["legacy_score"] == 85.4 and report["canonical_score"] is None and report["difference"] is None
    assert report["status"] == "SHADOW_INCOMPLETE" and report["missing_requirements"]
    assert await records.developer_performances.find_one({}) == before


async def test_all_legacy_read_routes_deny_foreign_org_including_admin(records):
    from api.routes import performance
    app = FastAPI()
    app.include_router(performance.router, prefix="/api/performance")
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "X", "role": "CEO", "is_admin": True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for path in ("developer/AUDIT-DEV", "developer/AUDIT-DEV/trend", "dashboard/AUDIT-DEV", "assessment/hr/AUDIT-DEV",
                     "assessments/AUDIT-DEV/completeness", "team/AUDIT-PROJECT/2026-Q3"):
            response = await client.get("/api/performance/" + path)
            assert response.status_code in {403, 404}, (path, response.text)


async def test_unscoped_and_foreign_policy_history_is_not_disclosed(records):
    await records.evaluation_policies.insert_many([
        dict(policy_id="foreign", org_id="OTHER", role_weights={"ceo": 1}, is_active=True),
        dict(policy_id="unscoped", role_weights={"lead": 1}, is_active=True),
        dict(policy_id="local", org_id="O1", role_weights={"lead": 1}, is_active=True)])
    from api.routes import performance
    result = await performance.get_human_evaluation_policy_history(user={"employee_id": "L"}, limit=20)
    assert len(result) == 1 and result[0]["policy_id"] == "local"
    current = await performance.get_human_evaluation_policy(user={"employee_id": "L"})
    assert current["status"] == "POLICY_PENDING" and current["role_weights"] == {}


async def test_out_of_scope_rows_are_withheld_without_hiding_visible_history(records):
    from datetime import timedelta
    await records.projects.insert_one({"id": "OTHER-PROJECT", "org_id": "O1"})
    other = copy.deepcopy(await records.developer_performances.find_one({}, {"_id": 0}))
    other.update(id="other-legacy", project_id="OTHER-PROJECT", period_label="2026-Q4",
                 period_start=other["period_start"] + timedelta(days=92), period_end=other["period_end"] + timedelta(days=92))
    await records.developer_performances.insert_one(other)
    managed = await service().trend("AUDIT-DEV", {"employee_id": "L"})
    assert [r["period_label"] for r in managed["history"]] == ["2026-Q3"]  # The unassigned project row is withheld.
    own = await service().trend("AUDIT-DEV", {"employee_id": "AUDIT-DEV"})
    assert [r["period_label"] for r in own["history"]] == ["2026-Q4", "2026-Q3"]
    await records.developer_performances.delete_many({"project_id": "AUDIT-PROJECT"})
    with pytest.raises(HTTPException) as error:
        await service().trend("AUDIT-DEV", {"employee_id": "L"})
    assert error.value.status_code == 403  # Nothing visible remains, so the read is still denied.


async def test_team_summary_excludes_rows_for_accounts_outside_the_organization(records):
    foreign = copy.deepcopy(await records.developer_performances.find_one({}, {"_id": 0}))
    foreign.update(id="foreign-account-row", developer_id="X")  # X belongs to another organization.
    await records.developer_performances.insert_one(foreign)
    rows = await service().team("AUDIT-PROJECT", "current", {"employee_id": "L"})
    assert [r["developer_id"] for r in rows] == ["AUDIT-DEV"]


async def test_hr_case_without_any_historical_scope_proof_is_withheld(records):
    await records.developer_performances.delete_many({})  # This fixture is an isolated in-memory database.
    await records.hr_assessments.insert_one(dict(developer_id="AUDIT-DEV", evaluator_id="H", performance_id="AUDIT-DEV",
                                                 general_comments="UNSCOPED PRIVATE CASE"))
    with pytest.raises(HTTPException) as error:
        await service().hr_case("AUDIT-DEV", {"employee_id": "H"})
    assert error.value.status_code == 403
