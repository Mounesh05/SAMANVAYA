"""Calibration packets are proposals, not model-generated approval or scores."""

import importlib
import pytest
from fastapi import HTTPException
from test_performance_human_service import stored as readiness_store  # noqa: F401

pytestmark = pytest.mark.anyio


@pytest.fixture
async def stored(readiness_store):  # noqa: F811
    return readiness_store


def service():
    assert importlib.util.find_spec("domain.services.performance_readiness_service"), "Phase 6 readiness is missing"
    return importlib.import_module("domain.services.performance_readiness_service").PerformanceReadinessService()


async def test_missing_calibration_never_activates_any_engineering_role(stored):
    result = await service().readiness({"employee_id": "A"})
    assert result["production_scoring_enabled"] is False
    assert [r["role"] for r in result["roles"]] == ["DEVELOPER", "QA", "DEVOPS", "LEAD", "PM"]
    assert all(r["is_finalizable"] is False and r["engineering_score"] is None for r in result["roles"])
    assert result["unresolved_decisions"] and result["ceo_routine_contribution"] == 0


async def test_unsigned_release_flags_cannot_satisfy_readiness(stored):
    db, _ = stored
    await db.ai_runs.insert_one({"agent_type": "performance_scoring_release", "status": "APPROVED", "is_active": True,
        "output_data": {"payload": {"subject_role": "DEVELOPER", "score": 100}}})
    result = await service().readiness({"employee_id": "A"})
    assert not result["production_scoring_enabled"] and not result["roles"][0]["is_finalizable"]


def packet(run, **changes):
    return {**dict(project_id="P", subject_role="DEVELOPER", rationale="Proposed calibration against frozen real work references",
        proposed_rules="No numeric rules are approved. Review quality, opportunity, duplication and role suitability.",
        samples=[dict(run_id=run.run_id, source_ids=[run.evidence.snapshot.records[0].source_id],
                      purpose="representative_work", rationale="Proposed representative sample; representativeness needs review")]), **changes}


async def test_calibration_draft_binds_exact_sources_and_is_never_approved(stored):
    db, run = stored
    receipt = await service().propose(packet(run), {"employee_id": "A"})
    assert receipt["status"] == "PROPOSED_UNVERIFIED" and not receipt["is_finalizable"]
    record = await service().get(receipt["draft_id"], {"employee_id": "R"})
    assert record["samples"][0]["snapshot_digest"] == run.evidence.digest
    assert record["samples"][0]["role_at_period"] is None
    assert record["representativeness"] == "NOT_ESTABLISHED"
    from repositories.ai_run_repository import AIRunRepository
    assert await AIRunRepository().get_by_id(receipt["draft_id"]) is None
    assert await db.developer_performances.count_documents({}) == 0


async def test_foreign_scope_and_current_role_are_checked_for_calibration_sources(stored):
    db, run = stored
    with pytest.raises(HTTPException):
        await service().propose(packet(run), {"employee_id": "C", "role": "LEAD", "is_admin": True})
    await db.users.update_one({"employee_id": "A"}, {"$set": {"org_id": "OTHER"}})
    with pytest.raises(HTTPException):
        await service().propose(packet(run), {"employee_id": "A"})


async def test_fabricated_sample_source_and_approval_fields_are_rejected(stored):
    _, run = stored
    data = packet(run)
    data["samples"][0]["source_ids"] = ["f" * 64]
    with pytest.raises(HTTPException) as error:
        await service().propose(data, {"employee_id": "A"})
    assert error.value.status_code == 422
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        await service().propose(packet(run, status="APPROVED", final_score=100), {"employee_id": "A"})


async def test_signed_assignment_discovery_lists_only_current_eligible_reviewer(stored):
    from domain.services.performance_human_service import HumanFeedbackService
    from test_performance_human_service import assignment
    db, run = stored
    await HumanFeedbackService().assign(assignment(run), {"employee_id": "A"})
    assert hasattr(HumanFeedbackService(), "assignments"), "Assigned observation discovery is missing"
    result = await HumanFeedbackService().assignments({"employee_id": "R"})
    assert len(result) == 1 and result[0]["employee_id"] == "D" and result[0]["dimensions"] == ["collaboration"]
    assert await HumanFeedbackService().assignments({"employee_id": "H"}) == []
    await db.users.update_one({"employee_id": "R"}, {"$set": {"is_active": False}})
    with pytest.raises(HTTPException):
        await HumanFeedbackService().assignments({"employee_id": "R", "role": "LEAD"})


async def test_subject_discovery_returns_current_scoped_receipts_without_raw_evidence(stored):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    db, run = stored
    lifecycle = AssessmentLifecycleService()
    head = await lifecycle.create({"run_id": run.run_id, "reason": "Scoped discovery verification"}, {"employee_id": "A"})
    result = await lifecycle.list_for_subject("D", {"employee_id": "D"})
    assert len(result) == 1 and result[0]["assessment_id"] == head["assessment_id"]
    assert result[0]["can_appeal"] is True and result[0]["approved_score"] is None
    assert "frozen_evidence" not in str(result) and "source_records" not in str(result)
    manager = await lifecycle.list_for_subject("D", {"employee_id": "R"})
    assert manager[0]["can_appeal"] is False
    await db.users.update_one({"employee_id": "R"}, {"$set": {"org_id": "OTHER"}})
    with pytest.raises(HTTPException):
        await lifecycle.list_for_subject("D", {"employee_id": "R", "role": "CEO", "is_admin": True})


async def test_readiness_and_calibration_routes_use_current_account_and_exact_sources(stored):
    import httpx
    from fastapi import FastAPI
    from api.routes.performance import router
    from core.dependencies import get_current_user
    db, run = stored
    app = FastAPI()
    app.include_router(router, prefix="/performance")
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "A", "role": "CEO"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/performance/readiness")
        assert response.status_code == 200 and not response.json()["production_scoring_enabled"]
        proposed = await client.post("/performance/calibration-drafts", json=packet(run))
        assert proposed.status_code == 201 and proposed.json()["status"] == "PROPOSED_UNVERIFIED"
        loaded = await client.get("/performance/calibration-drafts/" + proposed.json()["draft_id"])
        assert loaded.status_code == 200 and loaded.json()["samples"][0]["snapshot_digest"] == run.evidence.digest
        forged = await client.post("/performance/calibration-drafts", json=packet(run, status="APPROVED"))
        assert forged.status_code == 422
        assert (await client.get("/performance/human-assignments")).json() == []
        assert (await client.get("/performance/developer/D/assessments")).json() == []
        await db.users.update_one({"employee_id": "A"}, {"$set": {"is_active": False}})
        assert (await client.get("/performance/readiness")).status_code == 403
