"""Current-account assignment, private observation intake and legacy write guards."""

import copy
import importlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from core import database
from core.dependencies import get_current_user
from domain.models.performance_evidence import EvidencePreviewRequest

pytestmark = pytest.mark.anyio


def service():
    assert importlib.util.find_spec("domain.services.performance_human_service"), "Phase 4 review intake is missing"
    return importlib.import_module("domain.services.performance_human_service").HumanFeedbackService()


@pytest.fixture
async def stored(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.users.insert_many([
        {"employee_id": key, "role": role, "org_id": "O", "project_ids": ["P"], "is_active": True,
         "is_admin": key == "A", "designation": "HR_MANAGER" if role == "HR" else None,
         "github_username": "author" if key == "D" else key.lower()}
        for key, role in (("D", "DEVELOPER"), ("A", "LEAD"), ("R", "LEAD"), ("H", "HR"), ("C", "CEO"))])
    await mock_db.projects.insert_one({"id": "P", "org_id": "O"})
    await mock_db.github_project_configs.insert_one({"project_id": "P", "repository_owner": "o", "repository_name": "r"})
    await mock_db.pull_requests.insert_one({"id": "PR1", "pr_number": 1, "project_id": "P", "repo_id": "o/r",
        "author_login": "author", "status": "merged", "head_sha": "a" * 40, "merged_at": "2026-08-01T00:00:00Z"})
    from agents import performance_agent
    def unavailable(**kwargs):
        raise ConnectionError("Synthetic model outage")
    monkeypatch.setattr(performance_agent, "get_ollama_llm", unavailable)
    from domain.services.performance_claim_service import PerformanceClaimService
    run = await PerformanceClaimService().create(EvidencePreviewRequest(employee_id="D", project_id="P",
        period_start="2026-07-01T00:00:00Z", period_end="2026-10-01T00:00:00Z"), {"employee_id": "A"})
    return mock_db, run


def assignment(run, role="LEAD", **changes):
    from domain.models.performance_human import HumanReviewerAssignmentRequest
    source = run.evidence.snapshot.records[0]
    return HumanReviewerAssignmentRequest(**{**dict(run_id=run.run_id, reviewer_id="H" if role == "HR" else "R",
        role=role, dimensions=["professional_conduct" if role == "HR" else "collaboration"],
        interaction_reason="Actual period interaction attested by an independent scoped administrator",
        interaction_evidence=[dict(source_reference=source.source_id, source_revision=source.content_digest,
                                  observed_at="2026-08-01T00:00:00Z")],
        interaction_attested=True, no_conflict_attested=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1)), **changes})


def body(role="LEAD", **changes):
    from domain.models.performance_human import HumanReviewRequest
    return HumanReviewRequest(**{**dict(no_conflict_attested=True, observations=[dict(
        dimension="professional_conduct" if role == "HR" else "collaboration", state="OBSERVED", rating=4,
        reason="Observed specific behavior during this period", direct_observation=True,
        evidence=[dict(source_reference="workplace:private-reference", source_revision="v1", observed_at="2026-08-01T00:00:00Z")])]), **changes})


async def test_signed_intake_is_idempotent_and_does_not_write_legacy_scores(stored):
    db, run = stored
    receipt = await service().assign(assignment(run), {"employee_id": "A"})
    first = await service().submit(receipt["assignment_id"], body(), {"employee_id": "R"})
    assert first["status"] == "RECORDED_UNVERIFIED" and first["human_score"] is None
    second = await service().submit(receipt["assignment_id"], body(), {"employee_id": "R"})
    assert first == second
    assert await db.ai_runs.count_documents({"agent_type": "performance_human_review"}) == 1
    assert await db.developer_performances.count_documents({}) == 0
    summary = await service().summary(run.run_id, {"employee_id": "D"})
    assert summary["aggregation"]["status"] == "POLICY_PENDING"
    assert "workplace:private-reference" not in str(summary) and "Observed specific" not in str(summary)


@pytest.mark.parametrize("actor", ["D", "R", "H", "C"])
async def test_only_independent_current_scoped_technical_admin_can_assign(stored, actor):
    _, run = stored
    with pytest.raises(HTTPException) as error:
        await service().assign(assignment(run), {"employee_id": actor, "role": "LEAD", "is_admin": True})
    assert error.value.status_code == 403


async def test_duplicate_role_assignment_cannot_add_extra_weight(stored):
    _, run = stored
    await service().assign(assignment(run), {"employee_id": "A"})
    with pytest.raises(HTTPException) as error:
        await service().assign(assignment(run, reviewer_id="A"), {"employee_id": "A"})
    assert error.value.status_code in {403, 409}


@pytest.mark.parametrize("changes", [{"role": "PM"}, {"is_active": False}, {"org_id": "OTHER"}, {"project_ids": []}])
async def test_changed_current_eligibility_blocks_submission(stored, changes):
    db, run = stored
    receipt = await service().assign(assignment(run), {"employee_id": "A"})
    await db.users.update_one({"employee_id": "R"}, {"$set": changes})
    with pytest.raises(HTTPException) as error:
        await service().submit(receipt["assignment_id"], body(), {"employee_id": "R", "role": "LEAD"})
    assert error.value.status_code == 403
    assert await db.ai_runs.count_documents({"agent_type": "performance_human_review"}) == 0


async def test_hr_assignment_accepts_only_own_workplace_observations_without_raw_engineering_access(stored):
    db, run = stored
    receipt = await service().assign(assignment(run, "HR"), {"employee_id": "A"})
    await service().submit(receipt["assignment_id"], body("HR"), {"employee_id": "H"})
    own = await service().get_review(receipt["assignment_id"], {"employee_id": "H"})
    assert own["observations"][0]["dimension"] == "professional_conduct"
    with pytest.raises(HTTPException):
        await service().get_review(receipt["assignment_id"], {"employee_id": "A"})
    from domain.services.performance_claim_service import PerformanceClaimService
    with pytest.raises(HTTPException):
        await PerformanceClaimService().get(run.run_id, {"employee_id": "H"})
    from repositories.ai_run_repository import AIRunRepository
    assert await AIRunRepository().get_by_id(receipt["assignment_id"]) is None
    assert await db.hr_assessments.count_documents({}) == 0


async def test_forged_assignment_and_expired_authority_cannot_submit(stored):
    db, run = stored
    receipt = await service().assign(assignment(run), {"employee_id": "A"})
    original = copy.deepcopy(await db.ai_runs.find_one({"id": receipt["assignment_id"]}))
    await db.ai_runs.update_one({"id": receipt["assignment_id"]}, {"$set": {"signature": "f" * 64}})
    with pytest.raises(HTTPException) as error:
        await service().submit(receipt["assignment_id"], body(), {"employee_id": "R"})
    assert error.value.status_code == 409
    await db.ai_runs.replace_one({"id": receipt["assignment_id"]}, original)
    await db.users.update_one({"employee_id": "A"}, {"$set": {"is_admin": False}})
    with pytest.raises(HTTPException):
        await service().submit(receipt["assignment_id"], body(), {"employee_id": "R"})


async def test_conflicting_retry_and_wrong_dimension_are_rejected(stored):
    _, run = stored
    receipt = await service().assign(assignment(run), {"employee_id": "A"})
    await service().submit(receipt["assignment_id"], body(), {"employee_id": "R"})
    changed = body().model_dump()
    changed["observations"][0]["rating"] = 3
    with pytest.raises(HTTPException) as error:
        await service().submit(receipt["assignment_id"], changed, {"employee_id": "R"})
    assert error.value.status_code == 409
    changed["observations"][0]["dimension"] = "communication"
    with pytest.raises(HTTPException) as error:
        await service().submit(receipt["assignment_id"], changed, {"employee_id": "R"})
    assert error.value.status_code == 422


async def test_legacy_writes_do_not_create_fake_scores_or_overwrite_history(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    from domain.services.performance_service import PerformanceService
    from domain.services.hr_performance_service import HRPerformanceService
    from domain.models.hr_performance import HRAssessmentCreate
    await mock_db.developer_performances.insert_one({"id": "old", "final_score": 85.4, "grade": "B+"})
    before = await mock_db.developer_performances.find_one({})
    with pytest.raises(ValueError, match="assigned|assignment"):
        await PerformanceService.__new__(PerformanceService).add_role_feedback("old", "lead", {})
    with pytest.raises(ValueError, match="assigned|assignment"):
        await HRPerformanceService.__new__(HRPerformanceService).submit_hr_assessment("old", HRAssessmentCreate(dimensions={}), {})
    assert await mock_db.developer_performances.find_one({}) == before
    assert await mock_db.hr_assessments.count_documents({}) == 0


async def test_policy_read_never_seeds_example_weights(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    from repositories.hr_performance_repository import EvaluationPolicyRepository
    result = await EvaluationPolicyRepository().get_active_policy()
    assert result["status"] == "POLICY_PENDING" and result["role_weights"] == {}
    assert await mock_db.evaluation_policies.count_documents({}) == 0
    assert await EvaluationPolicyRepository().get_policy_history() == []


async def test_legacy_ceo_and_hr_submit_api_report_pending_with_string_detail():
    from api.routes import performance
    app = FastAPI()
    app.include_router(performance.router, prefix="/api/performance")
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "C", "role": "CEO"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/performance/feedback/old/ceo", json={"business_impact": 5,
            "innovation": 5, "company_alignment": 5, "leadership_potential": 5})
        assert response.status_code == 409 and response.json()["status"] == "CEO_SCORING_DISABLED"
        assert isinstance(response.json()["detail"], str)
        app.dependency_overrides[get_current_user] = lambda: {"employee_id": "H", "role": "HR", "designation": "HR_MANAGER"}
        response = await client.post("/api/performance/assessment/hr/old/submit", json={"dimensions": {}})
        assert response.status_code == 409 and response.json()["status"] == "POLICY_PENDING"


async def test_standard_and_hr_assigned_endpoints_share_intake_and_cannot_supply_scores(stored):
    _, run = stored
    from api.routes import performance
    receipt = await service().assign(assignment(run, "HR"), {"employee_id": "A"})
    app = FastAPI()
    app.include_router(performance.router, prefix="/api/performance")
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "H"}
    url = "/api/performance/human-reviews/" + receipt["assignment_id"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(url, json=body("HR").model_dump(mode="json"))
        second = await client.post(url + "/hr", json=body("HR").model_dump(mode="json"))
        assert first.status_code == second.status_code == 201 and first.json() == second.json()
        assert first.json()["combined_score"] is None
        forged = {**body("HR").model_dump(mode="json"), "validated_dimensions": ["professional_conduct"]}
        assert (await client.post(url, json=forged)).status_code == 422


async def test_concurrent_role_assignment_and_identical_submission_have_one_effect(stored):
    import asyncio
    db, run = stored
    request = assignment(run)
    results = await asyncio.gather(*(service().assign(request, {"employee_id": "A"}) for _ in range(2)),
                                   return_exceptions=True)
    successes = [r for r in results if isinstance(r, dict)]
    assert len(successes) == 2 and successes[0] == successes[1]
    assigned = successes[0]
    receipts = await asyncio.gather(*(service().submit(assigned["assignment_id"], body(), {"employee_id": "R"}) for _ in range(2)))
    assert receipts[0] == receipts[1]
    assert await db.ai_runs.count_documents({"agent_type": "performance_human_review"}) == 1


async def test_assignment_retry_recovers_receipt_but_conflicting_reviewer_is_rejected(stored):
    db, run = stored
    request = assignment(run)
    first = await service().assign(request, {"employee_id": "A"})
    assert await service().assign(request, {"employee_id": "A"}) == first
    await db.users.insert_one({"employee_id": "R2", "role": "LEAD", "org_id": "O", "is_active": True, "project_ids": ["P"]})
    with pytest.raises(HTTPException) as error:
        await service().assign(assignment(run, reviewer_id="R2"), {"employee_id": "A"})
    assert error.value.status_code == 409
    assert await db.ai_runs.count_documents({"agent_type": "performance_human_assignment"}) == 1


async def test_draft_policy_is_sealed_but_cannot_activate_or_replace_legacy_policy(stored):
    from test_performance_human import policy
    db, _ = stored
    receipt = await service().propose_policy(dict(project_id="P", reason="Synthetic proposal", policy=policy(status="DRAFT")),
                                            {"employee_id": "A"})
    assert receipt["status"] == "DRAFT" and not receipt["is_active"]
    assert await db.evaluation_policies.count_documents({}) == 0
    from repositories.ai_run_repository import AIRunRepository
    assert await AIRunRepository().get_by_id(receipt["draft_id"]) is None
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        await service().propose_policy(dict(project_id="P", reason="Forged approval", policy=policy()), {"employee_id": "A"})


async def test_wrong_period_and_fabricated_interaction_references_do_not_assign(stored):
    from domain.models.performance_human import HumanReviewerAssignmentRequest
    _, run = stored
    for change in ({"source_revision": "forged"}, {"observed_at": "2026-10-01T00:00:00Z"}):
        data = assignment(run).model_dump()
        data["interaction_evidence"][0].update(change)
        with pytest.raises(HTTPException) as error:
            await service().assign(HumanReviewerAssignmentRequest(**data), {"employee_id": "A"})
        assert error.value.status_code == 422
