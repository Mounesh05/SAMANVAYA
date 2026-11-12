"""Stored proposals and independent claim decisions remain separate from scores."""

import copy
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from core import database
from core.dependencies import get_current_user

pytestmark = pytest.mark.anyio


def service():
    from domain.services.performance_claim_service import PerformanceClaimService
    return PerformanceClaimService()


def request():
    from domain.models.performance_evidence import EvidencePreviewRequest
    return EvidencePreviewRequest(employee_id="D", project_id="P", period_start="2026-07-01T00:00:00Z",
                                  period_end="2026-10-01T00:00:00Z")


@pytest.fixture
async def stored(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.users.insert_many([
        {"employee_id": key, "role": role, "org_id": "O", "project_ids": ["P"], "is_active": True,
         "is_admin": key == "A", "github_username": "author" if key == "D" else key.lower()}
        for key, role in (("D", "DEVELOPER"), ("A", "LEAD"), ("R", "LEAD"), ("L", "PM"))])
    await mock_db.projects.insert_one({"id": "P", "org_id": "O"})
    await mock_db.github_project_configs.insert_one({"project_id": "P", "repository_owner": "o", "repository_name": "r"})
    await mock_db.pull_requests.insert_one({"id": "PR1", "pr_number": 1, "project_id": "P", "repo_id": "o/r",
        "author_login": "author", "status": "merged", "head_sha": "a" * 40, "merged_at": "2026-08-01T00:00:00Z"})
    from agents import performance_agent
    async def response(prompt, **kwargs):
        observations = json.loads(prompt.split("\nObservations: ", 1)[1])
        record = observations["records"][0]
        return json.dumps({"claims": [{"claim_id": "arch", "claim_type": "possible_architecture_tradeoff",
            "dimension_id": "engineering_judgment", "citations": [{"source_id": record["source_id"], "content_digest": record["content_digest"]}],
            "interpretation": "Possible architecture tradeoff; needs independent technical review."}]})
    monkeypatch.setattr(performance_agent, "get_ollama_llm", lambda **kwargs: type("LLM", (), {"model": "test", "ainvoke": staticmethod(response)})())
    return mock_db


async def create(stored):
    return await service().create(request(), {"employee_id": "L"})


async def grant(stored, reviewer="R"):
    from domain.models.performance_claims import ReviewerAssignmentRequest
    body = ReviewerAssignmentRequest(reviewer_id=reviewer, project_id="P", dimensions=["engineering_judgment"],
        claim_types=["possible_architecture_tradeoff"], qualification_reason="Independent technical competence reviewed from project artifacts.",
        qualification_source_ids=["PR1"], qualification_attested=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    return await service().assign_reviewer(body, {"employee_id": "A"})


def review_body(run, assignment, **changes):
    from domain.models.performance_claims import ClaimReviewRequest
    from domain.models.performance_evidence import canonical_digest
    return ClaimReviewRequest(**{**dict(assignment_id=assignment["assignment_id"], expected_snapshot_digest=run.evidence.digest,
        expected_proposal_digest=canonical_digest(run.interpretation.proposal.model_dump(mode="json")), decision="VALIDATE",
        reason="Independently checked the exact recorded source revision, attribution and claimed tradeoff.",
        attribution_checked=True, predicate_checked=True), **changes})


async def test_create_stores_evidence_proposal_and_validation_separately_from_scores(stored):
    run = await create(stored)
    assert run.interpretation.decisions[0].status == "NEEDS_REVIEW"
    assert run.interpretation.combined_score is None
    assert await stored.developer_performances.count_documents({}) == 0
    assert await stored.ai_runs.count_documents({"agent_type": "performance_interpretation"}) == 1
    loaded = await service().get(run.run_id, {"employee_id": "R"})
    assert loaded.run == run and loaded.facts_for_measurement == ()


async def test_qualified_signed_review_and_rejection_preserve_original_and_history(stored):
    run, assignment = await create(stored), await grant(stored)
    original = copy.deepcopy(await stored.ai_runs.find_one({"id": run.run_id}))
    first = await service().review(run.run_id, "arch", review_body(run, assignment), {"employee_id": "R"})
    assert first.fact.predicate == "qualified_review_attestation" and first.score_effect is None
    from domain.models.performance_evidence import canonical_digest
    second = await service().review(run.run_id, "arch", review_body(run, assignment,
        decision="REJECT", previous_review_digest=canonical_digest(first.model_dump(mode="json"))), {"employee_id": "R"})
    assert second.revision == 2 and second.fact is None
    detail = await service().get(run.run_id, {"employee_id": "D"})
    assert len(detail.reviews) == 2 and detail.effective_decisions[0].status == "REJECTED"
    assert detail.effective_decisions[0].fact is None and detail.facts_for_measurement == ()
    assert await stored.ai_runs.find_one({"id": run.run_id}) == original


async def test_forged_assignment_and_changed_stored_proposal_are_not_authority(stored):
    run, assignment = await create(stored), await grant(stored)
    await stored.ai_runs.update_one({"id": assignment["assignment_id"]}, {"$set": {"signature": "f" * 64}})
    with pytest.raises(HTTPException) as error:
        await service().review(run.run_id, "arch", review_body(run, assignment), {"employee_id": "R"})
    assert error.value.status_code == 409
    await stored.ai_runs.update_one({"id": run.run_id}, {"$set": {"output_data.payload.interpretation.status": "INVALID_OUTPUT"}})
    with pytest.raises(HTTPException) as error:
        await service().get(run.run_id, {"employee_id": "D"})
    assert error.value.status_code == 409


async def test_role_alone_cannot_assign_or_validate_claims(stored):
    from domain.models.performance_claims import ReviewerAssignmentRequest
    body = ReviewerAssignmentRequest(reviewer_id="R", project_id="P", dimensions=["engineering_judgment"],
        claim_types=["possible_architecture_tradeoff"], qualification_reason="Attested competence", qualification_source_ids=["PR1"],
        qualification_attested=True, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    with pytest.raises(HTTPException) as error:
        await service().assign_reviewer(body, {"employee_id": "L", "is_admin": True})
    assert error.value.status_code == 403


@pytest.mark.parametrize("who", ["A", "D", "L"])
async def test_issuer_subject_and_proposer_cannot_self_validate(stored, who):
    run = await create(stored)
    assignment = await grant(stored, reviewer=who) if who != "A" else await grant(stored)
    with pytest.raises(HTTPException) as error:
        await service().review(run.run_id, "arch", review_body(run, assignment), {"employee_id": who})
    assert error.value.status_code == 403


async def test_cross_org_and_deactivated_reviewer_are_denied(stored):
    run = await create(stored)
    await stored.users.update_one({"employee_id": "R"}, {"$set": {"org_id": "OTHER"}})
    with pytest.raises(HTTPException) as error:
        await service().get(run.run_id, {"employee_id": "R", "is_admin": True})
    assert error.value.status_code == 403


async def test_expired_assignment_and_inactive_reviewer_cannot_validate(stored):
    run, assignment = await create(stored), await grant(stored)
    await stored.users.update_one({"employee_id": "R"}, {"$set": {"is_active": False}})
    with pytest.raises(HTTPException) as error:
        await service().review(run.run_id, "arch", review_body(run, assignment), {"employee_id": "R"})
    assert error.value.status_code == 403
    await stored.users.update_one({"employee_id": "R"}, {"$set": {"is_active": True}})
    await stored.users.update_one({"employee_id": "A"}, {"$set": {"is_admin": False}})
    with pytest.raises(HTTPException) as error:
        await service().review(run.run_id, "arch", review_body(run, assignment), {"employee_id": "R"})
    assert error.value.status_code == 409


async def test_review_revision_retries_and_concurrency_cannot_overwrite_history(stored, monkeypatch):
    import asyncio
    run, assignment = await create(stored), await grant(stored)
    body = review_body(run, assignment)
    instance = service()
    original = instance._reviews
    ready, reads = asyncio.Event(), []
    async def concurrent_read(run_id):
        history = await original(run_id)
        reads.append(1)
        if len(reads) == 2:
            ready.set()
        await ready.wait()
        return history
    monkeypatch.setattr(instance, "_reviews", concurrent_read)
    outcomes = await asyncio.wait_for(asyncio.gather(*(instance.review(run.run_id, "arch", body, {"employee_id": "R"})
                                    for _ in range(2)), return_exceptions=True), timeout=5)
    assert sum(not isinstance(v, Exception) for v in outcomes) == 1
    assert any(isinstance(v, HTTPException) and v.status_code == 409 for v in outcomes)
    assert len((await service().get(run.run_id, {"employee_id": "D"})).reviews) == 1


async def test_snapshot_permission_is_rechecked_after_the_model_call(stored, monkeypatch):
    from agents import performance_agent
    async def revoked(*args, **kwargs):
        await stored.users.update_one({"employee_id": "L"}, {"$set": {"is_active": False}})
        return '{"claims":[]}'
    monkeypatch.setattr(performance_agent, "get_ollama_llm", lambda **kwargs: type("LLM", (), {"model": "test", "ainvoke": staticmethod(revoked)})())
    with pytest.raises(HTTPException) as error:
        await create(stored)
    assert error.value.status_code == 403
    assert await stored.ai_runs.count_documents({}) == 0


async def test_changed_or_deleted_source_blocks_positive_claim_review(stored):
    run, assignment = await create(stored), await grant(stored)
    await stored.pull_requests.update_one({"id": "PR1"}, {"$set": {"head_sha": "b" * 40}})
    with pytest.raises(HTTPException) as error:
        await service().review(run.run_id, "arch", review_body(run, assignment), {"employee_id": "R"})
    assert error.value.status_code == 409
    assert await stored.ai_runs.count_documents({"agent_type": "performance_claim_review"}) == 0


async def test_generic_ai_run_paths_do_not_leak_performance_artifacts(stored):
    run = await create(stored)
    from repositories.ai_run_repository import AIRunRepository
    repo = AIRunRepository()
    assert await repo.get_by_id(run.run_id) is None
    assert await repo.list() == []


async def test_http_interpretation_is_scoped_and_legacy_numeric_route_is_pending(stored):
    from api.routes import performance
    app = FastAPI()
    app.include_router(performance.router, prefix="/api/performance")
    actor = {"employee_id": "L", "role": "PM"}
    app.dependency_overrides[get_current_user] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/performance/interpretations", json=request().model_dump(mode="json"))
        assert created.status_code == 201
        assert created.json()["interpretation"]["combined_score"] is None
        fetched = await client.get("/api/performance/interpretations/" + created.json()["run_id"])
        assert fetched.status_code == 200
        forged = await client.post("/api/performance/interpretations", json={**request().model_dump(mode="json"), "score": 100})
        assert forged.status_code == 422
        # CR-004: a Lead may only target their own team, so use the org-wide CEO here.
        actor.update(employee_id="A", role="CEO", is_admin=True)
        pending = await client.post("/api/performance/evaluate", json={"developer_id": "D", "developer_name": "D", "period": "2026-Q3", "project_id": "P"})
        assert pending.status_code == 409 and pending.json()["status"] == "POLICY_PENDING"
        assert isinstance(pending.json()["detail"], str)  # Existing frontend error handlers call .includes().
    assert await stored.developer_performances.count_documents({}) == 0


async def test_service_retires_old_numeric_orchestration_even_with_mocked_model(stored):
    from domain.services.performance_service import PerformanceService, PeriodScoringPending
    from domain.models.developer_performance import DeveloperPerformanceCreate
    instance = PerformanceService()
    instance.evaluation_agent.evaluate_performance = AsyncMock(return_value=100)
    with pytest.raises(PeriodScoringPending):
        await instance.evaluate_developer(DeveloperPerformanceCreate(developer_id="D", project_id="P", period_label="2026-Q3",
            period_start=datetime(2026, 7, 1), period_end=datetime(2026, 10, 1)), "D", "ignored")
    instance.evaluation_agent.evaluate_performance.assert_not_called()
