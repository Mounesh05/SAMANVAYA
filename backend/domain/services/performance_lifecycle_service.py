"""Append-only scoring workflow and governance in the existing signed artifact store.

Each state change and its audit metadata are one insert. Natural primary keys
serialize competing revisions without an unsafe read/overwrite cycle. Numerical
eligibility depends on a trusted calibrated measurement adapter, not a state flag.
"""

from datetime import datetime, timezone

from fastapi import HTTPException

from core.database import col
from core.permissions import Permission, get_user_permissions
from domain.models.performance_evidence import canonical_digest
from domain.models.performance_human import HumanPolicyDraftRequest
from domain.models.performance_lifecycle import (
    ApproverAssignmentRequest, AssessmentActionRequest, AssessmentAppealRequest,
    AssessmentCreateRequest, MeasurementAttestation, PolicyReviewRequest, ScoringRelease,
)
from domain.services.performance_artifact_store import _context, _read, _verify, _write
from domain.services.performance_human_service import _assigned, _current, _scoped_run, _technical_admin
from intelligence.performance_human import aggregate_human_reviews


TRANSITIONS = {
    "COLLECT": ({"DRAFT"}, "EVIDENCE_COLLECTING"),
    "VALIDATE": ({"EVIDENCE_COLLECTING"}, "EVIDENCE_VALIDATED"),
    "ELIGIBLE": ({"EVIDENCE_VALIDATED"}, "SCORING_ELIGIBLE"),
    "CALCULATE": ({"SCORING_ELIGIBLE"}, "PROVISIONAL"),
    "REVIEW": ({"PROVISIONAL"}, "UNDER_REVIEW"),
    "APPROVE": ({"UNDER_REVIEW"}, "APPROVED"),
    "REJECT": ({"UNDER_REVIEW", "DISPUTED"}, "REJECTED"),
    "CANCEL": ({"DRAFT", "EVIDENCE_COLLECTING", "EVIDENCE_VALIDATED", "SCORING_ELIGIBLE", "PROVISIONAL", "UNDER_REVIEW"}, "CANCELLED"),
    "CORRECT": ({"DISPUTED", "REJECTED", "APPROVED", "INSUFFICIENT_EVIDENCE"}, "DRAFT"),
}


def _key(assessment_id, revision):
    return f"{assessment_id}:{revision:06d}"


def _receipt(record):
    payload = record["payload"]
    calculation = (payload.get("measurement") or {}).get("snapshot", {}).get("calculation") or {}
    score = (calculation.get("combined_score") or {}).get("value")
    return {"assessment_id": payload["assessment_id"], "event_id": record["id"], "revision": payload["revision"],
            "state": payload["state"], "digest": canonical_digest(record),
            "provisional_score": score if payload["state"] in {"PROVISIONAL", "UNDER_REVIEW"} else None,
            "approved_score": score if payload["state"] == "APPROVED" else None}


class AssessmentLifecycleService:
    async def _history(self, assessment_id):
        documents = await col("ai_runs").find({"agent_type": "performance_assessment_event",
            "output_data.payload.assessment_id": assessment_id}).limit(501).to_list(501)
        if not documents:
            raise HTTPException(404, "Assessment not found")
        if len(documents) > 500:
            raise HTTPException(409, "Assessment history requires archival review before further use")
        records = sorted((_verify(d, "performance_assessment_event") for d in documents), key=lambda r: r["payload"]["revision"])
        for index, record in enumerate(records):
            payload = record["payload"]
            previous = canonical_digest(records[index - 1]) if index else None
            if (record["id"] != _key(assessment_id, index + 1) or payload["revision"] != index + 1
                    or payload["predecessor_digest"] != previous or record["context"] != records[0]["context"]):
                raise HTTPException(409, "Assessment revision chain integrity failed")
        return records

    async def _access(self, records, actor, historical=False):
        current = await _current(actor)
        run, project = await _scoped_run(records[-1]["payload"]["run_id"], current, historical=historical)
        scope = run.evidence.snapshot.scope
        if records[0]["context"] != _context(scope):
            raise HTTPException(403, "Assessment scope mismatch")
        own = current["employee_id"] == scope.employee_id
        if (not own and current.get("role") == "HR" and Permission.VIEW_PERFORMANCE_OUTCOMES not in
                get_user_permissions("HR", current.get("is_admin", False), current.get("designation"))):
            raise HTTPException(403, "Current HR outcome scope is required")
        manager = current.get("role") in {"LEAD", "PM"} and _assigned(current, project)
        if not (own or manager or current.get("role") in {"CEO", "HR"}):
            raise HTTPException(403, "Assessment access is outside current scope")
        return current, run, project

    @staticmethod
    def _manage(current, project):
        if not _technical_admin(current) or not _assigned(current, project):
            raise HTTPException(403, "A current scoped technical administrator is required")

    async def create(self, body, actor):
        body = AssessmentCreateRequest.model_validate(body)
        current = await _current(actor)
        run, project = await _scoped_run(body.run_id, current)
        self._manage(current, project)
        scope = run.evidence.snapshot.scope
        if current["employee_id"] == scope.employee_id:
            raise HTTPException(403, "The subject cannot initiate their own managed assessment")
        identity = {**_context(scope), "period_start": scope.period_start.isoformat(), "period_end": scope.period_end.isoformat()}
        assessment_id = "PA-" + canonical_digest(identity)
        payload = {"assessment_id": assessment_id, "revision": 1, "predecessor_digest": None, "state": "DRAFT",
                   "run_id": run.run_id, "frozen_evidence": run.evidence.model_dump(mode="json"), "measurement": None,
                   "action": "CREATE", "request_id": "create", "request_digest": canonical_digest(body.model_dump(mode="json")),
                   "reason": body.reason}
        try:
            record = await _write("performance_assessment_event", payload, _context(scope), current["employee_id"], _key(assessment_id, 1))
        except HTTPException as error:
            if error.status_code != 409:
                raise
            record = await _read(_key(assessment_id, 1), "performance_assessment_event")
            if record["payload"]["run_id"] != run.run_id or record["context"] != _context(scope):
                raise HTTPException(409, "This scoped period already has an assessment; use a reviewed correction") from None
        return _receipt(record)

    async def _append(self, records, body, current, state, **changes):
        digest = canonical_digest(body.model_dump(mode="json"))
        for record in records:
            old = record["payload"]
            if old["request_id"] == body.request_id and record["created_by"] == current["employee_id"]:
                if old["request_digest"] != digest:
                    raise HTTPException(409, "Idempotency key already used for a different request")
                return _receipt(record)
        head = records[-1]
        if canonical_digest(head) != body.expected_digest:
            raise HTTPException(409, "Assessment changed; use the current revision digest")
        payload = {**head["payload"], **changes, "revision": head["payload"]["revision"] + 1,
                   "predecessor_digest": body.expected_digest, "state": state, "request_id": body.request_id,
                   "request_digest": digest, "reason": body.reason}
        try:
            record = await _write("performance_assessment_event", payload, head["context"], current["employee_id"],
                                  _key(payload["assessment_id"], payload["revision"]))
        except HTTPException as error:
            if error.status_code != 409:
                raise
            record = await _read(_key(payload["assessment_id"], payload["revision"]), "performance_assessment_event")
            if record["created_by"] != current["employee_id"] or record["payload"]["request_digest"] != digest:
                raise HTTPException(409, "A concurrent different action created this revision") from None
        return _receipt(record)

    async def _measurement(self, measurement_id, run, historical=False):
        if not measurement_id:
            raise HTTPException(409, "A calibrated, validated deterministic measurement artifact is required")
        record = await _read(measurement_id, "performance_measurement")
        measurement = MeasurementAttestation.model_validate(record["payload"])
        scope = run.evidence.snapshot.scope
        if record["created_by"] != "scoring-measurement-service" or record["context"] != _context(scope) or measurement.run_id != run.run_id:
            raise HTTPException(409, "Measurement authority and exact assessment scope are not established")
        release_record = await _read(measurement.release_id, "performance_scoring_release")
        release = ScoringRelease.model_validate(release_record["payload"])
        draft_record = await _read(release.policy_draft_id, "performance_human_policy_draft")
        draft = HumanPolicyDraftRequest.model_validate(draft_record["payload"])
        review_record = await _read(release.policy_review_id, "performance_policy_review")
        snapshot = measurement.snapshot
        identity = snapshot.identity
        if (release_record["created_by"] != "scoring-calibration-service"
                or release_record["context"] != {"organization_id": scope.organization_id, "project_id": scope.project_id}
                or draft_record["context"] != release_record["context"] or review_record["context"] != release_record["context"]
                or canonical_digest(draft_record) != release.policy_draft_digest
                or canonical_digest(review_record) != release.policy_review_digest
                or review_record["payload"]["draft_id"] != draft_record["id"]
                or review_record["created_by"] == draft_record["created_by"]
                or review_record["payload"]["draft_digest"] != release.policy_draft_digest
                or release.effective_from > scope.period_start or scope.period_end > release.effective_until
                or release.effective_from < datetime.fromisoformat(review_record["payload"]["effective_from"])
                or identity.assessment_id != "PA-" + canonical_digest({**_context(scope),
                    "period_start": scope.period_start.isoformat(), "period_end": scope.period_end.isoformat()})
                or identity.organization_id != scope.organization_id or identity.employee_id != scope.employee_id
                or identity.project_ids != (scope.project_id,) or identity.period_start != scope.period_start or identity.period_end != scope.period_end
                or identity.employee_role_at_period != release.subject_role or draft.policy.subject_role != release.subject_role
                or snapshot.rubric != release.rubric or snapshot.methodology != release.measurement_method
                or not snapshot.policy or snapshot.policy.id != draft.policy.policy_id or snapshot.policy.version != draft.policy.version
                or not snapshot.evidence or snapshot.evidence.id != run.run_id or snapshot.evidence.digest != run.evidence.digest
                or snapshot.coverage.engineering_percent is None or snapshot.coverage.engineering_percent < release.minimum_engineering_coverage
                or snapshot.coverage.human_completeness != "COMPLETE" or snapshot.coverage.policy != snapshot.policy or not snapshot.calculation):
            raise HTTPException(409, "Frozen policy, release, coverage or measurement provenance is incomplete or inapplicable")
        policy = draft.policy.model_copy(update={"status": "APPROVED"})
        replay = aggregate_human_reviews(policy, measurement.human_reviews, snapshot.calculation.engineering_score)
        if replay.status != "COMPLETE" or replay.calculation != snapshot.calculation:
            raise HTTPException(409, "Frozen measurement cannot be replayed with the approved policy")
        if len(measurement.human_review_ids) != len(measurement.human_reviews):
            raise HTTPException(409, "Every human measurement must reference its frozen observation")
        for reference, resolved in zip(measurement.human_review_ids, measurement.human_reviews):
            observation = await _read(reference, "performance_human_review")
            if (observation["context"] != _context(scope) or observation["created_by"] != resolved.reviewer_id
                    or observation["payload"]["run_id"] != run.run_id
                    or observation["payload"]["assignment_id"] != resolved.assignment_id
                    or observation["payload"]["observations"] != [o.model_dump(mode="json") for o in resolved.observations]):
                raise HTTPException(409, "Human measurement does not match its signed observation")
            from domain.services.performance_human_service import HumanFeedbackService, human_review_history
            if not historical and (await human_review_history(resolved.assignment_id))[-1]["id"] != reference:
                raise HTTPException(409, "Human feedback was corrected after measurement; create a calculation revision")
            if not historical:
                reviewer = await _current({"employee_id": resolved.reviewer_id})
                await HumanFeedbackService()._assignment(resolved.assignment_id, reviewer)
        return measurement

    async def _approver(self, assignment_id, records, current, run, project):
        if not assignment_id:
            raise HTTPException(403, "An independent qualified approver assignment is required")
        record = await _read(assignment_id, "performance_assessment_approver")
        request = ApproverAssignmentRequest.model_validate(record["payload"]["request"])
        issuer = await _current({"employee_id": record["created_by"]})
        self._manage(issuer, project)
        scope = run.evidence.snapshot.scope
        contributors = {scope.employee_id, run.created_by, records[0]["created_by"], record["created_by"]}
        measurement = records[-1]["payload"].get("measurement")
        if measurement:
            contributors.update(r["reviewer_id"] for r in measurement["human_reviews"])
        if (record["context"] != _context(scope) or issuer["org_id"] != scope.organization_id
                or record["payload"]["snapshot_digest"] != run.evidence.digest
                or record["payload"]["assessment_id"] != records[0]["payload"]["assessment_id"]
                or request.reviewer_id != current["employee_id"] or current["employee_id"] in contributors
                or request.expires_at <= datetime.now(timezone.utc) or current.get("role") not in {"LEAD", "PM"}
                or not _assigned(current, project)):
            raise HTTPException(403, "Approver is conflicted, expired or outside the assigned scope")

    async def transition(self, assessment_id, body, actor):
        body = AssessmentActionRequest.model_validate(body)
        records = await self._history(assessment_id)
        current, run, project = await self._access(records, actor)
        if current["employee_id"] == run.evidence.snapshot.scope.employee_id:
            raise HTTPException(403, "The subject may appeal but cannot manage or approve their own assessment")
        if body.action in {"REVIEW", "APPROVE", "REJECT"}:
            await self._approver(body.assignment_id, records, current, run, project)
        else:
            self._manage(current, project)
        # Recover exact retries before applying a transition to the newer head.
        if any(r["payload"]["request_id"] == body.request_id and r["created_by"] == current["employee_id"] for r in records):
            return await self._append(records, body, current, records[-1]["payload"]["state"])
        allowed, state = TRANSITIONS[body.action]
        if records[-1]["payload"]["state"] not in allowed:
            raise HTTPException(409, "Invalid assessment state transition")
        changes = {"action": body.action}
        if body.action == "CORRECT":
            if not body.run_id:
                raise HTTPException(422, "A correction requires an exact replacement snapshot")
            replacement, _ = await _scoped_run(body.run_id, current)
            if replacement.evidence.snapshot.scope != run.evidence.snapshot.scope:
                raise HTTPException(409, "Restatement must retain the exact subject/project/period scope")
            changes.update(run_id=replacement.run_id, frozen_evidence=replacement.evidence.model_dump(mode="json"), measurement=None, measurement_id=None)
        elif body.action in {"VALIDATE", "ELIGIBLE", "CALCULATE", "APPROVE"}:
            existing_id = records[-1]["payload"].get("measurement_id")
            if existing_id and body.measurement_id and body.measurement_id != existing_id:
                raise HTTPException(409, "Frozen measurements cannot change within a review; create a correction revision")
            measurement_id = body.measurement_id or existing_id
            measurement = await self._measurement(measurement_id, run)
            changes.update(measurement=measurement.model_dump(mode="json"), measurement_id=measurement_id)
        return await self._append(records, body, current, state, **changes)

    async def appeal(self, assessment_id, body, actor):
        body = AssessmentAppealRequest.model_validate(body)
        records = await self._history(assessment_id)
        current, run, _ = await self._access(records, actor, historical=True)
        if current["employee_id"] != run.evidence.snapshot.scope.employee_id:
            raise HTTPException(403, "Only the scoped subject may file this appeal; delegated authority is not inferred")
        return await self._append(records, body, current, "DISPUTED", action="APPEAL",
                                  evidence_references=list(body.evidence_references))

    async def get(self, assessment_id, actor):
        records = await self._history(assessment_id)
        current, run, _ = await self._access(records, actor, historical=True)
        head = _receipt(records[-1])
        if current.get("role") in {"CEO", "HR"} and current["employee_id"] != run.evidence.snapshot.scope.employee_id:
            head["provisional_score"] = None
            records = [r for r in records if r["payload"]["state"] == "APPROVED"]
            if not records:
                raise HTTPException(404, "No approved summary is available")
        await _write("performance_access_audit", {"action": "ASSESSMENT_HISTORY_READ", "assessment_id": assessment_id,
            "head_digest": head["digest"]}, {"organization_id": current["org_id"]}, current["employee_id"])
        return {"current": head, "history": [_receipt(r) for r in records],
                "comparability": "Compare only compatible frozen rubric, policy, coverage and period scopes"}

    async def replay(self, assessment_id, revision, actor):
        records = await self._history(assessment_id)
        current, _, _ = await self._access(records, actor, historical=True)
        if type(revision) is not int or not 1 <= revision <= len(records):
            raise HTTPException(404, "Assessment revision not found")
        record = records[revision - 1]
        if current.get("role") in {"CEO", "HR"} and record["payload"]["state"] != "APPROVED":
            raise HTTPException(404, "No approved calculation is available")
        measurement_id = record["payload"].get("measurement_id")
        if not measurement_id:
            raise HTTPException(409, "This revision has no calibrated calculation to replay")
        run, _ = await _scoped_run(record["payload"]["run_id"], current, historical=True)
        measurement = await self._measurement(measurement_id, run, historical=True)
        if measurement.model_dump(mode="json") != record["payload"]["measurement"]:
            raise HTTPException(409, "Frozen revision measurement digest differs from its signed source")
        await _write("performance_access_audit", {"action": "ASSESSMENT_REPLAY", "assessment_id": assessment_id,
            "revision": revision, "digest": canonical_digest(record)}, {"organization_id": current["org_id"]}, current["employee_id"])
        return {"status": "REPRODUCED", "revision": revision, "snapshot_digest": canonical_digest(measurement.snapshot.model_dump(mode="json")),
                "calculation": measurement.snapshot.calculation.model_dump(mode="json"),
                "limitations": ["Replays frozen validated inputs and policy; does not revalidate later source or account changes"]}

    async def assign_approver(self, assessment_id, body, actor):
        body = ApproverAssignmentRequest.model_validate(body)
        records = await self._history(assessment_id)
        current, run, project = await self._access(records, actor)
        self._manage(current, project)
        reviewer = await _current({"employee_id": body.reviewer_id})
        scope = run.evidence.snapshot.scope
        if (reviewer.get("role") not in {"LEAD", "PM"} or reviewer["org_id"] != scope.organization_id
                or not _assigned(reviewer, project) or body.reviewer_id in {scope.employee_id, current["employee_id"], records[0]["created_by"]}
                or current["employee_id"] == scope.employee_id or body.expires_at <= datetime.now(timezone.utc)
                or not set(body.qualification_source_ids) <= {r.source_id for r in run.evidence.snapshot.records}):
            raise HTTPException(403, "Independent qualified approver scope and period-source attestation are required")
        key = "PAQ-" + canonical_digest({"assessment_id": assessment_id, "reviewer_id": body.reviewer_id, "snapshot_digest": run.evidence.digest})
        payload = {"assessment_id": assessment_id, "snapshot_digest": run.evidence.digest, "request": body.model_dump(mode="json")}
        try:
            await _write("performance_assessment_approver", payload, _context(scope), current["employee_id"], key)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            old = await _read(key, "performance_assessment_approver")
            if old["payload"] != payload or old["created_by"] != current["employee_id"]:
                raise
        return {"assignment_id": key, "reviewer_id": body.reviewer_id}

    async def review_policy(self, draft_id, body, actor):
        body = PolicyReviewRequest.model_validate(body)
        current = await _current(actor)
        draft = await _read(draft_id, "performance_human_policy_draft")
        context = draft["context"]
        project = await col("projects").find_one({"id": context["project_id"], "org_id": current["org_id"]}, {"_id": 0})
        if (not project or current["org_id"] != context["organization_id"] or current.get("role") not in {"LEAD", "PM"}
                or not _assigned(current, project) or current["employee_id"] == draft["created_by"]):
            raise HTTPException(403, "Independent scoped technical policy review is required")
        if body.effective_from < datetime.now(timezone.utc):
            raise HTTPException(409, "Policy review cannot retroactively activate past periods; restatement requires separate review")
        payload = {**body.model_dump(mode="json"), "draft_id": draft_id, "draft_digest": canonical_digest(draft),
                   "status": "REVIEWED_INACTIVE", "is_active": False}
        key = "PPR-" + canonical_digest({"draft_id": draft_id})
        try:
            await _write("performance_policy_review", payload, context, current["employee_id"], key)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            previous = await _read(key, "performance_policy_review")
            if previous["payload"] != payload or previous["created_by"] != current["employee_id"]:
                raise HTTPException(409, "A different policy review already exists") from None
        return {"review_id": key, "status": "REVIEWED_INACTIVE", "is_active": False,
                "missing_requirements": ["Trusted empirical calibration/release attestation and applicable measurement adapter"]}

    async def policy_detail(self, draft_id, actor):
        current = await _current(actor)
        draft = await _read(draft_id, "performance_human_policy_draft")
        project = await col("projects").find_one({"id": draft["context"]["project_id"], "org_id": current["org_id"]}, {"_id": 0})
        if (draft["context"]["organization_id"] != current["org_id"] or not project
                or current.get("role") not in {"LEAD", "PM"} or not _assigned(current, project)):
            raise HTTPException(403, "Current scoped technical policy inspection is required")
        await _write("performance_access_audit", {"action": "POLICY_DRAFT_READ", "draft_id": draft_id},
                     {"organization_id": current["org_id"]}, current["employee_id"])
        return {"draft_id": draft_id, "digest": canonical_digest(draft), "proposal": draft["payload"], "is_active": False}
