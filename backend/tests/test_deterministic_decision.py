"""Synthetic evidence only: deterministic decisions never execute submitted source."""

import copy
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from domain.schemas.algorithm_benchmark import BenchmarkRequest
from domain.schemas.decision_policy import DecisionPolicy, PEAK_TRACKED
from intelligence.algorithms.decision import evaluate_decision, fingerprint, identities
from intelligence.algorithms.runner import BenchmarkFailure, DockerBenchmarkRunner


def fixture(language="python"):
    request = BenchmarkRequest.model_validate({
        "project_id": "P1", "language": language, "repetitions": 3,
        "contract": {"kind": "function", "name": "behavior", "version": "1",
                     "input_schema": {"type": "array"}, "output_schema": {}, "correctness": "expected"},
        "datasets": [{"id": "small", "args": [1, 2], "expected": 3},
                     {"id": "large", "args": [2, 3], "expected": 5}],
        "candidates": [{"name": name, "source": "NEVER EXECUTE", "entrypoint": "solve"} for name in ("a", "b")],
    }).model_dump()
    evidence = {"environment": {"images": {"worker": "sha256:immutable"}, "cpus": 1,
        "memory_limit_bytes": 536870912, "timing_method": "synthetic-v1",
        "workers": [{"candidate": name, "runtime": "test", "platform": "test"} for name in ("a", "b")]},
        "tools": {"timing": "test", "memory": "test"}, "results": []}
    for name, seconds in (("a", 1), ("b", 2)):
        evidence["results"].append({"candidate": name, "error": None, "cases": [
            {"case_id": d["id"], "dimensions": {}, "correct": True, "validation_status": "verified", "error": None,
             "measurement_version": "independent-v1", "timing_status": "AVAILABLE", "timing_error": None,
             "timings_seconds": [seconds] * 3, "memory_status": "AVAILABLE", "memory_error": None,
             "memory_bytes": 100 if name == "a" else 200,
             "memory_metric": PEAK_TRACKED if language == "python" else "node_heap_used_delta_bytes"}
            for d in request["datasets"]]})
    return request, evidence, {"id": "P", "version": "1", "objective": "MINIMIZE_TIME"}


def constraint(kind="MAX_LATENCY", **overrides):
    value = {"id": "requirement", "type": kind, "source_reference": "project:spec/1"}
    value.update({"MAX_LATENCY": {"threshold": 1.0, "unit": "seconds", "metric": "elapsed_invocation_seconds", "evaluation_policy": "MAX_OBSERVED_INVOCATION"},
                  "MAX_MEMORY": {"threshold": 100, "unit": "bytes", "metric": PEAK_TRACKED, "evaluation_policy": "OBSERVED_PEAK"},
                  "EXPECTED_OUTPUT": {"evaluation_policy": "ALL_EXPECTED"},
                  "DATASET_COVERAGE": {"required_dataset_ids": ["small", "large"], "evaluation_policy": "ALL_REQUIRED"}}[kind])
    return {**value, **overrides}


def decide(request, evidence, policy, **overrides):
    return evaluate_decision(request, evidence, {**policy, **overrides}, "RUN1")


def case(evidence, candidate=0, dataset=0):
    return evidence["results"][candidate]["cases"][dataset]


def unavailable(case, kind):
    case.update({kind + "_status": "UNAVAILABLE", kind + "_error": "instrument unavailable"})
    case["timings_seconds" if kind == "timing" else "memory_bytes"] = [] if kind == "timing" else None


def checks(decision, index=0, constraint_id="requirement"):
    return [c for c in decision["candidates"][index]["constraint_evaluations"] if c["constraint_id"] == constraint_id]


def test_pure_pipeline_preserves_all_inputs_and_reports_dataset_winners():
    request, evidence, policy = fixture()
    before = copy.deepcopy((request, evidence, policy))
    with patch("builtins.exec", side_effect=AssertionError("No execution")), patch("builtins.open", side_effect=AssertionError("No IO")):
        decision = decide(request, evidence, policy)
    assert (request, evidence, policy) == before
    assert [c["winner"] for c in decision["dataset_comparisons"]] == ["a", "a"]
    assert decision["task_suitability"]["global_winner"] is None
    assert decision["engine_version"] and decision["policy_fingerprint"]
    json.dumps(decision, allow_nan=False)


@pytest.mark.parametrize("kind,threshold,status", [("MAX_LATENCY", 0.99, "FAIL"), ("MAX_LATENCY", 1.0, "PASS"),
    ("MAX_LATENCY", 1.01, "PASS"), ("MAX_MEMORY", 99, "FAIL"), ("MAX_MEMORY", 100, "PASS"), ("MAX_MEMORY", 101, "PASS")])
def test_inclusive_latency_and_memory_boundaries(kind, threshold, status):
    request, evidence, policy = fixture()
    result = decide(request, evidence, policy, constraints=[constraint(kind, threshold=threshold)])
    assert checks(result)[0]["status"] == status
    assert checks(result)[0]["evidence_reference"].startswith("RUN1/")
    if kind == "MAX_LATENCY":
        assert checks(result)[0]["observed_maximum"] == 1
        assert checks(result)[0]["sample_count"] == 3


def test_latency_uses_maximum_not_median_and_timeout_is_not_acceptance_budget():
    request, evidence, policy = fixture()
    case(evidence)["timings_seconds"] = [1, 1, 3]
    request["resources"] = {"timeout_seconds": 1}
    assert checks(decide(request, evidence, policy, constraints=[constraint(threshold=2.0)]))[0]["status"] == "FAIL"
    result = decide(request, evidence, policy)
    assert result["candidates"][0]["task_eligibility"] == "ELIGIBLE"
    assert result["candidates"][0]["constraint_evaluations"] == []


@pytest.mark.parametrize("kind", ["timing", "memory"])
def test_optional_measurement_failure_is_independent(kind):
    request, evidence, policy = fixture()
    for r in evidence["results"]:
        for c in r["cases"]:
            unavailable(c, kind)
    objective = "MINIMIZE_TIME" if kind == "memory" else "MINIMIZE_MEMORY"
    result = decide(request, evidence, policy, objective=objective, memory_metric=PEAK_TRACKED)
    assert result["dataset_comparisons"][0]["winner"] == "a"
    assert result["candidates"][0]["task_eligibility"] == "ELIGIBLE"
    assert result["missing_evidence"][0]["measurement"] == kind


@pytest.mark.parametrize("metric,missing", [("rss_peak_bytes", False), (PEAK_TRACKED, True)])
def test_established_memory_budget_with_wrong_or_missing_evidence_is_unverified(metric, missing):
    request, evidence, policy = fixture()
    if missing:
        unavailable(case(evidence), "memory")
    result = decide(request, evidence, policy, constraints=[constraint("MAX_MEMORY", metric=metric)])
    assert checks(result)[0]["status"] == "UNVERIFIED"
    assert result["candidates"][0]["task_eligibility"] == "UNVERIFIED"


def test_node_heap_delta_never_satisfies_peak_constraints_or_optimization():
    request, evidence, policy = fixture("javascript")
    result = decide(request, evidence, policy, constraints=[constraint("MAX_MEMORY")])
    assert checks(result)[0]["status"] == "UNVERIFIED"
    result = decide(request, evidence, policy, objective="MINIMIZE_MEMORY", memory_metric=PEAK_TRACKED)
    assert result["dataset_comparisons"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(ValidationError):
        DecisionPolicy.model_validate({**policy, "objective": "MINIMIZE_MEMORY", "memory_metric": "node_heap_used_delta_bytes"})


def test_unknown_threshold_does_not_invent_constraints_or_block_time():
    request, evidence, policy = fixture()
    result = decide(request, evidence, policy, unknown_requirements=[{"id": "memory", "description": "Budget unknown"}])
    assert result["candidates"][0]["task_eligibility"] == "ELIGIBLE"
    assert result["candidates"][0]["constraint_evaluations"] == []
    assert result["dataset_comparisons"][0]["winner"] == "a"
    assert result["task_suitability"]["status"] == "CONDITIONAL_COMPARISON"


def test_missing_dataset_coverage_is_unverified_including_missing_declared_case():
    request, evidence, policy = fixture()
    result = decide(request, evidence, policy, constraints=[constraint("DATASET_COVERAGE", required_dataset_ids=["missing"])])
    assert checks(result)[0]["status"] == "UNVERIFIED"
    assert checks(result)[0]["missing_dataset_ids"] == ["missing"]
    evidence["results"][0]["cases"].pop()
    result = decide(request, evidence, policy, constraints=[constraint("DATASET_COVERAGE")])
    assert checks(result)[0]["missing_dataset_ids"] == ["large"]
    assert result["candidates"][0]["datasets"][0]["eligibility"] == "ELIGIBLE"
    assert result["candidates"][0]["task_eligibility"] == "UNVERIFIED"


def test_correctness_failure_is_contract_wide_even_outside_policy_required_subset():
    request, evidence, policy = fixture()
    case(evidence, dataset=1).update(correct=False, validation_status="failed", error="expected output mismatch")
    result = decide(request, evidence, policy, required_dataset_ids=["small"])
    assert result["candidates"][0]["correctness"] == "FAIL"
    assert all(d["eligibility"] == "INELIGIBLE" for d in result["candidates"][0]["datasets"])
    assert all(c["winner"] is None for c in result["dataset_comparisons"])
    assert result["dataset_comparisons"][0]["status"] == "ELIGIBILITY_ONLY"


def test_scope_and_preferential_failures():
    request, evidence, policy = fixture()
    c = constraint(dataset_ids=["large"], threshold=0.5)
    result = decide(request, evidence, policy, constraints=[c])
    assert [d["eligibility"] for d in result["candidates"][0]["datasets"]] == ["ELIGIBLE", "INELIGIBLE"]
    assert result["candidates"][0]["task_eligibility"] == "INELIGIBLE"
    assert [c["status"] for c in checks(result)] == ["NOT_APPLICABLE", "FAIL"]
    result = decide(request, evidence, policy, required_dataset_ids=["small"], constraints=[c])
    assert result["candidates"][0]["task_eligibility"] == "ELIGIBLE"
    result = decide(request, evidence, policy, constraints=[{**c, "classification": "PREFERENTIAL"}])
    assert result["candidates"][0]["task_eligibility"] == "ELIGIBLE"
    assert result["dataset_comparisons"][1]["winner"] == "a"


def test_cumulative_upper_bounds_do_not_conflict_and_keep_sources():
    request, evidence, policy = fixture()
    result = decide(request, evidence, policy, constraints=[constraint(id="one", threshold=3.0), constraint(id="two", threshold=0.5)])
    statuses = {c["constraint_id"]: c["status"] for c in result["candidates"][0]["constraint_evaluations"]}
    assert statuses == {"one": "PASS", "two": "FAIL"}
    assert result["task_suitability"]["status"] == "NO_ELIGIBLE_IMPLEMENTATION"


@pytest.mark.parametrize("conflict", [{"applicability": "UNRESOLVED"}, {"unresolved_override_of": "other"}])
def test_explicit_unresolved_relationships_are_conflicts(conflict):
    request, evidence, policy = fixture()
    result = decide(request, evidence, policy, constraints=[constraint(**conflict), constraint(id="other", threshold=3.0)])
    assert result["task_suitability"]["status"] == "REQUIREMENT_CONFLICT"
    assert checks(result)[0]["conflict"] is True
    assert result["dataset_comparisons"][0]["winner"] is None


@pytest.mark.parametrize("field,value", [("approved", True), ("provenance", {"authority": "CEO"}), ("type", "CUSTOM_EXPRESSION")])
def test_forged_authority_and_unsupported_constraint_types_are_rejected(field, value):
    _, _, policy = fixture()
    with pytest.raises(ValidationError):
        DecisionPolicy.model_validate({**policy, "constraints": [constraint(**{field: value})]})


@pytest.mark.parametrize("samples,status", [([1, 1, 1.05], "MULTIPLE_ELIGIBLE"), ([1, 1, 2], "MULTIPLE_ELIGIBLE")])
def test_unstable_timings_are_inconclusive(samples, status):
    request, evidence, policy = fixture()
    case(evidence)["timings_seconds"] = samples
    # First case remains stable for 1.05 spread; put medians within 5% for that case.
    if samples[-1] == 1.05:
        case(evidence, 1)["timings_seconds"] = [1.05] * 3
    assert decide(request, evidence, policy)["dataset_comparisons"][0]["status"] == status


@pytest.mark.parametrize("other,expected", [(1.0499, None), (1.05, None), (1.0501, "a")])
def test_practical_difference_boundary(other, expected):
    request, evidence, policy = fixture()
    case(evidence, 1)["timings_seconds"] = [other] * 3
    assert decide(request, evidence, policy)["dataset_comparisons"][0]["winner"] == expected


@pytest.mark.parametrize("maximum,expected", [(0.19, None), (0.20, "a"), (0.21, "a")])
def test_variability_boundary(maximum, expected):
    request, evidence, policy = fixture()
    case(evidence)["timings_seconds"] = [0.9, 1, 1.1]
    result = decide(request, evidence, policy, timing={"maximum_variability_ratio": maximum})
    assert result["dataset_comparisons"][0]["winner"] == expected


def test_different_datasets_can_favor_different_candidates():
    request, evidence, policy = fixture()
    case(evidence, 0, 1)["timings_seconds"] = [3] * 3
    result = decide(request, evidence, policy)
    assert [c["winner"] for c in result["dataset_comparisons"]] == ["a", "b"]


def test_no_policy_objective_means_tradeoffs_not_legacy_request_time_objective():
    request, evidence, _ = fixture()
    result = evaluate_decision(request, evidence, {"id": "no-objective", "version": "1"})
    assert all(d["winner"] is None and d["objective"] == "TRADEOFF_ONLY" for d in result["dataset_comparisons"])
    assert request["objective"] == "time"


@pytest.mark.parametrize("unverified,expected", [(False, "NO_ELIGIBLE_IMPLEMENTATION"), (True, "INSUFFICIENT_EVIDENCE")])
def test_all_fail_and_fail_plus_unverified_are_distinct(unverified, expected):
    request, evidence, policy = fixture()
    for i in range(2):
        case(evidence, i).update(correct=False, validation_status="failed", error="mismatch")
    if unverified:
        evidence["results"][1]["cases"] = []
    result = decide(request, evidence, policy)
    assert result["task_suitability"]["status"] == expected
    assert result["dataset_comparisons"][0]["status"] == expected


@pytest.mark.parametrize("change", ["runtime", "missing", "images"])
def test_incompatible_or_absent_methodology_never_compares(change):
    request, evidence, policy = fixture()
    if change == "runtime":
        evidence["environment"]["workers"][1]["runtime"] = "other"
    elif change == "missing":
        del evidence["environment"]["workers"]
    else:
        del evidence["environment"]["images"]
    assert decide(request, evidence, policy)["dataset_comparisons"][0]["status"] == "INCOMPARABLE_IMPLEMENTATIONS"


def test_versioned_fingerprints_preserve_types_order_and_validation_not_labels():
    request, evidence, policy = fixture()
    a = identities(request, evidence)
    changed = copy.deepcopy(request)
    changed["datasets"][0]["id"] = "different-label"
    assert identities(changed, evidence)["datasets"]["different-label"] == a["datasets"]["small"]
    changed["datasets"][0]["args"].reverse()
    assert identities(changed, evidence)["datasets"]["different-label"]["inputs"] != a["datasets"]["small"]["inputs"]
    assert len({fingerprint(v) for v in (1, 1.0, True, "1")}) == 4
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})
    other = decide(request, evidence, policy, constraints=[constraint(threshold=0.1)])
    first = decide(request, evidence, policy)
    assert other["identities"] == first["identities"]
    assert other["policy_fingerprint"] != first["policy_fingerprint"]


@pytest.mark.parametrize("mutation", [
    {"timing_status": "UNAVAILABLE"}, {"timing_status": "INVALID", "timing_error": "bad"},
    {"timings_seconds": [1]}, {"timings_seconds": [0, 0, 0]}, {"timing_status": "AVAILABLE", "timing_error": "bad"},
    {"memory_status": "UNAVAILABLE"}, {"memory_status": "UNAVAILABLE", "memory_error": "bad"},
    {"memory_status": "INVALID", "memory_error": "bad", "memory_bytes": 10},
    {"memory_bytes": -1}, {"memory_status": "AVAILABLE", "memory_error": "bad"},
    {"timings_seconds": [True, 1, 1]}, {"timings_seconds": [float("nan")] * 3},
])
def test_malformed_worker_protocol_is_rejected(mutation):
    request, evidence, policy = fixture()
    request["decision_policy"] = policy
    case(evidence).update(mutation)
    message = {"environment": {}, "tools": {}, "result": evidence["results"][0]}
    with pytest.raises(BenchmarkFailure, match="Malformed"):
        DockerBenchmarkRunner._parse(json.dumps(message), request, request["candidates"][0])


@pytest.mark.parametrize("kind", ["memory", "timing"])
def test_legitimate_optional_unavailability_passes_protocol(kind):
    request, evidence, policy = fixture()
    request["decision_policy"] = policy
    unavailable(case(evidence), kind)
    message = {"environment": {}, "tools": {}, "result": evidence["results"][0]}
    assert DockerBenchmarkRunner._parse(json.dumps(message), request, request["candidates"][0]) == message


def test_zero_invalid_incomplete_and_minimum_sample_handling():
    request, evidence, policy = fixture()
    for values in ([0, 0, 0], [1, 1]):
        case(evidence).update(timings_seconds=values, timing_status="INVALID", timing_error="invalid/incomplete")
        result = decide(request, evidence, policy, constraints=[constraint()])
        assert checks(result)[0]["status"] == "UNVERIFIED"
    request["repetitions"] = 2
    for row in evidence["results"]:
        for c in row["cases"]:
            c.update(timings_seconds=[1, 1], timing_status="AVAILABLE", timing_error=None)
    assert decide(request, evidence, policy)["dataset_comparisons"][0]["status"] == "INSUFFICIENT_EVIDENCE"


def test_historical_missing_measurements_are_not_upgraded_to_pass():
    request, evidence, policy = fixture()
    for row in evidence["results"]:
        for c in row["cases"]:
            for k in ("measurement_version", "timing_status", "timing_error", "memory_status", "memory_error"):
                c.pop(k)
    assert decide(request, evidence, policy)["dataset_comparisons"][0]["winner"] == "a"
    case(evidence)["memory_bytes"] = None
    assert checks(decide(request, evidence, policy, constraints=[constraint("MAX_MEMORY")]))[0]["status"] == "UNVERIFIED"


def test_conflict_and_correctness_failure_remain_independent_findings():
    request, evidence, policy = fixture()
    for result in evidence["results"]:
        result["cases"][0].update(correct=False, validation_status="failed", error="wrong expected value")
    result = decide(request, evidence, policy, constraints=[constraint(applicability="UNRESOLVED")])
    assert result["task_suitability"]["status"] == "REQUIREMENT_CONFLICT"
    assert result["candidates"][0]["task_eligibility"] == "INELIGIBLE"
    assert result["candidates"][0]["correctness"] == "FAIL"
    assert result["candidates"][0]["requirement_conflict"] is True


def test_even_sample_median_is_finite_at_large_valid_values():
    request, evidence, policy = fixture()
    request["repetitions"] = 2
    for row in evidence["results"]:
        for c in row["cases"]:
            c["timings_seconds"] = [1e308, 1e308]
    result = decide(request, evidence, policy, timing={"minimum_samples": 2})
    assert result["candidates"][0]["datasets"][0]["timing"]["median"] == 1e308
    json.dumps(result, allow_nan=False)


def test_new_protocol_cannot_be_silently_downgraded():
    request, evidence, policy = fixture()
    request["decision_policy"] = policy
    for c in evidence["results"][0]["cases"]:
        del c["measurement_version"]
    message = {"environment": {}, "tools": {}, "result": evidence["results"][0]}
    with pytest.raises(BenchmarkFailure):
        DockerBenchmarkRunner._parse(json.dumps(message), request, request["candidates"][0])


def test_correctness_without_expected_values_remains_unverified():
    request, evidence, policy = fixture()
    request["contract"]["correctness"] = "none"
    for d in request["datasets"]:
        del d["expected"]
    result = decide(request, evidence, policy, constraints=[constraint("EXPECTED_OUTPUT")])
    assert checks(result)[0]["status"] == "UNVERIFIED"
    assert result["candidates"][0]["task_eligibility"] == "UNVERIFIED"
    assert all(c["winner"] is None for c in result["dataset_comparisons"])


def test_one_eligible_candidate_never_implies_multiple_eligible_or_comparative_superiority():
    request, evidence, policy = fixture()
    request["candidates"].pop()
    evidence["results"].pop()
    result = decide(request, evidence, policy)
    assert result["task_suitability"]["status"] == "ELIGIBILITY_ONLY"
    assert result["task_suitability"]["eligible_candidates"] == ["a"]
    assert result["task_suitability"]["global_winner"] is None
    assert all(c["status"] == "ELIGIBILITY_ONLY" and c["winner"] is None for c in result["dataset_comparisons"])
