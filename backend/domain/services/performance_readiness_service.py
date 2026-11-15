"""Calibration evidence intake and truthful release readiness; no release issuer.

Software tests and model narratives cannot approve empirical role calibration.
This service intentionally supplies no runtime path for activating a draft.
"""

from fastapi import HTTPException
from core.database import col
from domain.models.performance_readiness import CalibrationPacketRequest
from domain.models.performance_evidence import canonical_digest
from domain.services.performance_artifact_store import _read, _write
from domain.services.performance_human_service import _assigned, _current, _technical_admin
from domain.services.performance_claim_service import PerformanceClaimService
from intelligence.performance_registry import get_rubric_profile

ROLE_ORDER = ("DEVELOPER", "QA", "DEVOPS", "LEAD", "PM")


class PerformanceReadinessService:
    async def readiness(self, actor):
        current = await _current(actor)
        if current.get("role") not in {*ROLE_ORDER, "HR", "CEO"}:
            raise HTTPException(403, "Current scoring context is unavailable")
        return {"production_scoring_enabled": False, "status": "CALIBRATION_REQUIRED",
            "roles": [{"role": role, "status": get_rubric_profile(role).calibration_status,
                       "is_finalizable": False, "engineering_score": None, "human_score": None, "approved_score": None}
                      for role in ROLE_ORDER],
            "unresolved_decisions": ["Approved role dimensions, measurement rules and anchored weights",
                "Authorized representative work and non-gaming/coverage validation",
                "Approved reviewer relevance, scale anchors and completeness policy",
                "Independent empirical calibration and release sign-off",
                "Validated deterministic measurement and workplace-source adapters"],
            "ceo_routine_contribution": 0, "hr_technical_rescoring_allowed": False,
            "limitations": ["Calibration packets are unverified proposals, not approval",
                            "Passing software tests does not establish an employee rubric"]}

    async def _project(self, project_id, current, write=False):
        project = await col("projects").find_one({"id": project_id, "org_id": current["org_id"]}, {"_id": 0})
        if (not project or current.get("role") not in {"LEAD", "PM"} or not _assigned(current, project)
                or write and not _technical_admin(current)):
            raise HTTPException(403, "Current scoped technical calibration access is required")
        return {"organization_id": current["org_id"], "project_id": project_id}

    async def propose(self, body, actor):
        body = CalibrationPacketRequest.model_validate(body)
        current = await _current(actor)
        context = await self._project(body.project_id, current, write=True)
        samples = []
        for sample in body.samples:
            run, _, _ = await PerformanceClaimService()._authorized_run(sample.run_id, actor)
            scope = run.evidence.snapshot.scope
            sources = {r.source_id: r for r in run.evidence.snapshot.records}
            if (scope.project_id != body.project_id or not set(sample.source_ids) <= set(sources)
                    or scope.role_at_period is not None and scope.role_at_period != body.subject_role):
                raise HTTPException(422, "Calibration references must match the exact project, period-role and snapshot sources")
            samples.append({**sample.model_dump(mode="json"), "snapshot_digest": run.evidence.digest,
                "role_at_period": scope.role_at_period, "source_digests": {key: sources[key].content_digest for key in sample.source_ids}})
        payload = {**body.model_dump(mode="json"), "samples": samples, "status": "PROPOSED_UNVERIFIED",
            "representativeness": "NOT_ESTABLISHED", "is_finalizable": False,
            "missing_requirements": ["Independent role/attribution confirmation", "Empirical scoring and sensitivity validation",
                                     "Approved policy, coverage and release evidence"]}
        key = "PCAL-" + canonical_digest({"context": context, "payload": payload, "proposer": current["employee_id"]})
        try:
            await _write("performance_calibration_draft", payload, context, current["employee_id"], key)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            existing = await _read(key, "performance_calibration_draft")
            if existing["context"] != context or existing["payload"] != payload:
                raise
        return {"draft_id": key, "status": "PROPOSED_UNVERIFIED", "is_finalizable": False}

    async def get(self, draft_id, actor):
        current = await _current(actor)
        record = await _read(draft_id, "performance_calibration_draft")
        context = await self._project(record["context"]["project_id"], current)
        if context != record["context"]:
            raise HTTPException(403, "Calibration scope is unavailable")
        # Recheck source access; this endpoint does not grant access to raw cases.
        for sample in record["payload"]["samples"]:
            await PerformanceClaimService()._authorized_run(sample["run_id"], actor)
        return record["payload"]
