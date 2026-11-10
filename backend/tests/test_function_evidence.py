"""Synthetic generic-function evidence: no workers, candidate execution or services."""

import copy
import json
import math
import socket
import subprocess
import sys

import pytest

from benchmark_worker.contracts import validate_function_payload
from intelligence.algorithms.evidence import recommend


PYTHON_MEMORY = "memray_peak_tracked_allocations_bytes"
NODE_MEMORY = "node_heap_used_delta_bytes"


def fixture(language="python", correctness="expected", objective="time"):
    payload = {
        "language": language, "objective": objective, "repetitions": 3,
        "candidates": [
            {"name": name, "entrypoint": "constellation_fold",
             "source": "raise AssertionError('candidate must never execute')"}
            for name in ("aurora", "nebula")
        ],
        "contract": {
            "kind": "function", "name": "new.constellation.fold", "version": "unpublished-1",
            "input_schema": {"type": "array", "items": {"type": "string"}},
            "output_schema": {"type": "string"}, "correctness": correctness,
            "mutation": "forbidden",
        },
        "datasets": [
            {"id": "sparse-sky", "args": ["alpha", "beta"],
             "dimensions": {"stars": 2, "bands": 9}},
            # Equal dimensions do not collapse distinct dataset identities.
            {"id": "dense-sky", "args": ["gamma", "delta"],
             "dimensions": {"stars": 2, "bands": 9}},
            {"id": "empty-sky", "args": []},
        ],
    }
    if correctness == "expected":
        for dataset in payload["datasets"]:
            dataset["expected"] = ":".join(dataset["args"])
    benchmark = {"error": None, "environment": {"runtime": "synthetic"}, "tools": {}, "results": [
        {"candidate": name, "error": None, "cases": [
            {"case_id": dataset["id"], "dimensions": copy.deepcopy(dataset.get("dimensions", {})),
             "correct": True if correctness == "expected" else None,
             "validation_status": "verified" if correctness == "expected" else "unverified",
             "timings_seconds": [seconds] * 3, "memory_bytes": memory,
             "memory_metric": PYTHON_MEMORY if language == "python" else NODE_MEMORY, "error": None}
            for dataset in payload["datasets"]]}
        for name, seconds, memory in [("aurora", 1.0, 200), ("nebula", 2.0, 100)]
    ]}
    return payload, benchmark


def row(response, name="aurora"):
    return next(item for item in response["rankings"] if item["candidate"] == name)


def assert_insufficient(response):
    assert response["status"] == "insufficient_evidence"
    assert response["winner"] is None
    assert response["reason"]
    json.dumps(response, allow_nan=False)


def assert_invalid(response, name="aurora"):
    result = row(response, name)
    assert result["eligible"] is False
    assert result["median_seconds"] is None
    assert result["timing_score_seconds"] is None
    assert result["peak_memory_bytes"] is None
    assert result["reason"]
    json.dumps(response, allow_nan=False)


def test_completely_new_function_ranks_without_sorting_fields_and_is_pure():
    payload, benchmark = fixture()
    before = copy.deepcopy((payload, benchmark))
    response = recommend(payload, benchmark)
    assert response["status"] == "recommended"
    assert response["winner"] == "aurora"
    assert row(response)["eligible"]
    assert row(response)["median_seconds"] == 1
    assert row(response)["timing_score_seconds"] == 1
    assert row(response)["peak_memory_bytes"] == 200
    assert set(response) == {"status", "winner", "reason", "rankings", "limitations"}
    assert (payload, benchmark) == before
    json.dumps(response, allow_nan=False)


def test_public_recommend_performs_no_io_or_execution(monkeypatch):
    payload, benchmark = fixture()

    def forbidden(*args, **kwargs):
        raise AssertionError("ranking must inspect data only")

    with monkeypatch.context() as patch:
        for name in ("open", "exec", "eval", "compile"):
            patch.setattr("builtins." + name, forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        patch.setattr(socket, "socket", forbidden)
        response = recommend(payload, benchmark)
    assert response["winner"] == "aurora"


@pytest.mark.parametrize("forged", [False, True])
@pytest.mark.parametrize("language", ["python", "javascript"])
def test_none_has_no_oracle_even_if_worker_forges_verified_correctness(forged, language):
    payload, benchmark = fixture(language=language, correctness="none")
    if forged:
        for result in benchmark["results"]:
            for case in result["cases"]:
                case.update(correct=True, validation_status="verified")
    before = copy.deepcopy((payload, benchmark))
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "no correctness oracle" in response["reason"].lower()
    for name in ("aurora", "nebula"):
        assert_invalid(response, name)
        assert "no correctness oracle" in row(response, name)["reason"].lower()
    # Services retain the original results, not the ranking summaries. Unverified
    # measurements must remain available for persistence and raw-evidence display.
    assert (payload, benchmark) == before
    assert benchmark["results"][0]["cases"][0]["timings_seconds"] == [1, 1, 1]
    assert benchmark["results"][0]["cases"][0]["memory_bytes"] == 200


def test_single_generic_candidate_is_eligible_baseline_not_comparison_winner():
    payload, benchmark = fixture()
    payload["candidates"].pop()
    benchmark["results"].pop()
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert row(response)["eligible"]
    assert row(response)["timing_score_seconds"] == 1
    assert "two requested candidates" in response["reason"]


def test_equal_weight_geometric_mean_of_case_medians_not_display_median():
    payload, benchmark = fixture()
    for case, timing in zip(benchmark["results"][0]["cases"], [1, 1, 1000]):
        case["timings_seconds"] = [timing, timing, sys.float_info.max]
    for case in benchmark["results"][1]["cases"]:
        case["timings_seconds"] = [20, 20, 20]
    benchmark["results"].reverse()
    for result in benchmark["results"]:
        result["cases"].reverse()
    response = recommend(payload, benchmark)
    assert response["winner"] == "aurora"
    assert row(response)["timing_score_seconds"] == pytest.approx(10)
    assert row(response)["median_seconds"] == 1


@pytest.mark.parametrize("second", [1, 1.001, 1.04, 1.05, 1.05001])
def test_generic_uses_same_five_percent_margin(second):
    payload, benchmark = fixture()
    for case in benchmark["results"][1]["cases"]:
        case["timings_seconds"] = [second] * 3
    response = recommend(payload, benchmark)
    assert all(item["eligible"] for item in response["rankings"])
    if second <= 1.05:
        assert_insufficient(response)
        assert "5%" in response["reason"]
    else:
        assert response["winner"] == "aurora"


@pytest.mark.parametrize("field,value", [
    ("correct", False), ("correct", None), ("correct", 1), ("correct", "true"),
    ("validation_status", "unverified"), ("validation_status", "failed"),
    ("validation_status", None), ("validation_status", True),
    ("validation_status", "Verified"), ("validation_status", []),
])
def test_only_literal_correct_true_and_verified_are_eligible(field, value):
    payload, benchmark = fixture()
    benchmark["results"][0]["cases"][0][field] = value
    response = recommend(payload, benchmark)
    assert_invalid(response)
    assert response["winner"] == "nebula"
    assert "No speed comparison" in response["reason"]


@pytest.mark.parametrize("field", ["correct", "validation_status", "error", "case_id", "dimensions",
                                  "timings_seconds", "memory_bytes", "memory_metric"])
def test_missing_required_case_evidence(field):
    payload, benchmark = fixture()
    del benchmark["results"][0]["cases"][0][field]
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("target", ["candidate", "case"])
@pytest.mark.parametrize("error", ["timeout", "", False, 0, "missing"])
def test_errors_and_missing_error_status_invalidate_candidate(target, error):
    payload, benchmark = fixture()
    target = benchmark["results"][0] if target == "candidate" else benchmark["results"][0]["cases"][0]
    if error == "missing":
        del target["error"]
    else:
        target["error"] = error
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "unexpected_id", "bad_id",
                                      "wrong_dimensions", "extra_dimension", "missing_dimension",
                                      "bool_dimension", "float_dimension", "bad_dimensions", "sorting_case",
                                      "malformed"])
def test_exact_dataset_ids_and_dimensions_required(mutation):
    payload, benchmark = fixture()
    cases = benchmark["results"][0]["cases"]
    if mutation == "missing":
        cases.pop()
    elif mutation == "extra":
        cases.append(copy.deepcopy(cases[0]))
    elif mutation == "duplicate":
        cases[1] = copy.deepcopy(cases[0])
    elif mutation == "unexpected_id":
        cases[0]["case_id"] = "unrequested-sky"
    elif mutation == "bad_id":
        cases[0]["case_id"] = []
    elif mutation == "wrong_dimensions":
        cases[0]["dimensions"]["stars"] = 3
    elif mutation == "extra_dimension":
        cases[0]["dimensions"]["size"] = 2
    elif mutation == "missing_dimension":
        del cases[0]["dimensions"]["stars"]
    elif mutation == "bool_dimension":
        cases[0]["dimensions"]["stars"] = True
        payload["datasets"][0]["dimensions"]["stars"] = 1
    elif mutation == "float_dimension":
        cases[0]["dimensions"]["stars"] = 2.0
    elif mutation == "bad_dimensions":
        cases[0]["dimensions"] = []
    elif mutation == "sorting_case":
        cases[0].update(size=2, distribution="random")
        del cases[0]["case_id"]
    else:
        cases[0] = None
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("samples", [[], [1], [1, 1, 1, 1], None, "111"])
def test_exact_sample_count_required_and_extra_duplicate_samples_rejected(samples):
    payload, benchmark = fixture()
    benchmark["results"][0]["cases"][0]["timings_seconds"] = samples
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf, -math.inf, True, "1", None, 10**1000])
def test_every_timing_sample_must_be_positive_finite(value):
    payload, benchmark = fixture()
    benchmark["results"][0]["cases"][-1]["timings_seconds"][1] = value
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("language", ["python", "javascript", "typescript", "js", "ts"])
@pytest.mark.parametrize("field,value", [
    ("memory_metric", "rss"), ("memory_metric", None), ("memory_bytes", None),
    ("memory_bytes", True), ("memory_bytes", 1.5), ("memory_bytes", math.nan),
    ("memory_bytes", math.inf), ("memory_bytes", 2**63),
    ("memory_bytes", -(2**63) - 1), ("memory_bytes", 10**1000),
])
def test_runtime_memory_metric_and_storable_integer_required(language, field, value):
    payload, benchmark = fixture(language=language)
    benchmark["results"][0]["cases"][0][field] = value
    assert_invalid(recommend(payload, benchmark))


def test_python_negative_memory_rejected_but_zero_valid():
    payload, benchmark = fixture()
    case = benchmark["results"][0]["cases"][0]
    case["memory_bytes"] = -1
    assert_invalid(recommend(payload, benchmark))
    case["memory_bytes"] = 0
    assert row(recommend(payload, benchmark))["eligible"]


@pytest.mark.parametrize("limit,winner", [(None, "nebula"), (100, "nebula"), (99, None)])
def test_python_memory_ranks_peak_and_applies_inclusive_limit(limit, winner):
    payload, benchmark = fixture(objective="memory")
    payload["memory_limit_bytes"] = limit
    response = recommend(payload, benchmark)
    assert response["winner"] == winner
    assert row(response)["peak_memory_bytes"] == 200
    assert row(response, "nebula")["peak_memory_bytes"] == 100
    if winner is None:
        assert_insufficient(response)


def test_memory_objective_uses_maximum_and_no_timing_tiebreak():
    payload, benchmark = fixture(objective="memory")
    benchmark["results"][1]["cases"][0]["memory_bytes"] = 300
    assert recommend(payload, benchmark)["winner"] == "aurora"
    benchmark["results"][1]["cases"][0]["memory_bytes"] = 200
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(item["eligible"] for item in response["rankings"])


@pytest.mark.parametrize("language", ["javascript", "typescript", "js", "ts"])
def test_node_signed_delta_supports_time_only_and_never_claims_peak(language):
    payload, benchmark = fixture(language=language)
    benchmark["results"][0]["cases"][0]["memory_bytes"] = -100
    response = recommend(payload, benchmark)
    assert response["winner"] == "aurora"
    assert all(item["peak_memory_bytes"] is None for item in response["rankings"])
    for objective, limit in [("memory", None), ("time", 1000), ("memory", 1000)]:
        payload.update(objective=objective, memory_limit_bytes=limit)
        response = recommend(payload, benchmark)
        assert_insufficient(response)
        assert "not peak memory" in response["reason"]
        assert all(not item["eligible"] for item in response["rankings"])


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "missing_cases", "bad_cases"])
def test_candidate_result_integrity(mutation):
    payload, benchmark = fixture()
    if mutation == "duplicate":
        benchmark["results"].append(copy.deepcopy(benchmark["results"][0]))
    elif mutation == "missing":
        benchmark["results"].pop(0)
    elif mutation == "missing_cases":
        del benchmark["results"][0]["cases"]
    else:
        benchmark["results"][0]["cases"] = {}
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("benchmark", [None, [], {}, {"results": None}, {"results": [None]},
    {"results": [{"candidate": "unknown"}]}, {"results": [{"candidate": []}]},
    {"results": [], "error": "failed"}])
def test_malformed_benchmark_cannot_produce_winner(benchmark):
    payload, _ = fixture()
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(not item["eligible"] for item in response["rankings"])


@pytest.mark.parametrize("mutation", ["contract", "kind", "schema", "args", "expected", "duplicate_ids",
                                      "datasets", "dimensions", "resources", "none_with_expected"])
def test_invalid_or_incompatible_generic_request_is_insufficient(mutation):
    payload, benchmark = fixture()
    if mutation == "contract":
        payload["contract"] = False  # Non-null must not fall back to sorting.
    elif mutation == "kind":
        payload["contract"]["kind"] = "sort"
    elif mutation == "schema":
        payload["contract"]["input_schema"] = {"type": "object"}
    elif mutation == "args":
        payload["datasets"][0]["args"] = [1]
    elif mutation == "expected":
        del payload["datasets"][0]["expected"]
    elif mutation == "duplicate_ids":
        payload["datasets"][1]["id"] = payload["datasets"][0]["id"]
    elif mutation == "datasets":
        payload["datasets"] = []
    elif mutation == "dimensions":
        payload["datasets"][0]["dimensions"] = {"stars": True}
    elif mutation == "resources":
        payload["resources"] = {"cpus": 2}
    else:
        payload["contract"]["correctness"] = "none"
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "Invalid request" in response["reason"]


@pytest.mark.parametrize("field,value", [("language", "rust"), ("language", []),
    ("candidates", []), ("candidates", [{"name": "x"}, {"name": "x"}]),
    ("repetitions", True), ("repetitions", 0), ("objective", "energy"),
    ("objective", []), ("memory_limit_bytes", True), ("memory_limit_bytes", -1)])
def test_common_request_checks_still_apply(field, value):
    payload, benchmark = fixture()
    payload[field] = value
    assert_insufficient(recommend(payload, benchmark))


@pytest.mark.parametrize("contract", [False, True, 0, 1, "", "function", [], ["function"], {}, ()])
def test_malformed_contract_types_raise_value_error_and_cannot_rank(contract):
    payload, benchmark = fixture()
    payload["contract"] = contract
    with pytest.raises(ValueError):
        validate_function_payload(payload)
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "Invalid request" in response["reason"]
    assert response["rankings"] == []


@pytest.mark.parametrize("field", ["kind", "name", "version", "correctness", "mutation", "output"])
@pytest.mark.parametrize("value", [None, False, 1, [], {}])
def test_malformed_contract_field_types_do_not_escape_request_validation(field, value):
    payload, benchmark = fixture()
    payload["contract"][field] = value
    with pytest.raises(ValueError):
        validate_function_payload(payload)
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "Invalid request" in response["reason"]
    assert response["rankings"] == []


@pytest.mark.parametrize("field", ["input_schema", "output_schema"])
@pytest.mark.parametrize("schema", [
    None, False, 0, "array", [], {"type": []}, {"type": {}}, {"type": True},
    {"type": "object", "required": [[]]}, {"type": "array", "items": []},
    {"type": "object", "properties": []}, {"type": "string", "enum": {}},
])
def test_malformed_schemas_raise_value_error_not_type_or_attribute_errors(field, schema):
    payload, benchmark = fixture()
    payload["contract"][field] = schema
    with pytest.raises(ValueError):
        validate_function_payload(payload)
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "Invalid request" in response["reason"]
    assert response["rankings"] == []


@pytest.mark.parametrize("field", ["input_schema", "output_schema"])
@pytest.mark.parametrize("depth", [33, 2000])
def test_deeply_nested_schema_is_bounded_before_recursive_validation(field, depth):
    payload, benchmark = fixture()
    schema = {"type": "string"}
    for _ in range(depth):
        schema = {"type": "array", "items": schema}
    payload["contract"][field] = schema
    with pytest.raises(ValueError, match="depth 32"):
        validate_function_payload(payload)
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "depth 32" in response["reason"]
    assert response["rankings"] == []


@pytest.mark.parametrize("cyclic", [False, True])
def test_deep_or_cyclic_dataset_input_cannot_escape_as_recursion_error(cyclic):
    payload, benchmark = fixture()
    args = []
    if cyclic:
        args.append(args)
    else:
        for _ in range(2000):
            args = [args]
    payload["datasets"][0]["args"] = args
    with pytest.raises(ValueError, match="depth 32"):
        validate_function_payload(payload)
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "depth 32" in response["reason"]
    assert response["rankings"] == []


def test_generic_ignores_legacy_grid_even_when_present():
    payload, benchmark = fixture()
    payload.update(sizes=[True, True], distributions=[[]])
    assert recommend(payload, benchmark)["winner"] == "aurora"


@pytest.mark.parametrize("timing", [sys.float_info.max, math.ulp(0.0)])
@pytest.mark.parametrize("case_count", [1, 11, 32])
def test_float_extremes_keep_finite_scores_and_json_safe_response(timing, case_count):
    payload, benchmark = fixture()
    template = payload["datasets"][0]
    payload["datasets"] = [{**template, "id": str(i)} for i in range(case_count)]
    payload["repetitions"] = 2
    for result in benchmark["results"]:
        case = result["cases"][0]
        result["cases"] = [{**case, "case_id": str(i), "timings_seconds": [timing, timing]}
                           for i in range(case_count)]
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(item["eligible"] and math.isfinite(item["timing_score_seconds"])
               and item["median_seconds"] == timing for item in response["rankings"])


def test_generic_limitations_do_not_make_sorting_or_universal_claims():
    payload, benchmark = fixture()
    text = " ".join(recommend(payload, benchmark)["limitations"])
    for phrase in ("supplied cases", "semantic contract identity", "equivalence", "caller-defined",
                   "No Big-O", "optimality", "stability", "not a statistical significance test"):
        assert phrase in text
    for phrase in ("sorting", "numeric ascending", "custom comparator", "distributions"):
        assert phrase not in text
