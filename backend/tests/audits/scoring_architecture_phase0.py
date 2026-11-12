"""Phase-0 characterization probes, NOT desired future scoring behavior.

Run explicitly with:
  python -m pytest tests/audits/scoring_architecture_phase0.py -q -s

The filename deliberately avoids default test discovery. These probes assert
observed legacy defects so the audit can be repeated without modifying runtime
code. Replace them with desired-behavior regressions during the relevant phase.
All data is synthetic; MongoDB and model/GitHub boundaries are isolated.
"""

import asyncio
import copy
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from agents import performance_agent
from agents.performance_agent import PerformanceEvaluationAgent
from api.routes import performance as routes
from core import audit, database
from core.dependencies import get_current_user
from domain.models.developer_evaluation import DeveloperEvaluation
from domain.models.developer_performance import (
    AIEvaluation, CEOFeedback, DeveloperPerformance, DeveloperPerformanceCreate,
    LeadFeedback, PMFeedback, PerformanceBreakdown, RoleEvaluation,
)
from domain.models.hr_performance import HRAssessmentCreate, HRAssessmentDimensionItem, HRDimensionKey
from domain.services.hr_performance_service import HRPerformanceService
from domain.services.performance_service import PerformanceService
from domain.services.period_evidence import period_manifest
from intelligence.contribution_credit import calculate_contribution_credit, combine_hybrid_credit
from intelligence.developer_data_aggregator import DeveloperDataAggregator
from repositories.hr_performance_repository import DEFAULT_HUMAN_EVALUATION_POLICY
from repositories.performance_repository import PerformanceRepository

pytestmark = pytest.mark.anyio


def observe(finding, **values):
    print(json.dumps({"finding": finding, **values}, sort_keys=True))


def ai_result(score=77.4):
    return AIEvaluation(score=score, breakdown=PerformanceBreakdown(
        code_quality=0, delivery=0, collaboration=0, reliability=0,
        engineering_impact=0, engineering_judgment=0,
    ), reasoning="Synthetic typed upstream result; not a live Ollama assessment", confidence="low")


def assessment(**overrides):
    fields = dict(developer_id="AUDIT-DEV", developer_name="Synthetic employee", project_id="AUDIT-PROJECT",
        period_type="quarter", period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 10, 1, tzinfo=timezone.utc), period_label="2026-Q3",
        ai_evaluation=ai_result(), role_evaluation=RoleEvaluation(), final_score=85.4,
        grade="B+", confidence_level="low", confidence_reason="Synthetic audit fixture")
    fields.update(overrides)
    return DeveloperPerformance(**fields)


def role_rating(value):
    return dict(criterion_1=value, criterion_2=value, criterion_3=value, criterion_4=value)


def hr_data():
    return HRAssessmentCreate(dimensions={key.value: HRAssessmentDimensionItem(
        dimension=key.value, rating=4 if index == 0 else 3
    ) for index, key in enumerate(HRDimensionKey)})


@pytest.fixture
async def store(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    # AuditLogger is instantiated at import time; isolate that cached collection
    # too, while retaining the real audit-writing code.
    monkeypatch.setattr(audit.audit_logger, "collection", mock_db.audit_logs)
    await mock_db.users.insert_one({"employee_id": "AUDIT-DEV", "role": "DEVELOPER", "org_id": "ORG-B"})
    await mock_db.users.insert_one({"employee_id": "AUDIT-HR", "role": "HR", "designation": "HR_MANAGER", "org_id": "ORG-A"})
    return mock_db


def test_f1_formula_and_missing_human_denominator():
    objective = {"score": 86, "confidence": "low", "components": {}, "evidence_counts": {}}
    combined = combine_hybrid_credit(objective, ai_score=77.4, human_score=80)
    partial = combine_hybrid_credit(objective, ai_score=77.4)
    offline = combine_hybrid_credit(objective, ai_score=0, ai_available=False)
    assert combined["score"] == 85.4  # Equal E/normalized-AI can mask the conflict.
    other = combine_hybrid_credit({**objective, "score": 50}, ai_score=77.4, human_score=80)
    assert other["score"] == 63.8
    assert partial["components"]["human_weight"] == 0
    assert partial["components"]["objective_weight"] == pytest.approx(2 / 3)
    assert offline["score"] == 86
    observe("F1", masked_case=combined["score"], differing_objective=other["score"],
            missing_human=partial["score"], effective_weights=partial["components"], offline=offline["score"])


def test_f2_model_numeric_input_changes_aggregate():
    objective = {"score": 50, "components": {}}
    low = combine_hybrid_credit(objective, ai_score=18, human_score=80)["score"]
    high = combine_hybrid_credit(objective, ai_score=81, human_score=80)["score"]
    assert (low, high) == (44, 65)
    observe("F2", same_evidence_and_human=True, low_model_number=low, high_model_number=high,
            scope="aggregate contract; real parser separately blocked by F3")


def model_response(name, citation):
    return json.dumps({"dimensions": {name: {"score": 0.05, "reasoning": "Synthetic explanation", "evidence": [citation]}},
        "strengths": [], "weaknesses": [], "recommendations": [], "confidence": "low", "overall_reasoning": "Audit"})


@pytest.mark.skip(reason="Phase 3 retired the numeric parser; desired behavior is tested in test_performance_claims.py")
def test_f3_actual_manifest_cannot_supply_required_citations():
    data = {"pull_requests": [{"id": "p1"}]}
    agent = PerformanceEvaluationAgent.__new__(PerformanceEvaluationAgent)
    manifest = period_manifest(data)
    assert manifest["eligible_dimensions"] == ["innovation"] and "sources" not in manifest
    with pytest.raises(KeyError) as exc:
        agent._parse_ai_response(model_response("innovation", "pr:p1"), data)
    assert exc.value.args == ("sources",)
    observe("F3a", actual_parser_exception="KeyError: sources", eligible=manifest["eligible_dimensions"])


@pytest.mark.skip(reason="Phase 3 uses the canonical claim registry; legacy numeric parser is retired")
def test_f3_isolated_registry_lookup_is_incompatible(monkeypatch):
    # Supply only the missing manifest contract to expose the next real boundary.
    monkeypatch.setattr(performance_agent, "period_manifest", lambda _: {
        "eligible_dimensions": ["innovation"], "sources": {"pr:p1": {"kind": "pr"}}})
    agent = PerformanceEvaluationAgent.__new__(PerformanceEvaluationAgent)
    with pytest.raises(KeyError) as exc:
        agent._parse_ai_response(model_response("innovation", "pr:p1"), {})
    assert exc.value.args == ("innovation",)
    observe("F3b", exception="KeyError: innovation", scope="isolated missing-manifest repair only")


@pytest.mark.skip(reason="Phase 3 produces advisory proposals rather than numeric breakdowns")
def test_f3_isolated_breakdown_rejects_partial_registry(monkeypatch):
    monkeypatch.setattr(performance_agent, "period_manifest", lambda _: {
        "eligible_dimensions": ["code_quality"], "sources": {"commit:c1": {"kind": "commit"}}})
    agent = PerformanceEvaluationAgent.__new__(PerformanceEvaluationAgent)
    with pytest.raises(ValidationError) as exc:
        agent._parse_ai_response(model_response("code_quality", "commit:c1"), {})
    missing = sorted(error["loc"][0] for error in exc.value.errors() if error["type"] == "missing")
    assert missing == ["collaboration", "delivery", "engineering_impact", "engineering_judgment", "reliability"]
    observe("F3c", missing_fields=missing, scope="isolated known dimension after supplying manifest contract")


def test_f4_duplicate_activity_receives_additional_points():
    data = {"summary": {}, "pull_requests": [{"id": "same-pr", "state": "merged"}], "tasks": [], "bugs": {}}
    first = calculate_contribution_credit(data)["score"]
    repeated = calculate_contribution_credit({**data, "pull_requests": data["pull_requests"] * 2})["score"]
    assert (first, repeated) == (8, 16)
    observe("F4", single_source=first, duplicated_same_source=repeated)


def test_f5_equal_and_policy_weighted_human_aggregates_differ():
    record = assessment(role_evaluation=RoleEvaluation(pm=PMFeedback(**role_rating(1)), lead=LeadFeedback(**role_rating(5))))
    ordinary = PerformanceService.__new__(PerformanceService)._calculate_role_scores(record.role_evaluation)
    hr, _ = HRPerformanceService.__new__(HRPerformanceService).calculate_aggregated_human_score(record, DEFAULT_HUMAN_EVALUATION_POLICY)
    assert ordinary["average"] == 60 and hr == 63.08
    observe("F5", ordinary=ordinary["average"], policy_weighted=hr, required_hr_and_qa_missing=True)


async def test_f6_ceo_remains_numeric_reviewer_and_policy_option(store):
    role = RoleEvaluation(ceo=CEOFeedback(**role_rating(5)))
    score = PerformanceService.__new__(PerformanceService)._calculate_role_scores(role)
    policy = await HRPerformanceService().configure_policy({"ceo": 1.0}, configured_by="AUDIT-CEO")
    assert score["average"] == 100 and policy.role_weights == {"ceo": 1.0}
    assert await store.audit_logs.count_documents({"actor_id": "AUDIT-CEO"}) == 1
    observe("F6", ceo_only_human_score=score["average"], accepted_policy=policy.role_weights)


async def test_f7_empty_hr_submission_creates_zero_score_and_grade(store):
    result = await HRPerformanceService().submit_hr_assessment("AUDIT-DEV", HRAssessmentCreate(dimensions={}),
        {"employee_id": "AUDIT-HR", "role": "HR"})
    assert result.ai_evaluation.score == 0 and result.final_score == 0 and result.grade == "C+"
    assert await store.developer_performances.count_documents({"developer_id": "AUDIT-DEV"}) == 1
    observe("F7", ai_score=result.ai_evaluation.score, final_score=result.final_score, grade=result.grade)


async def test_f8_hr_path_applies_ninety_percent_to_legacy_ninety_point_score(store):
    await PerformanceRepository().create(assessment().model_dump())
    result = await HRPerformanceService().submit_hr_assessment("AUDIT-DEV", hr_data(), {"employee_id": "AUDIT-HR", "role": "HR"})
    assert result.ai_evaluation.score == 77.4 and result.role_evaluation.average_score == 80
    assert result.final_score == 77.66
    observe("F8", legacy_ai_contribution=77.4, human=80, actual=result.final_score, normalized_spec_example=85.4)


async def test_f9_not_observed_compatibility_fields_are_fabricated(store):
    result = await HRPerformanceService().submit_hr_assessment("AUDIT-DEV", HRAssessmentCreate(dimensions={}),
        {"employee_id": "AUDIT-HR", "role": "HR"})
    feedback = result.role_evaluation.hr
    assert feedback.normalized_score is None
    assert [feedback.criterion_1, feedback.criterion_2, feedback.criterion_3, feedback.criterion_4] == [3, 3, 3, 3]
    observe("F9", normalized=feedback.normalized_score, invented_legacy_criteria=[3, 3, 3, 3])


def test_f10_duplicates_and_invalid_period_still_establish_eligibility():
    data = {"commits": [{"sha": "same"}] * 20, "pull_requests": [{"id": "same"}] * 10,
        "period_start": "2026-10-01T00:00:00+00:00", "period_end": "2026-07-01T00:00:00+00:00"}
    manifest = period_manifest(data)
    assert manifest["evidence_quality"]["commits"] == "EXCELLENT"
    assert manifest["has_sufficient_evidence"] and manifest["period_validated"]
    assert "Invalid period: start_date is not before end_date" in manifest["warnings"]
    observe("F10", duplicate_quality=manifest["evidence_quality"], invalid_period_sufficient=manifest["has_sufficient_evidence"],
            period_validated=manifest["period_validated"])


def test_f11_pr_score_family_is_distinct_and_already_bounded():
    fields = dict(evaluation_id="AUDIT-EVAL", employee_id="AUDIT-DEV", github_username="audit", repo_owner="o",
        repo_name="r", pr_number=1, head_commit_sha="abc", evaluation_focus="code_quality", ai_provider="ollama", model_name="audit")
    assert DeveloperEvaluation(**fields, overall_score=8.6).overall_score == 8.6
    with pytest.raises(ValidationError):
        DeveloperEvaluation(**fields, overall_score=86)
    observe("F11", pr_scale_maximum=10, period_scale_maximum=100, classification="distinct semantics, not itself a defect")


@pytest.mark.skip(reason="Phase 3 blocks numeric period creation; replacement regression is in test_performance_claim_service.py")
async def test_f12_typed_ai_success_publishes_grade_before_human_feedback(store):
    service = PerformanceService()
    data = {"summary": {"total_commits": 0, "total_prs": 0, "total_tasks": 0}, "tasks": [], "pull_requests": []}
    service.data_aggregator.aggregate_developer_data = AsyncMock(return_value=data)
    service.evaluation_agent.evaluate_performance = AsyncMock(return_value=ai_result())
    result = await service.evaluate_developer(DeveloperPerformanceCreate(developer_id="AUDIT-DEV", project_id="P1",
        period_start=datetime(2026, 7, 1), period_end=datetime(2026, 10, 1), period_label="2026-Q3"),
        developer_name="Synthetic employee", developer_email="audit@example.invalid")
    assert result.role_evaluation.pm is None and result.role_evaluation.lead is None
    assert result.final_score == 28.67 and result.grade == "F" and result.credit_status == "advisory"
    observe("F12", final_score=result.final_score, grade=result.grade, status=result.credit_status,
            scope="real orchestration after a synthetic successful typed AI result; original parser remains blocked")


async def test_additional_aggregator_manifest_contract_mismatch(store):
    aggregator = DeveloperDataAggregator()
    aggregator._collect_tasks = AsyncMock(return_value={"tasks": [{"id": "task", "status": "done"}]})
    aggregator._collect_bugs = AsyncMock(return_value={})
    aggregator._collect_sprint_contributions = AsyncMock(return_value=[])
    data = await aggregator.aggregate_developer_data("AUDIT-DEV", "audit@example.invalid", "P1", datetime(2026, 7, 1), datetime(2026, 10, 1))
    assert len(data["tasks"]) == 1 and "completed_tasks" not in data
    assert period_manifest(data)["evidence_counts"]["completed_tasks"] == 0
    observe("A1", collected_completed_tasks=1, recognized_completed_tasks=0)


async def test_additional_feedback_retry_reuses_prior_composite_as_objective(store):
    credit = combine_hybrid_credit({"score": 50, "confidence": "low", "components": {}, "evidence_counts": {}}, ai_score=72)
    await PerformanceRepository().create(assessment(ai_evaluation=ai_result(72), final_score=credit["score"], contribution_credit=credit).model_dump())
    service = PerformanceService()
    first = await service.add_role_feedback("AUDIT-DEV", "lead", role_rating(5))
    second = await service.add_role_feedback("AUDIT-DEV", "lead", role_rating(5))
    assert (first.final_score, second.final_score) == (70, 76)
    observe("A2", same_feedback_first=first.final_score, same_feedback_retry=second.final_score)


async def test_f13_concurrent_feedback_loses_one_completed_submission(store):
    record_id = await PerformanceRepository().create(assessment().model_dump())
    services = [PerformanceService(), PerformanceService()]
    ready = asyncio.Event()
    reads = []
    for service in services:
        original = service.performance_repo.get_by_id
        async def snapshot(record, original=original):
            value = copy.deepcopy(await original(record))
            reads.append(1)
            if len(reads) == 2:
                ready.set()
            await ready.wait()
            return value
        service.performance_repo.get_by_id = snapshot
    results = await asyncio.wait_for(asyncio.gather(
        services[0].add_role_feedback(record_id, "lead", role_rating(5)),
        services[1].add_role_feedback(record_id, "pm", role_rating(4)),
    ), 2)
    saved = await PerformanceRepository().get_by_id(record_id)
    kept = [name for name in ["lead", "pm"] if saved["role_evaluation"].get(name)]
    assert len(results) == 2 and len(kept) == 1
    observe("F13-concurrency", successful_submissions=2, retained_reviews=kept)


async def test_f13_http_cross_org_read_and_self_hr_submission(store):
    await PerformanceRepository().create(assessment().model_dump())
    user = {"employee_id": "AUDIT-HR", "role": "HR", "designation": "HR_MANAGER", "org_id": "ORG-A", "is_admin": False}
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/performance")
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://audit") as client:
        foreign = await client.get("/api/performance/developer/AUDIT-DEV")
        assert foreign.status_code == 200 and foreign.json()["employee_id"] == "AUDIT-DEV"
        # A former engineering contributor now works in HR and has a historical
        # engineering assessment. Keep the synthetic principal consistent with
        # the current account; the route has no independent self-review guard.
        await store.users.update_one({"employee_id": "AUDIT-DEV"}, {"$set": {"role": "HR", "designation": "HR_MANAGER"}})
        user.update(employee_id="AUDIT-DEV", org_id="ORG-B")
        submitted = await client.post("/api/performance/assessment/hr/AUDIT-DEV/submit", json=hr_data().model_dump(mode="json"))
        assert submitted.status_code == 200
    observe("F13-authorization", cross_org_read_status=foreign.status_code, self_hr_submit_status=submitted.status_code,
            scope="real routes/repositories, synthetic authenticated principals")


@pytest.mark.skip(reason="Phase 3 preserves deterministic evidence on model outage; replacement test_performance_claims.py")
async def test_additional_ollama_outage_blocks_objective_calculation(store):
    service = PerformanceService()
    data = {"commits": [{"sha": "same"}] * 5, "pull_requests": [{"id": "pr"}] * 2,
            "summary": {"total_commits": 5, "total_prs": 2, "total_tasks": 0}}
    service.data_aggregator.aggregate_developer_data = AsyncMock(return_value=data)
    service.evaluation_agent.llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=TimeoutError("Ollama unavailable")))
    with pytest.raises(TimeoutError, match="Ollama unavailable"):
        await service.evaluate_developer(DeveloperPerformanceCreate(developer_id="AUDIT-DEV", project_id="P1",
            period_start=datetime(2026, 7, 1), period_end=datetime(2026, 10, 1), period_label="2026-Q3"),
            developer_name="Synthetic employee", developer_email="audit@example.invalid")
    assert await store.developer_performances.count_documents({}) == 0
    observe("A3", collected_evidence_present=True, exception="TimeoutError", objective_result_persisted=False)
