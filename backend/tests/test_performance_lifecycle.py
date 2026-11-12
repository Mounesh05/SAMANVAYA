"""Immutable assessment workflow: finite test fixtures do not calibrate employees."""

import importlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from test_performance_human_service import stored as lifecycle_store  # noqa: F401


pytestmark = pytest.mark.anyio


@pytest.fixture
async def stored(lifecycle_store):  # noqa: F811
    return lifecycle_store


def service():
    assert importlib.util.find_spec("domain.services.performance_lifecycle_service"), "Phase 5 lifecycle is missing"
    return importlib.import_module("domain.services.performance_lifecycle_service").AssessmentLifecycleService()


async def create(run):
    return await service().create({"run_id": run.run_id, "reason": "Inspect the exact period evidence"}, {"employee_id": "A"})


def transition(head, action, **changes):
    return {**dict(expected_digest=head["digest"], request_id=action.lower(), action=action,
                  reason="Explicit scoped workflow action"), **changes}


async def test_creation_is_scoped_idempotent_and_no_legacy_row_is_written(stored):
    db, run = stored
    first = await create(run)
    second = await create(run)
    assert first == second and first["state"] == "DRAFT"
    assert first["approved_score"] is None
    assert await db.developer_performances.count_documents({}) == 0


async def test_invalid_draft_approval_and_stale_revision_are_denied(stored):
    _, run = stored
    first = await create(run)
    with pytest.raises(HTTPException) as error:
        await service().transition(first["assessment_id"], transition(first, "APPROVE"), {"employee_id": "A"})
    assert error.value.status_code == 403  # Authority is checked before workflow state.
    collecting = await service().transition(first["assessment_id"], transition(first, "COLLECT"), {"employee_id": "A"})
    assert collecting["revision"] == 2 and collecting["state"] == "EVIDENCE_COLLECTING"
    with pytest.raises(HTTPException) as error:
        await service().transition(first["assessment_id"], transition(first, "CANCEL"), {"employee_id": "A"})
    assert error.value.status_code == 409


async def test_unverified_snapshot_cannot_be_promoted_to_validated_or_approved(stored):
    _, run = stored
    head = await create(run)
    head = await service().transition(head["assessment_id"], transition(head, "COLLECT"), {"employee_id": "A"})
    with pytest.raises(HTTPException) as error:
        await service().transition(head["assessment_id"], transition(head, "VALIDATE"), {"employee_id": "A"})
    assert error.value.status_code == 409


async def test_subject_appeal_and_manager_correction_preserve_all_prior_revisions(stored):
    db, run = stored
    first = await create(run)
    disputed = await service().appeal(first["assessment_id"], {
        "expected_digest": first["digest"], "request_id": "appeal-1", "reason": "The cited attribution needs factual correction",
        "evidence_references": ["task:case-reference"]}, {"employee_id": "D"})
    assert disputed["state"] == "DISPUTED" and disputed["approved_score"] is None
    corrected = await service().transition(first["assessment_id"], transition(disputed, "CORRECT", run_id=run.run_id), {"employee_id": "A"})
    assert corrected["state"] == "DRAFT" and corrected["revision"] == 3
    history = await service().get(first["assessment_id"], {"employee_id": "D"})
    assert [r["state"] for r in history["history"]] == ["DRAFT", "DISPUTED", "DRAFT"]
    assert await db.developer_performances.count_documents({}) == 0


async def test_duplicate_concurrent_actions_have_one_immutable_effect(stored):
    import asyncio
    db, run = stored
    first = await create(run)
    body = transition(first, "COLLECT")
    results = await asyncio.gather(*(service().transition(first["assessment_id"], body, {"employee_id": "A"}) for _ in range(2)))
    assert results[0] == results[1] and results[0]["revision"] == 2
    assert await db.ai_runs.count_documents({"agent_type": "performance_assessment_event"}) == 2


async def test_cross_org_and_stale_role_cannot_read_or_change_lifecycle(stored):
    db, run = stored
    first = await create(run)
    await db.users.update_one({"employee_id": "R"}, {"$set": {"org_id": "OTHER"}})
    with pytest.raises(HTTPException) as error:
        await service().get(first["assessment_id"], {"employee_id": "R", "role": "CEO", "is_admin": True})
    assert error.value.status_code == 403
    await db.users.update_one({"employee_id": "A"}, {"$set": {"is_admin": False}})
    with pytest.raises(HTTPException):
        await service().transition(first["assessment_id"], transition(first, "COLLECT"), {"employee_id": "A", "is_admin": True})


async def test_forged_event_and_generic_ai_access_fail_closed(stored):
    db, run = stored
    first = await create(run)
    from repositories.ai_run_repository import AIRunRepository
    key = first["event_id"]
    assert await AIRunRepository().get_by_id(key) is None
    await db.ai_runs.update_one({"id": key}, {"$set": {"output_data.payload.state": "APPROVED"}})
    with pytest.raises(HTTPException) as error:
        await service().get(first["assessment_id"], {"employee_id": "D"})
    assert error.value.status_code == 409


async def test_approver_must_be_independent_assigned_current_and_not_ceo(stored):
    _, run = stored
    head = await create(run)
    body = dict(reviewer_id="R", qualification_reason="Independent technical review qualification attested",
                qualification_source_ids=[run.evidence.snapshot.records[0].source_id],
                no_conflict_attested=True, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    grant = await service().assign_approver(head["assessment_id"], body, {"employee_id": "A"})
    assert grant["reviewer_id"] == "R"
    for actor in ("D", "C", "H"):
        with pytest.raises(HTTPException):
            await service().assign_approver(head["assessment_id"], body, {"employee_id": actor, "is_admin": True})


async def test_policy_review_does_not_activate_uncalibrated_weights(stored):
    _, run = stored
    from test_performance_human import policy
    from domain.services.performance_human_service import HumanFeedbackService
    draft = await HumanFeedbackService().propose_policy(dict(project_id="P", policy=policy(status="DRAFT"), reason="Synthetic draft"), {"employee_id": "A"})
    head = await service().review_policy(draft["draft_id"], {"reason": "Independent policy review",
        "effective_from": datetime.now(timezone.utc) + timedelta(days=1)}, {"employee_id": "R"})
    assert head["status"] == "REVIEWED_INACTIVE" and head["is_active"] is False
    with pytest.raises(HTTPException):
        await service().review_policy(draft["draft_id"], {"reason": "Self approval",
            "effective_from": datetime.now(timezone.utc) + timedelta(days=1)}, {"employee_id": "A"})


async def trusted_measurement(stored, head):
    """Synthetic Phase 6 adapter output. No production measurement adapter is installed."""
    from domain.models.performance_scoring import CalculationSnapshot, AssessmentIdentity, CoverageSummary, VersionReference, SnapshotReference, ScoreValue
    from domain.models.performance_human import EligibleHumanReview
    from domain.models.performance_evidence import canonical_digest
    from domain.services.performance_artifact_store import _write
    from domain.services.performance_human_service import HumanFeedbackService
    from intelligence.performance_human import aggregate_human_reviews
    from test_performance_human import policy
    from test_performance_human_service import assignment, body
    db, run = stored
    scope = run.evidence.snapshot.scope
    context = {"organization_id": "O", "project_id": "P"}
    p = policy(status="DRAFT")
    draft = await _write("performance_human_policy_draft", dict(project_id="P", reason="Synthetic historical calibration fixture",
        policy=p.model_dump(mode="json")), context, "A")
    review = await _write("performance_policy_review", {"draft_id": draft["id"], "draft_digest": canonical_digest(draft),
        "effective_from": "2026-07-01T00:00:00+00:00", "status": "REVIEWED_INACTIVE", "is_active": False}, context, "R")
    release = await _write("performance_scoring_release", dict(policy_draft_id=draft["id"], policy_draft_digest=canonical_digest(draft),
        policy_review_id=review["id"], policy_review_digest=canonical_digest(review), rubric={"id": "synthetic-rubric", "version": "test"},
        subject_role="DEVELOPER", measurement_method={"id": "synthetic-measurement", "version": "test"}, minimum_engineering_coverage=100,
        calibration_source_refs=["synthetic-approved-calibration-fixture"], effective_from="2026-07-01T00:00:00Z",
        effective_until="2026-10-01T00:00:00Z"), context, "scoring-calibration-service")
    rows, refs = [], []
    for role, actor in (("LEAD", "R"), ("HR", "H")):
        grant = await HumanFeedbackService().assign(assignment(run, role), {"employee_id": "A"})
        result = await HumanFeedbackService().submit(grant["assignment_id"], body(role), {"employee_id": actor})
        refs.append(result["review_id"])
        rows.append(EligibleHumanReview(assignment_id=grant["assignment_id"], reviewer_id=actor, role=role, eligibility="ELIGIBLE",
            observations=body(role).observations, validated_dimensions=[o.dimension for o in body(role).observations]))
    calculation = aggregate_human_reviews(p.model_copy(update={"status": "APPROVED"}), tuple(rows), ScoreValue(unit="PERIOD_0_100", value=86)).calculation
    snapshot = CalculationSnapshot(identity=AssessmentIdentity(assessment_id=head["assessment_id"], revision=1, organization_id="O", employee_id="D",
        employee_role_at_period="DEVELOPER", project_ids=["P"], rubric_profile_id="synthetic-rubric", period_start=scope.period_start, period_end=scope.period_end),
        methodology=VersionReference(id="synthetic-measurement", version="test"), rubric=VersionReference(id="synthetic-rubric", version="test"),
        policy=VersionReference(id=p.policy_id, version=p.version), evidence=SnapshotReference(id=run.run_id, digest=run.evidence.digest),
        coverage=CoverageSummary(engineering_percent=100, human_completeness="COMPLETE", policy=VersionReference(id=p.policy_id, version=p.version)),
        calculation=calculation)
    measurement = await _write("performance_measurement", dict(run_id=run.run_id, release_id=release["id"], snapshot=snapshot.model_dump(mode="json"),
        human_reviews=[r.model_dump(mode="json") for r in rows], human_review_ids=refs),
        {**context, "employee_id": "D"}, "scoring-measurement-service")
    await db.users.insert_one(dict(employee_id="FINAL", role="PM", org_id="O", is_active=True, project_ids=["P"]))
    approver = await service().assign_approver(head["assessment_id"], dict(reviewer_id="FINAL", qualification_reason="Independent review qualification",
        qualification_source_ids=[run.evidence.snapshot.records[0].source_id], no_conflict_attested=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1)), {"employee_id": "A"})
    return measurement["id"], approver["assignment_id"]


async def test_trusted_frozen_measurement_can_be_replayed_and_independently_approved(stored):
    _, run = stored
    head = await create(run)
    measurement_id, approver = await trusted_measurement(stored, head)
    for action in ("COLLECT", "VALIDATE", "ELIGIBLE", "CALCULATE"):
        head = await service().transition(head["assessment_id"], transition(head, action, measurement_id=measurement_id), {"employee_id": "A"})
    assert head["provisional_score"] == 85.4 and head["approved_score"] is None
    for action in ("REVIEW", "APPROVE"):
        head = await service().transition(head["assessment_id"], transition(head, action, assignment_id=approver), {"employee_id": "FINAL"})
    assert head["state"] == "APPROVED" and head["approved_score"] == 85.4
    summary = await service().get(head["assessment_id"], {"employee_id": "C"})
    assert summary["current"]["approved_score"] == 85.4 and "observations" not in str(summary)
    assert hasattr(service(), "replay"), "Approved frozen calculations need a reproducibility API"
    replay = await service().replay(head["assessment_id"], head["revision"], {"employee_id": "D"})
    assert replay["status"] == "REPRODUCED" and replay["calculation"]["combined_score"]["value"] == 85.4
    db, _ = stored
    await db.users.update_one({"employee_id": "D"}, {"$set": {"role": "HR"}})
    own_history = await service().get(head["assessment_id"], {"employee_id": "D"})
    assert own_history["current"]["approved_score"] == 85.4
    await db.users.update_one({"employee_id": "D"}, {"$set": {"role": "DEVELOPER"}})
    disputed = await service().appeal(head["assessment_id"], dict(expected_digest=head["digest"], request_id="dispute-approved",
        reason="Please review the attribution of this source", evidence_references=[]), {"employee_id": "D"})
    assert disputed["state"] == "DISPUTED"
    summary = await service().get(head["assessment_id"], {"employee_id": "C"})
    assert summary["current"]["state"] == "DISPUTED" and summary["current"]["approved_score"] is None


async def test_frozen_measurement_cannot_be_switched_after_review(stored):
    _, run = stored
    head = await create(run)
    measurement_id, _ = await trusted_measurement(stored, head)
    for action in ("COLLECT", "VALIDATE"):
        head = await service().transition(head["assessment_id"], transition(head, action, measurement_id=measurement_id), {"employee_id": "A"})
    with pytest.raises(HTTPException) as error:
        await service().transition(head["assessment_id"], transition(head, "ELIGIBLE", measurement_id="another-valid-looking-artifact"), {"employee_id": "A"})
    assert error.value.status_code == 409


async def test_two_different_concurrent_actions_cannot_create_branches(stored, monkeypatch):
    import asyncio
    _, run = stored
    first = await create(run)
    workers = [service(), service()]
    ready = asyncio.Event()
    reads = []
    for worker in workers:
        original = worker._history
        async def snapshot(key, original=original):
            rows = await original(key)
            reads.append(1)
            if len(reads) == 2:
                ready.set()
            await ready.wait()
            return rows
        monkeypatch.setattr(worker, "_history", snapshot)
    results = await asyncio.gather(workers[0].transition(first["assessment_id"], transition(first, "COLLECT"), {"employee_id": "A"}),
        workers[1].transition(first["assessment_id"], transition(first, "CANCEL"), {"employee_id": "A"}), return_exceptions=True)
    assert len([r for r in results if isinstance(r, dict)]) == 1
    assert len([r for r in results if isinstance(r, HTTPException) and r.status_code == 409]) == 1
    assert len((await service().get(first["assessment_id"], {"employee_id": "D"}))["history"]) == 2


async def test_corrected_human_input_blocks_stale_measurement_approval(stored):
    from domain.models.performance_evidence import canonical_digest
    from domain.services.performance_artifact_store import _read
    from domain.services.performance_human_service import HumanFeedbackService
    from test_performance_human_service import body
    _, run = stored
    head = await create(run)
    measurement_id, _ = await trusted_measurement(stored, head)
    frozen = await _read(measurement_id, "performance_measurement")
    original = await _read(frozen["payload"]["human_review_ids"][0], "performance_human_review")
    assigned = original["payload"]["assignment_id"]
    updated = body().model_dump()
    updated["observations"][0]["rating"] = 3
    await HumanFeedbackService().revise(assigned, {**updated, "expected_digest": canonical_digest(original),
        "request_id": "correct-source", "reason": "Correcting the observed assessment"}, {"employee_id": "R"})
    head = await service().transition(head["assessment_id"], transition(head, "COLLECT"), {"employee_id": "A"})
    with pytest.raises(HTTPException) as error:
        await service().transition(head["assessment_id"], transition(head, "VALIDATE", measurement_id=measurement_id), {"employee_id": "A"})
    assert error.value.status_code == 409


async def test_lifecycle_api_never_accepts_direct_scores_or_approval_flags(stored):
    import httpx
    from fastapi import FastAPI
    from api.routes import performance
    from core.dependencies import get_current_user
    _, run = stored
    head = await create(run)
    app = FastAPI()
    app.include_router(performance.router, prefix="/api/performance")
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "A"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/performance/assessments/{head['assessment_id']}/actions",
            json={**transition(head, "COLLECT"), "approved_score": 100, "is_approved": True})
        assert response.status_code == 422
        response = await client.get(f"/api/performance/assessments/{head['assessment_id']}/history")
        assert response.status_code == 200 and response.json()["current"]["state"] == "DRAFT"


def appeal_body(head, request_id):
    return dict(expected_digest=head["digest"], request_id=request_id, reason="Please review the attribution of this source",
                evidence_references=[])


async def test_cancelled_or_already_disputed_assessment_cannot_be_appealed_again(stored):
    _, run = stored
    first = await create(run)
    disputed = await service().appeal(first["assessment_id"], appeal_body(first, "appeal-1"), {"employee_id": "D"})
    retry = await service().appeal(first["assessment_id"], appeal_body(first, "appeal-1"), {"employee_id": "D"})
    assert retry == disputed  # An exact retry still returns the original receipt.
    with pytest.raises(HTTPException) as error:
        await service().appeal(first["assessment_id"], appeal_body(disputed, "appeal-2"), {"employee_id": "D"})
    assert error.value.status_code == 409
    corrected = await service().transition(first["assessment_id"], transition(disputed, "CORRECT", run_id=run.run_id), {"employee_id": "A"})
    cancelled = await service().transition(first["assessment_id"], transition(corrected, "CANCEL"), {"employee_id": "A"})
    with pytest.raises(HTTPException) as error:
        await service().appeal(first["assessment_id"], appeal_body(cancelled, "appeal-3"), {"employee_id": "D"})
    assert error.value.status_code == 409
    assert len((await service().get(first["assessment_id"], {"employee_id": "D"}))["history"]) == 4


async def test_restating_an_approved_assessment_requires_the_independent_approver(stored):
    _, run = stored
    head = await create(run)
    measurement_id, approver = await trusted_measurement(stored, head)
    for action in ("COLLECT", "VALIDATE", "ELIGIBLE", "CALCULATE"):
        head = await service().transition(head["assessment_id"], transition(head, action, measurement_id=measurement_id), {"employee_id": "A"})
    for action in ("REVIEW", "APPROVE"):
        head = await service().transition(head["assessment_id"], transition(head, action, assignment_id=approver), {"employee_id": "FINAL"})
    assert head["state"] == "APPROVED"
    with pytest.raises(HTTPException) as error:
        await service().transition(head["assessment_id"], transition(head, "CORRECT", run_id=run.run_id), {"employee_id": "A"})
    assert error.value.status_code == 403  # The initiating administrator alone cannot void an approval.
    corrected = await service().transition(head["assessment_id"],
        transition(head, "CORRECT", run_id=run.run_id, assignment_id=approver), {"employee_id": "FINAL"})
    assert corrected["state"] == "DRAFT" and corrected["approved_score"] is None


async def test_expired_approver_grant_can_be_renewed_for_the_same_reviewer(stored):
    _, run = stored
    head = await create(run)

    def grant(expires_at):
        return dict(reviewer_id="R", qualification_reason="Independent technical review qualification attested",
                    qualification_source_ids=[run.evidence.snapshot.records[0].source_id],
                    no_conflict_attested=True, expires_at=expires_at)

    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    first = await service().assign_approver(head["assessment_id"], grant(expiry), {"employee_id": "A"})
    assert await service().assign_approver(head["assessment_id"], grant(expiry), {"employee_id": "A"}) == first
    renewed = await service().assign_approver(head["assessment_id"], grant(expiry + timedelta(days=2)), {"employee_id": "A"})
    assert renewed["reviewer_id"] == "R" and renewed["assignment_id"] != first["assignment_id"]


async def test_subject_cannot_manage_own_workflow_after_becoming_an_admin(stored):
    db, run = stored
    head = await create(run)
    await db.users.update_one({"employee_id": "D"}, {"$set": {"role": "LEAD", "is_admin": True}})
    with pytest.raises(HTTPException) as error:
        await service().transition(head["assessment_id"], transition(head, "COLLECT"), {"employee_id": "D"})
    assert error.value.status_code == 403
