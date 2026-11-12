"""Scoped human observation intake, without policy approval or numerical publishing.

The independent issuer attests actual period interaction, not automatic competence
from a job title. Submitted observations remain unverified until their cited
sources and approved anchors are independently validated. No LLM is invoked.
"""

from datetime import datetime, timezone

from fastapi import HTTPException

from core.database import col
from core.permissions import Permission, get_user_permissions
from domain.models.performance_claims import InterpretationRun
from domain.models.performance_evidence import canonical_digest
from domain.models.performance_human import (
    EligibleHumanReview, HumanPolicyDraftRequest, HumanReviewerAssignmentRequest, HumanReviewRequest, HumanReviewRevisionRequest,
)
from domain.services.performance_artifact_store import _context, _read, _verify, _write
from intelligence.performance_human import aggregate_human_reviews


class HumanScoringPending(ValueError):
    def __init__(self, ceo=False):
        super().__init__("CEO routine scoring is disabled; historical records remain readable" if ceo else
            "Human scoring requires an exact-period assignment, approved policy and validated evidence; use assigned human reviews")
        self.status = "CEO_SCORING_DISABLED" if ceo else "POLICY_PENDING"


def _assigned(account, project):
    projects = account.get("project_ids")
    return (isinstance(projects, list) and project["id"] in projects or
            bool(account.get("team_id") and account.get("team_id") == project.get("team_id")))


async def _current(actor):
    current = await col("users").find_one({"employee_id": actor.get("employee_id")}, {"_id": 0})
    if not current or current.get("is_active") is not True or not current.get("org_id"):
        raise HTTPException(403, "An active current organization account is required")
    return current


def _technical_admin(current):
    return current.get("role") in {"LEAD", "PM"} and current.get("is_admin") is True


async def _scoped_run(run_id, current, historical=False):
    record = await _read(run_id, "performance_interpretation")
    run = InterpretationRun.model_validate(record["payload"])
    scope = run.evidence.snapshot.scope
    if record["context"] != _context(scope) or current["org_id"] != scope.organization_id:
        raise HTTPException(403, "Human assessment scope is unavailable or unauthorized")
    project = await col("projects").find_one({"id": scope.project_id, "org_id": scope.organization_id}, {"_id": 0})
    subject = await col("users").find_one({"employee_id": scope.employee_id, "org_id": scope.organization_id}, {"_id": 0})
    if (not project or not subject or not historical and (subject.get("is_active") is not True
            or subject.get("role") not in {"DEVELOPER", "QA", "DEVOPS", "LEAD", "PM"} or not _assigned(subject, project))):
        raise HTTPException(403, "Current engineering subject and project membership are required")
    return run, project


def _reviewer_matches(reviewer, request, project, scope):
    if (not reviewer or reviewer.get("is_active") is not True or reviewer.get("role") != request.role
            or reviewer.get("org_id") != scope.organization_id):
        return False
    if request.role == "HR":
        return Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT in get_user_permissions(
            reviewer["role"], reviewer.get("is_admin", False), reviewer.get("designation"))
    return _assigned(reviewer, project)


async def human_review_history(assignment_id):
    base = "PH-R-" + canonical_digest({"assignment_id": assignment_id})
    docs = await col("ai_runs").find({"agent_type": "performance_human_review",
        "output_data.payload.assignment_id": assignment_id}).limit(101).to_list(101)
    if not docs:
        raise HTTPException(404, "No submitted human review is available")
    if len(docs) > 100:
        raise HTTPException(409, "Human review history requires archival review")
    records = sorted((_verify(d, "performance_human_review") for d in docs), key=lambda r: r["payload"].get("revision", 1))
    for index, record in enumerate(records):
        key = base if index == 0 else f"{base}:{index + 1:06d}"
        if (record["id"] != key or record["context"] != records[0]["context"] or record["created_by"] != records[0]["created_by"]
                or record["payload"].get("revision", 1) != index + 1
                or (index and record["payload"].get("predecessor_digest") != canonical_digest(records[index - 1]))):
            raise HTTPException(409, "Human review history integrity failed")
    return records


class HumanFeedbackService:
    async def assign(self, request, actor):
        request = HumanReviewerAssignmentRequest.model_validate(request)
        current = await _current(actor)
        if not _technical_admin(current):
            raise HTTPException(403, "An independent scoped technical administrator must assign period reviewers")
        run, project = await _scoped_run(request.run_id, current)
        scope = run.evidence.snapshot.scope
        if (not _assigned(current, project) or current["employee_id"] in {scope.employee_id, request.reviewer_id}
                or request.reviewer_id == scope.employee_id):
            raise HTTPException(403, "Self-assignment and subject/issuer conflicts are prohibited")
        reviewer = await col("users").find_one({"employee_id": request.reviewer_id}, {"_id": 0})
        if not _reviewer_matches(reviewer, request, project, scope):
            raise HTTPException(403, "Reviewer current role, organization and project eligibility are required")
        if request.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(422, "An unexpired reviewer assignment is required")
        refs = {(r.source_id, r.content_digest) for r in run.evidence.snapshot.records}
        for evidence in request.interaction_evidence:
            if (not scope.period_start <= evidence.observed_at < scope.period_end
                    or (evidence.source_reference, evidence.source_revision) not in refs):
                raise HTTPException(422, "Interaction references must resolve to the exact period snapshot")
        # One immutable slot per role and snapshot; two reviewers cannot amplify a role.
        key = "PH-A-" + canonical_digest({"run_id": run.run_id, "role": request.role})
        payload = request.model_dump(mode="json")
        try:
            await _write("performance_human_assignment", payload, _context(scope), current["employee_id"], key)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            existing = await _read(key, "performance_human_assignment")
            if (existing["payload"] != payload or existing["created_by"] != current["employee_id"]
                    or existing["context"] != _context(scope)):
                raise HTTPException(409, "A different reviewer assignment already occupies this role and snapshot") from None
        return {"assignment_id": key, "run_id": run.run_id, "reviewer_id": request.reviewer_id,
                "role": request.role, "expires_at": request.expires_at.isoformat(),
                "authority_basis": "EXPLICIT_INDEPENDENT_PERIOD_INTERACTION_ATTESTATION"}

    async def _assignment(self, assignment_id, current):
        record = await _read(assignment_id, "performance_human_assignment")
        request = HumanReviewerAssignmentRequest.model_validate(record["payload"])
        run, project = await _scoped_run(request.run_id, current)
        scope = run.evidence.snapshot.scope
        if record["context"] != _context(scope) or current["employee_id"] != request.reviewer_id:
            raise HTTPException(403, "Only the current assigned reviewer may access private observations")
        issuer = await col("users").find_one({"employee_id": record["created_by"]}, {"_id": 0})
        if (not issuer or not _technical_admin(issuer) or issuer.get("is_active") is not True
                or issuer.get("org_id") != scope.organization_id or not _assigned(issuer, project)
                or request.reviewer_id in {scope.employee_id, record["created_by"]}
                or record["created_by"] == scope.employee_id
                or request.expires_at <= datetime.now(timezone.utc)
                or not _reviewer_matches(current, request, project, scope)):
            raise HTTPException(403, "Current reviewer/issuer eligibility expired, changed or conflicts with the subject")
        return request, run

    @staticmethod
    def _receipt(record):
        return {"review_id": record["id"], "assignment_id": record["payload"]["assignment_id"],
                "status": "RECORDED_UNVERIFIED", "human_score": None, "combined_score": None,
                "is_finalizable": False,
                "limitations": ["Observation references are attestations, not independent evidence validation",
                                "Approved calibration, engineering measurements and final approval are pending"]}

    async def submit(self, assignment_id, body, actor, required_role=None):
        body = HumanReviewRequest.model_validate(body)
        current = await _current(actor)
        request, run = await self._assignment(assignment_id, current)
        if required_role is not None and request.role != required_role:
            raise HTTPException(403, "This submission route requires an assigned HR reviewer")
        if {o.dimension for o in body.observations} != set(request.dimensions):
            raise HTTPException(422, "Review must cover exactly the assigned dimensions")
        scope = run.evidence.snapshot.scope
        if any(not scope.period_start <= e.observed_at < scope.period_end for o in body.observations for e in o.evidence):
            raise HTTPException(422, "Observation evidence must fall within the exact assessed period")
        digest = canonical_digest(body.model_dump(mode="json"))
        key = "PH-R-" + canonical_digest({"assignment_id": assignment_id})
        existing = await col("ai_runs").find_one({"id": key, "agent_type": "performance_human_review"})
        if existing:
            record = _verify(existing, "performance_human_review")
            if record["payload"]["request_digest"] != digest:
                raise HTTPException(409, "A different immutable review already exists; corrections require the revision workflow")
            return self._receipt(record)
        payload = {"assignment_id": assignment_id, "run_id": run.run_id, "reviewer_id": current["employee_id"],
                   "role": request.role, "request_digest": digest, "observations": body.model_dump(mode="json")["observations"],
                   "no_conflict_attested": True, "evidence_status": "ATTESTED_NOT_INDEPENDENTLY_VERIFIED"}
        try:
            record = await _write("performance_human_review", payload, _context(scope), current["employee_id"], key)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            record = await _read(key, "performance_human_review")
            if record["payload"]["request_digest"] != digest:
                raise HTTPException(409, "A concurrent different review already exists") from None
        return self._receipt(record)

    async def get_review(self, assignment_id, actor):
        current = await _current(actor)
        await self._assignment(assignment_id, current)
        record = (await human_review_history(assignment_id))[-1]
        if record["created_by"] != current["employee_id"]:
            raise HTTPException(403, "Private reviewer observations are unavailable")
        return {**record["payload"], "revision": record["payload"].get("revision", 1), "revision_digest": canonical_digest(record)}

    async def revise(self, assignment_id, body, actor):
        body = HumanReviewRevisionRequest.model_validate(body)
        current = await _current(actor)
        assignment, run = await self._assignment(assignment_id, current)
        scope = run.evidence.snapshot.scope
        if ({o.dimension for o in body.observations} != set(assignment.dimensions)
                or any(not scope.period_start <= e.observed_at < scope.period_end for o in body.observations for e in o.evidence)):
            raise HTTPException(422, "Corrections must retain assigned dimensions and assessed period")
        records = await human_review_history(assignment_id)
        digest = canonical_digest(body.model_dump(mode="json"))
        for record in records:
            if record["payload"].get("correction_request_id") == body.request_id:
                if record["payload"]["correction_digest"] != digest:
                    raise HTTPException(409, "Correction idempotency key was already used")
                return {**self._receipt(record), "revision": record["payload"]["revision"]}
        head = records[-1]
        if canonical_digest(head) != body.expected_digest:
            raise HTTPException(409, "Human observation changed; use its latest digest")
        revision = len(records) + 1
        payload = {**head["payload"], "revision": revision, "predecessor_digest": body.expected_digest,
            "correction_request_id": body.request_id, "correction_digest": digest, "correction_reason": body.reason,
            "observations": [o.model_dump(mode="json") for o in body.observations],
            "evidence_status": "ATTESTED_NOT_INDEPENDENTLY_VERIFIED"}
        key = f"{records[0]['id']}:{revision:06d}"
        try:
            record = await _write("performance_human_review", payload, _context(scope), current["employee_id"], key)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            record = await _read(key, "performance_human_review")
            if record["payload"].get("correction_digest") != digest:
                raise HTTPException(409, "A concurrent different correction created this revision") from None
        return {**self._receipt(record), "revision": revision}

    async def summary(self, run_id, actor):
        current = await _current(actor)
        run, project = await _scoped_run(run_id, current)
        scope = run.evidence.snapshot.scope
        documents = await col("ai_runs").find({"agent_type": "performance_human_assignment",
            "input_data.context": _context(scope), "output_data.payload.run_id": run_id}).limit(6).to_list(6)
        assignments = [_verify(d, "performance_human_assignment") for d in documents]
        own_hr = any(a["payload"]["reviewer_id"] == current["employee_id"] and a["payload"]["role"] == "HR" for a in assignments)
        if not (current["employee_id"] == scope.employee_id or
                current.get("role") in {"LEAD", "PM"} and _assigned(current, project) or own_hr):
            raise HTTPException(403, "Scoped subject, manager or assigned HR access is required")
        if own_hr:
            own = next(a for a in assignments if a["payload"]["reviewer_id"] == current["employee_id"])
            await self._assignment(own["id"], current)
        states, inputs = [], []
        for record in assignments:
            request = HumanReviewerAssignmentRequest.model_validate(record["payload"])
            reviewer = await col("users").find_one({"employee_id": request.reviewer_id}, {"_id": 0})
            eligible = False
            if reviewer:
                try:
                    await self._assignment(record["id"], reviewer)
                    eligible = True
                except HTTPException:
                    pass
            key = "PH-R-" + canonical_digest({"assignment_id": record["id"]})
            document = await col("ai_runs").find_one({"id": key, "agent_type": "performance_human_review"})
            state = "REVOKED" if not eligible else "PENDING"
            if document:
                review = (await human_review_history(record["id"]))[-1]
                if review["context"] != _context(scope) or review["created_by"] != request.reviewer_id:
                    raise HTTPException(409, "Human review scope integrity failed")
                inputs.append(EligibleHumanReview(assignment_id=record["id"], reviewer_id=request.reviewer_id,
                    role=request.role, eligibility="ELIGIBLE" if eligible else "REVOKED",
                    observations=review["payload"]["observations"], validated_dimensions=()))
                state = "RECORDED_UNVERIFIED" if eligible else "REVOKED"
            states.append({"role": request.role, "state": state})
        # No production approved-policy or validated E adapter exists yet. Never
        # infer approval from legacy is_active fields or accept authority from a client.
        result = aggregate_human_reviews(None, tuple(inputs), None)
        return {"run_id": run_id, "reviews": states, "aggregation": result.model_dump(mode="json")}

    async def propose_policy(self, body, actor):
        body = HumanPolicyDraftRequest.model_validate(body)
        current = await _current(actor)
        project = await col("projects").find_one({"id": body.project_id, "org_id": current["org_id"]}, {"_id": 0})
        if not _technical_admin(current) or not project or not _assigned(current, project):
            raise HTTPException(403, "A current scoped technical administrator may propose a policy draft")
        record = await _write("performance_human_policy_draft", body.model_dump(mode="json"),
            {"organization_id": current["org_id"], "project_id": body.project_id}, current["employee_id"])
        return {"draft_id": record["id"], "status": "DRAFT", "is_active": False, "is_finalizable": False}
