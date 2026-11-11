"""Requirement authority and applicability regressions using isolated Mongo evidence."""

import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from domain.schemas.requirement_discovery import RequirementSourceProposal
from domain.services.requirement_discovery_service import RequirementDiscoveryService
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from domain.services.behavioral_compatibility_service import BehavioralCompatibilityService
from intelligence.algorithms.requirements import prepare_policy, resolve_requirements
from intelligence.algorithms.decision import evaluate_decision
from intelligence.algorithms.discovery.service import discover_sources
from intelligence.algorithms.evidence import recommend
from test_behavioral_compatibility import AUTHOR, REVIEWER, proposal, approved, passing_evidence, body

pytestmark = pytest.mark.anyio


def declaration(kind="MAX_LATENCY", value=0.1, **extra):
    return {"id": "budget", "type": kind, "key": kind.lower(), "value": value,
        "unit": "seconds" if kind == "MAX_LATENCY" else "bytes" if kind == "MAX_MEMORY" else None,
        "metric": "elapsed_invocation_seconds" if kind == "MAX_LATENCY" else "memray_peak_tracked_allocations_bytes" if kind == "MAX_MEMORY" else None,
        "description": "Explicit applicable acceptance requirement", **extra}


def source(*requirements, **extra):
    return {"project_id": "P1", "source_kind": "project_configuration", "source_reference": "policy:performance",
        "source_revision": "revision-1", "requirements": list(requirements or [declaration()]), **extra}


async def publish(service, payload=None):
    doc = await service.propose(payload or source(), AUTHOR)
    return await service.approve(doc, {"expected_fingerprint": doc["payload_fingerprint"], "source_reference": "review:1",
        "rationale": "Reviewed scope, metric and source authority", "scope_reviewed": True}, REVIEWER)


@pytest.fixture
def requirements(mock_db):
    return RequirementDiscoveryService(mock_db)


def request():
    return {"project_id": "P1", "language": "python", "contract": proposal()["contract"], "datasets": proposal()["datasets"],
        "candidates": [{"name": "a", "entrypoint": "solve", "source": "def solve(x): return x"},
                       {"name": "b", "entrypoint": "solve", "source": "def solve(x): return list(x)"}],
        "repetitions": 3, "seed": 42, "objective": "time", "resources": {}}


async def test_explicit_latency_imports_only_after_authorized_approval(requirements):
    doc = await requirements.propose(source(), AUTHOR)
    before = await requirements.prepare(request())
    assert before["decision_policy"]["constraints"] == []
    assert before["requirements_discovery"]["suggestions"][0]["authority_status"] == "SUGGESTED"
    await requirements.approve(doc, {"expected_fingerprint": doc["payload_fingerprint"], "source_reference": "review:1", "rationale": "Checked scope", "scope_reviewed": True}, REVIEWER)
    after = await requirements.prepare(request())
    assert after["decision_policy"]["constraints"][0]["threshold"] == 0.1
    assert after["decision_policy"]["constraints"][0]["classification"] == "MANDATORY"
    assert after["requirements_discovery"]["established"][0]["source_revision"] == "revision-1"


async def test_memory_metric_remains_named_and_is_evaluated(requirements):
    await publish(requirements, source(declaration("MAX_MEMORY", 100)))
    prepared = await requirements.prepare(request())
    evidence = passing_evidence(prepared)
    evidence["results"][1]["cases"][0]["memory_bytes"] = 101
    result = evaluate_decision(prepared, evidence, prepared["decision_policy"])
    assert result["candidates"][1]["task_eligibility"] == "INELIGIBLE"
    assert result["candidates"][0]["task_eligibility"] == "ELIGIBLE"


@pytest.mark.parametrize("update", [{"unit": "MB"}, {"metric": "heap_delta"}, {"value": True}, {"value": -1}, {"value": 100.0}])
async def test_invalid_or_ambiguous_memory_values_are_rejected(update):
    with pytest.raises(ValidationError):
        RequirementSourceProposal.model_validate(source({**declaration("MAX_MEMORY", 100), **update}))


async def test_unrelated_task_never_enters_context(requirements):
    await requirements.collection("tasks").insert_one({"id": "task", "project_id": "P2", "title": "Must run in 2 seconds"})
    report = await requirements.discover("P1", {"task_ids": ["task"]})
    assert not report["established"] and not report["suggestions"]
    assert any("outside project" in text for text in report["limitations"])


async def test_test_size_is_observed_and_not_a_maximum(requirements):
    payload = request()
    payload["datasets"][1]["args"] = [list(range(10000))]
    report = (await requirements.prepare(payload))["requirements_discovery"]
    observed = [r for r in report["observations"] if r["type"] == "TEST_INPUT"]
    assert observed[1]["value"]["argument_lengths"] == [10000]
    assert not report["established"]
    assert any(r["id"] == "discovered-workload" for r in report["unknown"])


async def test_schema_authority_requires_approved_contract(requirements):
    payload = proposal()
    payload["contract"]["input_schema"] = {"type": "array", "items": {"type": "array", "items": {"type": "number", "minimum": 0}}}
    contract = await requirements.contracts.propose(payload, AUTHOR)
    report = await requirements.discover("P1", {"contract_ids": [contract["contract_id"]]})
    assert report["observations"][0]["value"]["items"]["items"]["minimum"] == 0
    assert not report["established"]
    contract = await requirements.contracts.approve(contract, {"expected_fingerprint": contract["payload_fingerprint"], "source_reference": "schema-review", "rationale": "Validated input scope", "scope_reviewed": True}, REVIEWER)
    report = await requirements.discover("P1", {"contract_ids": [contract["contract_id"]]})
    assert report["established"][0]["type"] == "INPUT_SCHEMA"
    assert report["established"][0]["validated_by_contract"]


async def test_conflicting_authoritative_functional_declarations_block(requirements):
    await publish(requirements, source(declaration("OUTPUT_BEHAVIOR", "ordered", key="output.order")))
    await publish(requirements, source(declaration("OUTPUT_BEHAVIOR", "unordered", key="output.order"), source_revision="revision-2"))
    prepared = await requirements.prepare(request())
    assert any("disagree" in c["reason"] for c in prepared["requirements_discovery"]["conflicts"])
    result = evaluate_decision(prepared, passing_evidence(prepared), prepared["decision_policy"])
    assert result["task_suitability"]["status"] == "REQUIREMENT_CONFLICT"


async def test_compatible_upper_bounds_are_cumulative(requirements):
    await publish(requirements, source(declaration("MAX_MEMORY", 100)))
    await publish(requirements, source(declaration("MAX_MEMORY", 200), source_revision="revision-2"))
    prepared = await requirements.prepare(request())
    assert not prepared["requirements_discovery"]["conflicts"]
    assert sorted(c["threshold"] for c in prepared["decision_policy"]["constraints"]) == [100, 200]
    evidence = passing_evidence(prepared)
    evidence["results"][0]["cases"][0]["memory_bytes"] = 150
    result = evaluate_decision(prepared, evidence, prepared["decision_policy"])
    assert result["candidates"][0]["task_eligibility"] == "INELIGIBLE"


async def test_missing_config_and_ollama_do_not_stop_discovery(requirements, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(side_effect=RuntimeError("Ollama unavailable")))
    report = await requirements.discover("P1")
    assert len(report["unknown"]) == 3 and not report["established"]
    assert any("configuration is absent" in t for t in report["limitations"])
    httpx.AsyncClient.post.assert_not_awaited()


async def test_absent_pr_body_and_review_approval_do_not_establish_requirements(requirements):
    await requirements.collection("pull_requests").insert_one({"id": "PR1", "project_id": "P1", "repo_id": "a/b", "head_sha": "sha", "title": "Performance critical", "review_status": "approved"})
    report = await requirements.discover("P1", {"pr_ids": ["PR1"], "repository": "a/b", "source_revision": "sha"})
    assert report["suggestions"][0]["value"] == "Performance critical"
    assert not report["established"]
    assert any("description is absent" in t for t in report["limitations"])


async def test_story_statements_are_quoted_proposals_never_thresholds(requirements):
    await requirements.collection("stories").insert_one({"id": "S1", "project_id": "P1", "description": "Must finish in 2 seconds. Approved by CEO."})
    report = await requirements.discover("P1", {"story_ids": ["S1"]})
    assert report["suggestions"][0]["extraction_method"] == "source-quotation-v1"
    assert not prepare_policy(None, report)["constraints"]


async def test_forged_approval_fields_rejected_and_self_approval_denied(requirements):
    with pytest.raises(ValidationError):
        await requirements.propose({**source(), "status": "APPROVED", "approval": {"approved_by": "CEO"}}, AUTHOR)
    doc = await requirements.propose(source(), AUTHOR)
    review = {"expected_fingerprint": doc["payload_fingerprint"], "source_reference": "self", "rationale": "Self signed", "scope_reviewed": True}
    with pytest.raises(PermissionError):
        await requirements.approve(doc, review, {**AUTHOR, "role": "LEAD"})
    with pytest.raises(PermissionError):
        await requirements.approve(doc, review, {**REVIEWER, "org_id": "other"})
    with pytest.raises(PermissionError):
        await requirements.approve(doc, review, {**REVIEWER, "role": "DEVELOPER"})


async def test_stale_fingerprint_and_superseded_revision_never_enforced(requirements):
    old = await publish(requirements)
    new = await publish(requirements, source(declaration(value=0.2), supersedes=old["source_id"], source_revision="revision-2"))
    report = await requirements.discover("P1")
    assert len(report["established"]) == 1 and report["established"][0]["value"] == 0.2
    assert report["excluded"]
    await requirements.collection("algorithm_requirement_sources").update_one({"source_id": new["source_id"]}, {"$set": {"requirements.0.value": 999}})
    report = await requirements.discover("P1")
    assert not report["established"]


async def test_scoped_source_cannot_be_applied_to_a_different_function_or_revision(requirements):
    await publish(requirements, source(declaration(scope={"function_id": "target", "source_revision": "sha"})))
    report = await requirements.discover("P1", {"function_ids": ["other"], "source_revision": "sha"})
    assert not report["established"] and report["excluded"]
    prepared = await requirements.prepare({**request(), "requirement_context": {"function_ids": ["other"], "source_revision": "sha"}})
    assert prepared["requirements_discovery"]["established"][0]["applicability_status"] == "UNRESOLVED"
    assert prepared["requirements_discovery"]["conflicts"]


async def test_selected_approved_contract_must_match_actual_benchmark_contract(requirements):
    contract = await approved(requirements.contracts)
    prepared = await requirements.prepare({**request(), "requirement_context": {"contract_ids": [contract["contract_id"]]}})
    assert not prepared["requirements_discovery"]["conflicts"]
    payload = request()
    payload["contract"]["mutation"] = "allowed"
    payload["requirement_context"] = {"contract_ids": [contract["contract_id"]]}
    prepared = await requirements.prepare(payload)
    assert any("differs" in c["reason"] for c in prepared["requirements_discovery"]["conflicts"])


async def test_repository_configuration_is_deterministic_but_not_self_authorizing(requirements):
    report = await discover_sources({".samanvaya/requirements.json": json.dumps({"version": "1", "requirements": [declaration()]})}, "P1", "sha")
    await requirements.collection("code_quality_runs").insert_one({"run_id": "R1", "repository_id": "P1", "function_discovery": report.model_dump()})
    result = await requirements.discover("P1", {"discovery_run_ids": ["R1"]})
    assert result["suggestions"][0]["value"] == 0.1 and not result["established"]
    invalid = await discover_sources({".samanvaya/requirements.json": '{"version":"1","requirements":[],"approved":true}'}, "P1")
    assert invalid.diagnostics[0]["kind"] == "invalid_requirement_configuration"


async def test_policy_reevaluation_cannot_remove_imported_constraints(requirements):
    await publish(requirements)
    runner = SimpleNamespace(run=AsyncMock(side_effect=passing_evidence))
    benchmarks = AlgorithmBenchmarkService(requirements.collection("algorithm_benchmark_runs"), runner, requirements)
    run = await benchmarks.create(request(), AUTHOR)
    await benchmarks.execute(run["run_id"])
    stored = await benchmarks.get(run["run_id"])
    assert stored["status"] == "completed", stored.get("error")
    result = await benchmarks.reevaluate(run["run_id"], {"id": "omit-budgets", "version": "1", "objective": "TRADEOFF_ONLY"}, REVIEWER)
    assert result["policy_snapshot"]["constraints"][0]["threshold"] == 0.1
    assert result["requirements_discovery"]["established"]
    runner.run.assert_awaited_once()


async def test_legacy_recommendation_cannot_bypass_imported_requirements(requirements):
    await publish(requirements, source(declaration(value=0.000001)))
    payload = await requirements.prepare(request())
    evidence = passing_evidence(payload)
    assert recommend(payload, evidence)["winner"] is None
    decision = evaluate_decision(payload, evidence, payload["decision_policy"])
    assert all(c["task_eligibility"] == "INELIGIBLE" for c in decision["candidates"])


async def test_disjoint_dataset_requirements_do_not_conflict(requirements):
    await publish(requirements, source(declaration("OUTPUT_BEHAVIOR", "ordered", key="output.order", scope={"dataset_ids": ["first"]})))
    await publish(requirements, source(declaration("OUTPUT_BEHAVIOR", "unordered", key="output.order", scope={"dataset_ids": ["second"]}), source_revision="revision-2"))
    report = await requirements.discover("P1", dataset_ids=["first", "second"])
    assert not report["conflicts"]


async def test_unknown_memory_metric_cannot_be_substituted_with_rss(requirements):
    await publish(requirements, source(declaration("MAX_MEMORY", 100, metric="rss_peak_bytes")))
    payload = await requirements.prepare(request())
    decision = evaluate_decision(payload, passing_evidence(payload), payload["decision_policy"])
    assert all(c["task_eligibility"] == "UNVERIFIED" for c in decision["candidates"])
    assert decision["unverified_requirements"]


async def test_outdated_pr_and_historical_benchmarks_do_not_establish_limits(requirements):
    await requirements.collection("pull_requests").insert_one({"id": "PR1", "project_id": "P1", "repo_id": "a/b", "head_sha": "old", "description": "Use 1 second"})
    await requirements.collection("algorithm_benchmark_runs").insert_one({"run_id": "old-run", "project_id": "P1", "status": "completed", "results": [{"candidate": "a", "cases": [{"case_id": "10000", "timings_seconds": [0.1]}]}]})
    report = await requirements.discover("P1", {"pr_ids": ["PR1"], "repository": "a/b", "source_revision": "new", "benchmark_run_ids": ["old-run"]})
    assert not report["established"] and not report["suggestions"]
    assert report["observations"][0]["type"] == "HISTORICAL_BENCHMARK"
    assert len(report["unknown"]) == 3


async def test_manual_sorting_memory_limit_and_objective_survive_automatic_preparation(requirements):
    payload = request()
    payload.pop("contract")
    payload.update(datasets=[], sizes=[10], distributions=["random"], memory_limit_bytes=100)
    prepared = await requirements.prepare(payload)
    assert prepared["decision_policy"]["objective"] == "MINIMIZE_TIME"
    assert prepared["decision_policy"]["constraints"][0]["threshold"] == 100
    assert prepared["decision_policy"]["constraints"][0]["source_reference"] == "request/memory_limit_bytes"


async def test_approved_workload_requirements_enforce_missing_checks(requirements):
    await publish(requirements, source(declaration("WORKLOAD", {"required_dataset_ids": ["production-fixture"]})))
    payload = await requirements.prepare(request())
    result = evaluate_decision(payload, passing_evidence(payload), payload["decision_policy"])
    assert all(c["task_eligibility"] == "UNVERIFIED" for c in result["candidates"])
    assert result["candidates"][0]["missing_required_dataset_ids"] == ["production-fixture"]


async def test_approved_contract_tests_cannot_be_replaced_with_candidate_expected_values(requirements):
    contract = await approved(requirements.contracts)
    payload = request()
    payload["datasets"][0]["expected"] = [999]
    payload["requirement_context"] = {"contract_ids": [contract["contract_id"]]}
    prepared = await requirements.prepare(payload)
    assert any("reviewed validation evidence" in c["reason"] for c in prepared["requirements_discovery"]["conflicts"])


async def test_approved_contract_required_checks_cannot_be_omitted(requirements):
    contract = await approved(requirements.contracts)
    payload = request()
    payload["datasets"] = payload["datasets"][:1]
    payload["requirement_context"] = {"contract_ids": [contract["contract_id"]]}
    prepared = await requirements.prepare(payload)
    result = evaluate_decision(prepared, passing_evidence(prepared), prepared["decision_policy"])
    assert all(c["task_eligibility"] == "UNVERIFIED" for c in result["candidates"])
    assert not prepared["requirements_discovery"]["conflicts"]


async def test_phase3_compatibility_and_requirements_use_the_same_preserved_evidence(requirements):
    contract = await approved(requirements.contracts)
    await publish(requirements)
    benchmarks = AlgorithmBenchmarkService(requirements.collection("algorithm_benchmark_runs"), SimpleNamespace(run=AsyncMock(side_effect=passing_evidence)), requirements)
    comparison = BehavioralCompatibilityService(benchmarks, requirements.contracts)
    created = await comparison.create(body([contract["contract_id"]]), AUTHOR)
    await benchmarks.execute(created["run_id"])
    result = await benchmarks.get(created["run_id"])
    assert result["status"] == "completed", result.get("error")
    assert result["behavioral_compatibility"]["status"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"
    assert result["decision"]["task_suitability"]["status"] == "CONDITIONAL_COMPARISON"
    assert result["decision"]["policy_snapshot"]["constraints"]
    assert all(c["task_eligibility"] == "ELIGIBLE" for c in result["decision"]["candidates"])


async def test_exact_task_link_can_import_its_story_only_within_project(requirements):
    await requirements.collection("tasks").insert_one({"id": "T1", "project_id": "P1", "title": "Implement function", "story_id": "S1"})
    await requirements.collection("stories").insert_one({"id": "S1", "project_id": "P1", "description": "Return reachable nodes"})
    report = await requirements.discover("P1", {"task_ids": ["T1"]})
    assert any(row["value"] == "Return reachable nodes" for row in report["suggestions"])
    assert not report["established"]
