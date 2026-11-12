"""Predicate checks, not citations or LLM prose, establish narrow validated facts."""

import asyncio
import importlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from intelligence.performance_evidence import build_evidence_snapshot, evidence_digest
from domain.models.performance_evidence import EvidenceScope


def models():
    return importlib.import_module("domain.models.performance_claims")


def claims():
    return importlib.import_module("intelligence.performance_claims")


def snapshot(kind="pr", **changes):
    scope = EvidenceScope(organization_id="O", employee_id="D", project_id="P", repository="o/r",
        period_start="2026-07-01T00:00:00Z", period_end="2026-10-01T00:00:00Z")
    origin = {"pr": "pull_requests", "test_run": "test_runs", "benchmark": "algorithm_benchmark_runs", "review": "code_reviews"}[kind]
    row = dict(kind=kind, origin=origin, external_id="1", organization_id="O", project_id="P", repository="o/r",
        occurred_at="2026-08-01T00:00:00Z", source_revision="a" * 40, actor_id="D", shared=False,
        attribution_basis="EXACT_GITHUB_MAPPING", facts={"status": "merged", "head_sha": "a" * 40})
    row.update(changes)
    return build_evidence_snapshot(scope, [row], captured_at=datetime(2026, 11, 12, tzinfo=timezone.utc))


def proposal(snap, **changes):
    record = snap.records[0]
    return {**dict(claim_id="c1", claim_type="recorded_status", dimension_id="delivery",
        citations=[{"source_id": record.source_id, "content_digest": record.content_digest}],
        expected_status="merged", interpretation="Possible delivery contribution; ownership/quality remain uncertain."), **changes}


def decide(snap, item):
    payload = models().ClaimProposal.model_validate(item)
    return claims().validate_claim(payload, snap, evidence_digest(snap))


def test_correct_typed_status_predicate_is_validated_without_approving_prose_or_points():
    snap = snapshot()
    decision = decide(snap, proposal(snap, interpretation="This proves 100% productivity and deserves promotion."))
    assert decision.status == "VALIDATED"
    assert decision.fact.predicate == "recorded_status" and decision.fact.recorded_status == "merged"
    assert "productivity" not in decision.fact.model_dump_json()
    assert decision.score_effect is None and decision.fact.is_performance_credit is False


def test_correct_citation_but_false_predicate_is_rejected():
    snap = snapshot()
    result = decide(snap, proposal(snap, expected_status="closed"))
    assert result.status == "REJECTED" and result.fact is None


@pytest.mark.parametrize("change", [
    {"citations": [{"source_id": "f" * 64, "content_digest": "a" * 64}]},
    {"citations": [{"source_id": "a" * 64, "content_digest": "f" * 64}]},
    {"dimension_id": "collaboration"},
])
def test_fabricated_or_irrelevant_citations_do_not_validate(change):
    snap = snapshot()
    assert decide(snap, proposal(snap, **change)).status == "REJECTED"


@pytest.mark.parametrize("key", ["score", "final_score", "weight", "approved", "permissions", "role", "override"])
def test_model_authority_fields_are_rejected(key):
    snap = snapshot()
    with pytest.raises(ValidationError):
        models().ProposalPayload.model_validate({"claims": [{**proposal(snap), key: 100}]})


@pytest.mark.parametrize("changes", [dict(actor_id=None), dict(shared=True), dict(source_revision=None),
    dict(disputed=True), dict(deleted=True), dict(current_head_sha="b" * 40), dict(occurred_at="2025-01-01T00:00:00Z")])
def test_unverified_stale_disputed_and_out_of_period_evidence_never_auto_validates(changes):
    snap = snapshot(**changes)
    result = decide(snap, proposal(snap))
    assert result.status in {"REJECTED", "NEEDS_REVIEW"} and result.fact is None


def test_test_outcome_verifies_counts_not_merely_run_existence():
    snap = snapshot("test_run", facts={"status": "passed", "head_sha": "a" * 40,
        "tests_run": 10, "tests_passed": 7, "tests_failed": 0, "tests_skipped": 3})
    item = proposal(snap, claim_type="recorded_test_outcome", dimension_id="reliability", expected_status=None,
        test_outcome="PASSED", tests_passed=7, tests_failed=0, tests_skipped=3)
    assert decide(snap, item).status == "VALIDATED"
    assert decide(snap, {**item, "tests_passed": 10}).status == "REJECTED"


def test_failed_run_with_zero_failed_cases_cannot_be_called_a_passing_execution():
    snap = snapshot("test_run", facts={"status": "failed", "head_sha": "a" * 40,
        "tests_run": 10, "tests_passed": 10, "tests_failed": 0, "tests_skipped": 0})
    item = proposal(snap, claim_type="recorded_test_outcome", dimension_id="reliability", expected_status=None,
        test_outcome="PASSED", tests_passed=10, tests_failed=0, tests_skipped=0)
    assert decide(snap, item).status != "VALIDATED"


def test_interpretation_contract_rejects_complete_output_without_traceable_proposal():
    with pytest.raises(ValidationError):
        models().Interpretation(status="COMPLETED", snapshot_digest="a" * 64, model_id="test")


def test_registry_and_prompt_schema_share_all_claim_and_dimension_identifiers():
    from typing import get_args
    assert set(get_args(models().ClaimType)) == set(claims().CLAIM_KINDS)
    contract = claims().prompt_contract()
    assert set(contract["dimensions"]) == set(models().ClaimProposal.model_json_schema()["$defs"]["DimensionId"]["enum"])


def test_benchmark_status_cannot_prove_an_improvement():
    snap = snapshot("benchmark", facts={"status": "completed"})
    result = decide(snap, proposal(snap, claim_type="possible_benchmark_improvement", dimension_id="engineering_impact", expected_status=None))
    assert result.status == "NEEDS_REVIEW" and result.fact is None


def test_subjective_claim_requires_independent_qualified_review():
    snap = snapshot()
    result = decide(snap, proposal(snap, claim_type="possible_architecture_tradeoff", dimension_id="engineering_judgment", expected_status=None))
    assert result.status == "NEEDS_REVIEW" and result.fact is None


def test_duplicate_claims_and_unbounded_output_are_rejected():
    snap = snapshot()
    item = proposal(snap)
    with pytest.raises(ValidationError):
        models().ProposalPayload(claims=[item, item])
    with pytest.raises(ValidationError):
        models().ProposalPayload(claims=[{**item, "claim_id": str(i)} for i in range(17)])
    with pytest.raises(ValueError):
        claims().parse_proposals(" " * 64001)
    for text in ("```json\n{}\n```", '{"claims":[],"claims":[]}', '{"claims":[],"score":NaN}'):
        with pytest.raises(ValueError):
            claims().parse_proposals(text)


@pytest.mark.anyio
async def test_period_agent_is_nonnumeric_and_uses_canonical_prompt_contract():
    from agents.performance_agent import PerformanceEvaluationAgent
    snap = snapshot()
    agent = PerformanceEvaluationAgent.__new__(PerformanceEvaluationAgent)
    agent.llm = SimpleNamespace(ainvoke=AsyncMock(return_value=json.dumps({"claims": [proposal(snap)]})))
    result = await agent.interpret_snapshot(snap)
    prompt = agent.llm.ainvoke.call_args.args[0]
    assert "engineering_judgment" in prompt and "technical_design" not in prompt and "innovation" not in prompt
    assert result.status == "COMPLETED" and result.engineering_score is None and result.combined_score is None
    assert result.decisions[0].status == "VALIDATED" and result.model_output_digest
    assert result.prompt_digest and result.prompt_version == "performance-claims-prompt-v1"


@pytest.mark.anyio
@pytest.mark.parametrize("response", [TimeoutError("offline"), "not json", '{"claims":[],"final_score":100}'])
async def test_ollama_outage_or_invalid_output_preserves_deterministic_evidence(response):
    from agents.performance_agent import PerformanceEvaluationAgent
    snap = snapshot()
    before = evidence_digest(snap)
    agent = PerformanceEvaluationAgent.__new__(PerformanceEvaluationAgent)
    agent.llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=response) if isinstance(response, Exception) else AsyncMock(return_value=response))
    result = await agent.interpret_snapshot(snap)
    assert result.status in {"UNAVAILABLE", "INVALID_OUTPUT"}
    assert result.snapshot_digest == before and evidence_digest(snap) == before
    assert result.engineering_score is None and result.combined_score is None


@pytest.mark.anyio
async def test_agent_has_a_bounded_timeout(monkeypatch):
    from agents import performance_agent
    async def hanging(*args):
        await asyncio.Event().wait()
    monkeypatch.setattr(performance_agent, "CLAIM_TIMEOUT_SECONDS", 0.01)
    agent = performance_agent.PerformanceEvaluationAgent.__new__(performance_agent.PerformanceEvaluationAgent)
    agent.llm = SimpleNamespace(ainvoke=hanging)
    assert (await agent.interpret_snapshot(snapshot())).status == "UNAVAILABLE"


@pytest.mark.anyio
async def test_legacy_period_agent_cannot_return_model_generated_scores():
    from agents.performance_agent import PerformanceEvaluationAgent
    agent = PerformanceEvaluationAgent.__new__(PerformanceEvaluationAgent)
    with pytest.raises(ValueError, match="retired"):
        await agent.evaluate_performance({}, "employee", "2026-Q3")
