"""Scoped, server-signed AI proposals and independent claim review history."""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core.config import settings
from core.database import col
from domain.models.performance_claims import (
    ClaimReview, ClaimReviewRequest, ClaimValidation, Interpretation, InterpretationDetails,
    InterpretationRun, ReviewerAssignmentRequest, ValidatedClaimFact,
)
from domain.models.performance_evidence import EvidencePreviewRequest, canonical_digest
from domain.services.performance_service import PerformanceService

def _signature(record):
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), canonical_digest(record).encode("ascii"), hashlib.sha256).hexdigest()


def _context(scope):
    return {"organization_id": scope.organization_id, "project_id": scope.project_id, "employee_id": scope.employee_id}


async def _write(kind, payload, context, actor, artifact_id=None):
    key = artifact_id or "PC-" + uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    record = {"schema_version": "performance-claim-artifact-v1", "signature_method": "HMAC-SHA256-v1",
              "id": key, "kind": kind, "context": context, "payload": payload,
              "created_by": actor, "created_at": now}
    document = {"_id": key, "id": key, "agent_type": kind, "input_data": {"context": context},
        "output_data": record, "signature": _signature(record), "status": "completed", "model_name": "advisory",
        "triggered_by": actor, "created_at": now, "updated_at": now}
    try:
        await col("ai_runs").insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(409, "A concurrent review already created this revision") from None
    return record


def _verify(document, kind):
    record = (document or {}).get("output_data")
    signature = (document or {}).get("signature")
    if (not isinstance(record, dict) or record.get("schema_version") != "performance-claim-artifact-v1"
            or record.get("signature_method") != "HMAC-SHA256-v1"
            or record.get("kind") != kind or record.get("id") != document.get("id")
            or document.get("agent_type") != kind or not isinstance(signature, str)
            or not hmac.compare_digest(signature, _signature(record))):
        raise HTTPException(409, "Performance artifact integrity or server authority could not be verified")
    return record


async def _read(key, kind):
    doc = await col("ai_runs").find_one({"id": key, "agent_type": kind}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Performance artifact not found")
    return _verify(doc, kind)


class PerformanceClaimService:
    async def create(self, request, actor):
        from agents.performance_agent import PerformanceEvaluationAgent
        evidence = await PerformanceService.inspect_evidence(request, actor)
        try:
            agent = PerformanceEvaluationAgent()
        except Exception:
            interpretation = Interpretation(status="UNAVAILABLE", snapshot_digest=evidence.digest,
                model_id=str(settings.OLLAMA_MODEL)[:500] or "unknown")
        else:
            interpretation = await agent.interpret_snapshot(evidence.snapshot)
        # Recheck permission after a potentially slow model operation.
        _, _, current = await PerformanceService.authorize_evidence(request, actor)
        run = InterpretationRun(run_id="PINT-" + uuid.uuid4().hex, evidence=evidence, interpretation=interpretation,
            created_at=datetime.now(timezone.utc), created_by=current["employee_id"])
        await _write("performance_interpretation", run.model_dump(mode="json"), _context(evidence.snapshot.scope),
                     current["employee_id"], run.run_id)
        return run

    async def _authorized_run(self, run_id, actor):
        record = await _read(run_id, "performance_interpretation")
        run = InterpretationRun.model_validate(record["payload"])
        saved = run.evidence.snapshot.scope
        request = EvidencePreviewRequest(employee_id=saved.employee_id, project_id=saved.project_id,
            period_start=saved.period_start, period_end=saved.period_end)
        scope, subject, current = await PerformanceService.authorize_evidence(request, actor)
        if scope.organization_id != saved.organization_id or scope.repository != saved.repository:
            raise HTTPException(409, "The source organization or repository mapping changed")
        return run, subject, current

    async def assign_reviewer(self, request, actor):
        request = ReviewerAssignmentRequest.model_validate(request)
        current = await col("users").find_one({"employee_id": actor.get("employee_id")}, {"_id": 0})
        if (not current or current.get("is_active") is not True or current.get("is_admin") is not True
                or current.get("role") not in {"LEAD", "PM"} or current.get("employee_id") == request.reviewer_id):
            raise HTTPException(403, "An independent current technical administrator must attest reviewer qualifications")
        now = datetime.now(timezone.utc)
        if request.expires_at <= now:
            raise HTTPException(422, "Reviewer assignment must have a future expiry")
        check = EvidencePreviewRequest(employee_id=request.reviewer_id, project_id=request.project_id,
            period_start=now, period_end=request.expires_at)
        scope, _, _ = await PerformanceService.authorize_evidence(check, actor)
        for reference in request.qualification_source_ids:
            source = await col("pull_requests").find_one({"id": reference, "project_id": scope.project_id,
                "$or": [{"org_id": scope.organization_id}, {"org_id": {"$exists": False}}]}, {"_id": 1})
            if not source:
                source = await col("code_quality_runs").find_one({"run_id": reference,
                    "$and": [{"$or": [{"project_id": scope.project_id}, {"repository_id": scope.project_id}]},
                             {"$or": [{"org_id": scope.organization_id}, {"org_id": {"$exists": False}}]}]}, {"_id": 1})
            if not source:
                raise HTTPException(422, "Qualification references must resolve to existing authorized project artifacts")
        record = await _write("performance_claim_assignment", request.model_dump(mode="json"),
                              _context(scope), current["employee_id"])
        return {"assignment_id": record["id"], "reviewer_id": request.reviewer_id,
                "expires_at": request.expires_at.isoformat(), "authority_basis": "EXPLICIT_TECHNICAL_ADMIN_QUALIFICATION_ATTESTATION"}

    async def _assignment(self, assignment_id, run, current):
        record = await _read(assignment_id, "performance_claim_assignment")
        request = ReviewerAssignmentRequest.model_validate(record["payload"])
        scope = run.evidence.snapshot.scope
        if (record["context"]["organization_id"] != scope.organization_id
                or request.project_id != scope.project_id or request.reviewer_id != current["employee_id"]
                or current["employee_id"] in {scope.employee_id, run.created_by, record["created_by"]}):
            raise HTTPException(403, "Claim review requires an independent assigned reviewer in the exact scope")
        issuer = await col("users").find_one({"employee_id": record["created_by"], "org_id": scope.organization_id},
            {"_id": 0, "is_active": 1, "is_admin": 1, "role": 1})
        if (request.expires_at <= datetime.now(timezone.utc) or not issuer or issuer.get("is_active") is not True
                or issuer.get("is_admin") is not True or issuer.get("role") not in {"LEAD", "PM"}):
            raise HTTPException(409, "Reviewer qualification assignment expired or its authority was revoked")
        return request

    async def _reviews(self, run_id):
        documents = await col("ai_runs").find({"agent_type": "performance_claim_review",
            "output_data.payload.run_id": run_id}, {"_id": 0}).limit(1601).to_list(1601)
        if len(documents) > 1600:
            raise HTTPException(409, "Claim review history exceeds its supported bound")
        values = [ClaimReview.model_validate(_verify(d, "performance_claim_review")["payload"]) for d in documents]
        return tuple(sorted(values, key=lambda r: (r.claim_id, r.revision)))

    async def get(self, run_id, actor):
        run, _, _ = await self._authorized_run(run_id, actor)
        reviews = await self._reviews(run_id)
        decisions = {d.claim_id: d for d in run.interpretation.decisions}
        for review in reviews:
            decisions[review.claim_id] = ClaimValidation(claim_id=review.claim_id,
                status="REJECTED" if review.decision == "REJECT" else "VALIDATED", fact=review.fact,
                reasons=("SIGNED_INDEPENDENT_REVIEW_REVISION_" + str(review.revision),))
        return InterpretationDetails(run=run, reviews=reviews, effective_decisions=tuple(decisions.values()))

    async def review(self, run_id, claim_id, request, actor):
        request = ClaimReviewRequest.model_validate(request)
        run, _, current = await self._authorized_run(run_id, actor)
        assignment = await self._assignment(request.assignment_id, run, current)
        proposal = run.interpretation.proposal
        proposal_digest = canonical_digest(proposal.model_dump(mode="json")) if proposal else None
        if request.expected_snapshot_digest != run.evidence.digest or request.expected_proposal_digest != proposal_digest:
            raise HTTPException(409, "Claim review must bind the exact stored proposal and snapshot")
        claim = next((c for c in proposal.claims if c.claim_id == claim_id), None) if proposal else None
        if not claim:
            raise HTTPException(404, "Claim not found")
        if claim.dimension_id not in assignment.dimensions or claim.claim_type not in assignment.claim_types:
            raise HTTPException(403, "Reviewer qualification does not cover this claim type and dimension")
        original = next(d for d in run.interpretation.decisions if d.claim_id == claim_id)
        fact = None
        if request.decision == "VALIDATE":
            if not request.attribution_checked or not request.predicate_checked or original.status == "REJECTED":
                raise HTTPException(409, "A contradicted claim or incomplete independent verification cannot be validated")
            if claim.claim_type in {"possible_benchmark_improvement", "possible_regression_fixed"}:
                raise HTTPException(409, "A specialized correctness/comparability or defect-to-test validator is required")
            scope = run.evidence.snapshot.scope
            fresh = await PerformanceService.inspect_evidence(EvidencePreviewRequest(employee_id=scope.employee_id,
                project_id=scope.project_id, period_start=scope.period_start, period_end=scope.period_end), actor)
            current_sources = {(r.source_id, r.content_digest) for r in fresh.snapshot.records
                               if r.state not in {"REJECTED", "STALE", "DISPUTED"}}
            if any((c.source_id, c.content_digest) not in current_sources for c in claim.citations):
                raise HTTPException(409, "A cited source changed or became unavailable; create a fresh interpretation")
            fact = ValidatedClaimFact(predicate="qualified_review_attestation", citations=claim.citations,
                snapshot_digest=run.evidence.digest, attested_claim_digest=canonical_digest(claim.model_dump(mode="json")))
        previous = [r for r in await self._reviews(run_id) if r.claim_id == claim_id]
        latest = previous[-1] if previous else None
        expected_previous = canonical_digest(latest.model_dump(mode="json")) if latest else None
        if request.previous_review_digest != expected_previous:
            raise HTTPException(409, "Claim review history changed; reload before creating a new revision")
        revision = latest.revision + 1 if latest else 1
        if revision > 100:
            raise HTTPException(409, "Claim review revision bound reached")
        key = "PCR-" + canonical_digest([run_id, claim_id, revision])
        review = ClaimReview(review_id=key, run_id=run_id, claim_id=claim_id, revision=revision,
            previous_review_digest=expected_previous, assignment_id=request.assignment_id,
            reviewer_id=current["employee_id"], snapshot_digest=run.evidence.digest, proposal_digest=proposal_digest,
            decision=request.decision, reason=request.reason, reviewed_at=datetime.now(timezone.utc), fact=fact)
        await _write("performance_claim_review", review.model_dump(mode="json"), _context(run.evidence.snapshot.scope),
                     current["employee_id"], key)
        return review
