"""Scoring-specific read migration: scoped historical values, never fake approval.

Legacy org provenance may be absent. Reads require both the current subject and
the recorded project to resolve within the current organization; unresolved rows
are withheld rather than guessed/backfilled. No historical score is recalculated.
"""

import copy

from fastapi import HTTPException
from pydantic import Field

from core.database import col
from core.permissions import Permission, get_user_permissions
from domain.models.developer_performance import DeveloperPerformance
from domain.models.performance_claims import Text
from domain.models.performance_scoring import FrozenContract, legacy_metadata_for_record
from domain.models.performance_evidence import canonical_digest
from domain.schemas.hr_views import PerformanceOutcomeHR
from domain.services.performance_artifact_store import _read, _write
from domain.services.performance_human_service import _assigned, _current
from repositories.performance_repository import PerformanceRepository

COMPARISON_LIMITATIONS = ["Legacy methodology, evidence coverage and period normalization are not verified; numeric changes are not a verified employee trend"]


class ExportRequest(FrozenContract):
    purpose: Text


class LegacyAppealRequest(FrozenContract):
    reason: Text
    evidence: list[Text] = Field(default_factory=list, max_length=20)


def _summary(record):
    return PerformanceOutcomeHR(evaluation_id=str(record.get("_id", record.get("id", ""))),
        employee_id=record["developer_id"], employee_name=record.get("developer_name", "Unknown"),
        period=record.get("period_label", ""), period_start=record.get("period_start"), period_end=record.get("period_end"),
        overall_score=record.get("final_score"), grade=record.get("grade"),
        ai_score_summary=(record.get("ai_evaluation") or {}).get("score"),
        human_score=(record.get("role_evaluation") or {}).get("average_score"),
        scoring=legacy_metadata_for_record(record))


def _technical(record):
    record = copy.deepcopy(record)
    record["hr_assessment"] = None
    if isinstance(record.get("role_evaluation"), dict):
        record["role_evaluation"]["hr"] = None
    if isinstance(record.get("role_feedback"), dict):
        record["role_feedback"].pop("hr", None)
    return DeveloperPerformance(**record)


class PerformanceAccessService:
    async def policy_history(self, actor, limit=20):
        current = await _current(actor)
        if not 1 <= limit <= 100:
            raise HTTPException(422, "Policy history limit must be between 1 and 100")
        rows = await col("evaluation_policies").find({"org_id": current["org_id"]}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        keys = {"policy_id", "version", "role_weights", "role_dimensions", "ai_weight", "human_weight", "created_at", "updated_at"}
        await self._audit(current, "LEGACY_POLICY_HISTORY_READ", current["org_id"])
        return [{**{k: v for k, v in row.items() if k in keys}, "status": "LEGACY_UNVERIFIABLE", "is_active": False,
                 "legacy_is_active": row.get("is_active"), "canonical_approval": None} for row in rows]

    async def _subject(self, employee_id, actor):
        current = await _current(actor)
        subject = await col("users").find_one({"employee_id": employee_id, "org_id": current["org_id"]}, {"_id": 0})
        if not subject:
            raise HTTPException(403, "Historical assessment scope is unavailable or unauthorized")
        if current["employee_id"] != employee_id and current.get("role") not in {"LEAD", "PM", "HR", "CEO"}:
            raise HTTPException(403, "Current role cannot inspect this employee assessment")
        if current.get("role") == "HR" and Permission.VIEW_PERFORMANCE_OUTCOMES not in get_user_permissions(
                "HR", current.get("is_admin", False), current.get("designation")):
            raise HTTPException(403, "Current HR outcome access is not authorized")
        return current, subject

    async def _row(self, record, current):
        project = await col("projects").find_one({"id": record.get("project_id"), "org_id": current["org_id"]}, {"_id": 0})
        if not project or record.get("org_id", current["org_id"]) != current["org_id"]:
            raise HTTPException(403, "Historical project/organization provenance is unavailable or unauthorized")
        if (current["employee_id"] != record["developer_id"] and current.get("role") not in {"HR", "CEO"}
                and not _assigned(current, project)):
            raise HTTPException(403, "Historical project is outside current management scope")
        return project

    async def _records(self, employee_id, actor, limit=10, period_label=None):
        current, _ = await self._subject(employee_id, actor)
        query = {"developer_id": employee_id}
        if period_label:
            query["period_label"] = period_label
        records = await col("developer_performances").find(query).sort("period_start", -1).limit(limit).to_list(limit)
        for record in records:
            await self._row(record, current)
        return current, records

    async def _audit(self, current, action, resource, **metadata):
        await _write("performance_access_audit", {"action": action, "resource": resource, **metadata},
                     {"organization_id": current["org_id"]}, current["employee_id"])

    async def detail(self, employee_id, actor, period_label=None):
        current, records = await self._records(employee_id, actor, 1, period_label)
        if not records:
            raise HTTPException(404, "No historical assessment is available")
        await self._audit(current, "LEGACY_READ", str(records[0]["_id"]))
        return _summary(records[0]) if current.get("role") in {"CEO", "HR"} else _technical(records[0])

    async def trend(self, employee_id, actor, limit=10):
        if not 1 <= limit <= 100:
            raise HTTPException(422, "History limit must be between 1 and 100")
        current, records = await self._records(employee_id, actor, limit)
        await self._audit(current, "LEGACY_HISTORY_READ", employee_id)
        history = [{"period_label": r.get("period_label"), "period_start": r.get("period_start"),
                    "final_score": r.get("final_score"), "grade": r.get("grade"),
                    "scoring": legacy_metadata_for_record(r).model_dump(mode="json")} for r in records]
        return {"developer_id": employee_id, "current_score": records[0].get("final_score") if records else None,
                "trend": "not_comparable", "history": history, "comparison_limitations": COMPARISON_LIMITATIONS}

    async def dashboard(self, employee_id, actor, periods=6):
        current, records = await self._records(employee_id, actor, 1)
        trend = await self.trend(employee_id, actor, periods)
        summary = _summary(records[0]).model_dump(mode="json") if records else None
        if summary:
            summary.update(developer_id=employee_id, developer_name=summary["employee_name"],
                contribution_credit=None, ai_evaluation={"dimension_scores": {}, "strengths": [], "weaknesses": [],
                    "overall_score": summary["ai_score_summary"], "confidence_score": None, "evaluation_summary": "Legacy unverified methodology",
                    "recommendations": []}, evaluation_count=len(trend["history"]), role_evaluations=[])
        return {"developer_id": employee_id, "current_performance": summary,
                "historical_trend": [{"period": r["period_label"], "score": r["final_score"], "grade": r["grade"],
                    "scoring": r["scoring"]} for r in trend["history"]], "peer_comparison": None,
                "hr_assessment": None, "is_hr_view": current.get("role") in {"HR", "CEO"},
                "comparison_limitations": COMPARISON_LIMITATIONS}

    async def team(self, project_id, period_label, actor):
        current = await _current(actor)
        if current.get("role") not in {"LEAD", "PM", "HR", "CEO"}:
            raise HTTPException(403, "Current role cannot read team performance summaries")
        projects = await col("projects").find({"org_id": current["org_id"]}).limit(1001).to_list(1001)
        if len(projects) > 1000:
            raise HTTPException(409, "Use a narrower project query")
        allowed = [p["id"] for p in projects if current.get("role") in {"CEO", "HR"} or _assigned(current, p)]
        if project_id != "all" and project_id not in allowed:
            raise HTTPException(403, "Team project is outside current organization/management scope")
        query = {"project_id": {"$in": allowed if project_id == "all" else [project_id]}}
        if period_label != "current":
            query["period_label"] = period_label
        rows = await col("developer_performances").find(query).sort("period_start", -1).limit(1001).to_list(1001)
        if len(rows) > 1000:
            raise HTTPException(409, "Team history requires a narrower period/project query")
        result, seen = [], set()
        for row in rows:
            if period_label == "current" and row["developer_id"] in seen:
                continue
            subject = await col("users").find_one({"employee_id": row["developer_id"], "org_id": current["org_id"]})
            if not subject or row.get("org_id", current["org_id"]) != current["org_id"]:
                continue
            seen.add(row["developer_id"])
            created = row.get("created_at")
            result.append({"developer_id": row["developer_id"], "developer_name": row.get("developer_name", "Unknown"),
                "overall_score": row.get("final_score"), "grade": row.get("grade"), "trend": "not_comparable",
                "last_evaluated": created.isoformat() if hasattr(created, "isoformat") else created,
                "scoring": legacy_metadata_for_record(row).model_dump(mode="json"), "comparison_limitations": COMPARISON_LIMITATIONS})
        await self._audit(current, "LEGACY_TEAM_READ", project_id, period=period_label)
        return sorted(result, key=lambda r: r["developer_id"])  # No unverifiable numeric ranking.

    async def hr_case(self, performance_id, actor):
        current = await _current(actor)
        if current.get("role") != "HR" or Permission.VIEW_HR_PERFORMANCE_ASSESSMENT not in get_user_permissions(
                "HR", current.get("is_admin", False), current.get("designation")):
            raise HTTPException(403, "Case-specific current HR permission is required")
        record = await PerformanceRepository().get_by_id(performance_id)
        employee_id = record["developer_id"] if record else performance_id
        await self._subject(employee_id, actor)
        if record:
            await self._row(record, current)
        assessment = await col("hr_assessments").find_one({"developer_id": employee_id,
            "evaluator_id": current["employee_id"], "performance_id": {"$in": [performance_id, str(record["_id"]) if record else performance_id]}}, {"_id": 0})
        if assessment and assessment.get("org_id", current["org_id"]) != current["org_id"]:
            raise HTTPException(403, "HR case organization mismatch")
        if assessment and not record and assessment.get("org_id") != current["org_id"]:
            raise HTTPException(403, "Unscoped historical HR case requires explicit organization provenance")
        await self._audit(current, "HR_OWN_CASE_READ", performance_id)
        return assessment

    async def completeness(self, performance_id, actor):
        record = await PerformanceRepository().get_by_id(performance_id)
        employee_id = record["developer_id"] if record else performance_id
        current, _ = await self._subject(employee_id, actor)
        if record:
            await self._row(record, current)
        from domain.services.hr_performance_service import HRPerformanceService
        await self._audit(current, "LEGACY_COMPLETENESS_READ", performance_id)
        return await HRPerformanceService().check_human_evaluation_completeness(performance_id)

    async def appeal_legacy(self, performance_id, body, actor):
        body = LegacyAppealRequest.model_validate(body)
        record = await PerformanceRepository().get_by_id(performance_id)
        if not record:
            raise HTTPException(404, "Historical assessment not found")
        current, _ = await self._subject(record["developer_id"], actor)
        await self._row(record, current)
        if current["employee_id"] != record["developer_id"]:
            raise HTTPException(403, "Only the scoped subject may file an appeal; admin title is not delegated authority")
        key = "PLA-" + canonical_digest({"org_id": current["org_id"], "performance_id": str(record["_id"]),
                                        "actor": current["employee_id"], "body": body.model_dump(mode="json")})
        payload = {"performance_id": str(record["_id"]), "historical_digest": canonical_digest(_summary(record).model_dump(mode="json")),
                   "request": body.model_dump(mode="json"), "status": "DISPUTED"}
        try:
            await _write("performance_legacy_appeal", payload, {"organization_id": current["org_id"],
                "project_id": record["project_id"], "employee_id": record["developer_id"]}, current["employee_id"], key)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            old = await _read(key, "performance_legacy_appeal")
            if old["payload"] != payload:
                raise
        return {"performance_id": performance_id, "credit_status": "appealed", "appeal_id": key,
                "status": "DISPUTED", "historical_score_unchanged": True}

    async def export(self, employee_id, body, actor):
        body = ExportRequest.model_validate(body)
        current, records = await self._records(employee_id, actor, 100)
        data = [_summary(r).model_dump(mode="json") for r in records]
        digest = canonical_digest(data)
        await self._audit(current, "REDACTED_EXPORT", employee_id, purpose=body.purpose, export_digest=digest, row_count=len(data))
        return {"employee_id": employee_id, "purpose": body.purpose, "digest": digest, "records": data,
                "comparison_limitations": COMPARISON_LIMITATIONS}

    async def shadow(self, employee_id, actor):
        current, records = await self._records(employee_id, actor, 1)
        if current.get("role") not in {"LEAD", "PM"}:
            raise HTTPException(403, "Scoped engineering management is required for a shadow discrepancy inspection")
        if not records:
            raise HTTPException(404, "No historical assessment is available")
        record = records[0]
        await self._audit(current, "SHADOW_INSPECTION", str(record["_id"]))
        return {"status": "SHADOW_INCOMPLETE", "legacy_score": record.get("final_score"),
                "legacy_units": legacy_metadata_for_record(record).source_units.model_dump(),
                "canonical_score": None, "difference": None, "is_finalizable": False,
                "missing_requirements": ["Historical validated evidence snapshot", "Calibrated applicable rubric and policy",
                                         "Validated E/H measurements and coverage"],
                "methodology_differences": ["Legacy 60/30/10 mixtures and HR 0–90 double weighting cannot be reverse-engineered from a final number"],
                "anomalies": ["Legacy zero engineering score is not verified poor performance"] if (record.get("ai_evaluation") or {}).get("score") == 0 else []}
