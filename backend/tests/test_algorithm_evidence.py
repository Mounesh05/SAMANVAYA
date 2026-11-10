"""Synthetic evidence only: no candidate execution, Docker or memory profilers."""

import copy
import json
import math
import sys

import pytest

from intelligence.algorithms.evidence import recommend


PYTHON_MEMORY = "memray_peak_tracked_allocations_bytes"
NODE_MEMORY = "node_heap_used_delta_bytes"


def fixture(language="python", objective="time"):
    payload = {"language": language, "objective": objective,
               "candidates": [{"name": name, "source": "never execute me", "entrypoint": "sort"}
                              for name in ("fast", "slow")],
               "sizes": [0, 100], "distributions": ["random", "duplicates"], "repetitions": 3}
    benchmark = {"environment": {"runtime": "synthetic"}, "tools": {}, "results": [
        {"candidate": name, "error": None, "cases": [
            {"size": size, "distribution": distribution, "correct": True,
             "timings_seconds": [seconds] * 3, "memory_bytes": memory,
             "memory_metric": PYTHON_MEMORY if language == "python" else NODE_MEMORY, "error": None}
            for size in payload["sizes"] for distribution in payload["distributions"]]}
        for name, seconds, memory in [("fast", 1.0, 200), ("slow", 2.0, 100)]]}
    return payload, benchmark


def row(response, name):
    return next(r for r in response["rankings"] if r["candidate"] == name)


def assert_insufficient(response):
    assert response["status"] == "insufficient_evidence"
    assert response["winner"] is None
    assert response["reason"]


def assert_invalid(response, name="fast"):
    result = row(response, name)
    assert result["eligible"] is False
    assert result["median_seconds"] is None
    assert result["timing_score_seconds"] is None
    assert result["peak_memory_bytes"] is None
    assert result["reason"]


def test_time_winner_schema_and_no_mutation():
    payload, benchmark = fixture()
    before = copy.deepcopy((payload, benchmark))
    response = recommend(payload, benchmark)
    assert response["status"] == "recommended"
    assert response["winner"] == "fast"
    assert set(response) == {"status", "winner", "reason", "rankings", "limitations"}
    assert row(response, "fast")["median_seconds"] == 1.0
    assert row(response, "fast")["timing_score_seconds"] == 1.0
    assert row(response, "fast")["peak_memory_bytes"] == 200
    assert all(isinstance(x, str) for x in response["limitations"])
    assert (payload, benchmark) == before
    json.dumps(response, allow_nan=False)


def test_equal_weight_geometric_ranking_not_ui_median_or_largest_case():
    payload, benchmark = fixture()
    for case, timing in zip(benchmark["results"][0]["cases"], [1, 1, 100, 100]):
        case["timings_seconds"] = [timing] * 3
    for case in benchmark["results"][1]["cases"]:
        case["timings_seconds"] = [20, 20, 20]
    response = recommend(payload, benchmark)
    assert response["winner"] == "fast"
    assert row(response, "fast")["timing_score_seconds"] == pytest.approx(10)
    assert row(response, "fast")["median_seconds"] == 50.5
    assert row(response, "slow")["median_seconds"] == 20


def test_per_case_medians_resist_outliers_and_grid_order_is_irrelevant():
    payload, benchmark = fixture()
    for case in benchmark["results"][0]["cases"]:
        case["timings_seconds"] = [10000, 1, 1]
    benchmark["results"].reverse()
    for result in benchmark["results"]:
        result["cases"].reverse()
    assert recommend(payload, benchmark)["winner"] == "fast"


@pytest.mark.parametrize("correct", [False, None, 1, "true"])
def test_incorrect_fastest_never_wins_and_only_valid_has_no_speed_claim(correct):
    payload, benchmark = fixture()
    benchmark["results"][0]["cases"][0]["correct"] = correct
    response = recommend(payload, benchmark)
    assert_invalid(response)
    assert response["winner"] == "slow"
    assert "No speed comparison" in response["reason"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "unexpected", "malformed",
                                      "missing_size", "bool_size", "bad_distribution"])
def test_exact_case_grid_required(mutation):
    payload, benchmark = fixture()
    cases = benchmark["results"][0]["cases"]
    if mutation == "missing":
        cases.pop()
    elif mutation == "duplicate":
        cases[-1] = copy.deepcopy(cases[0])
    elif mutation == "extra":
        cases.append(copy.deepcopy(cases[0]))
    elif mutation == "unexpected":
        cases[0]["size"] = 999
    elif mutation == "malformed":
        cases[0] = None
    elif mutation == "missing_size":
        del cases[0]["size"]
    elif mutation == "bool_size":
        cases[0]["size"] = False
    else:
        cases[0]["distribution"] = []
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), -float("inf"), True, "1", None, 10**1000])
def test_unreliable_timing_sample_rejects_entire_candidate(value):
    payload, benchmark = fixture()
    benchmark["results"][0]["cases"][-1]["timings_seconds"][1] = value
    response = recommend(payload, benchmark)
    assert_invalid(response)
    json.dumps(response, allow_nan=False)


@pytest.mark.parametrize("samples", [[], [1], [1, 1, 1, 1], None, "111"])
def test_exact_repetition_count(samples):
    payload, benchmark = fixture()
    benchmark["results"][0]["cases"][0]["timings_seconds"] = samples
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("target", ["candidate", "case"])
@pytest.mark.parametrize("error", ["timeout", "", False, 0, "missing"])
def test_any_error_or_missing_error_status_rejects(target, error):
    payload, benchmark = fixture()
    result = benchmark["results"][0]
    target = result if target == "candidate" else result["cases"][0]
    if error == "missing":
        del target["error"]
    else:
        target["error"] = error
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "missing_cases", "bad_cases"])
def test_candidate_result_integrity(mutation):
    payload, benchmark = fixture()
    if mutation == "missing":
        benchmark["results"].pop(0)
    elif mutation == "duplicate":
        benchmark["results"].append(copy.deepcopy(benchmark["results"][0]))
    elif mutation == "missing_cases":
        del benchmark["results"][0]["cases"]
    else:
        benchmark["results"][0]["cases"] = {}
    response = recommend(payload, benchmark)
    assert_invalid(response)
    assert response["winner"] == "slow"


@pytest.mark.parametrize("bad", [None, [], {}, {"results": None}, {"results": [None]},
                                  {"results": [{"candidate": "unknown"}]},
                                  {"results": [{"candidate": []}]}, {"results": [], "error": "failed"}])
def test_malformed_benchmark_is_insufficient(bad):
    payload, _ = fixture()
    response = recommend(payload, bad)
    assert_insufficient(response)
    assert all(not r["eligible"] for r in response["rankings"])


def test_all_failures_no_fabricated_measurements():
    payload, benchmark = fixture()
    for result in benchmark["results"]:
        result.update(cases=[], error="execution failed")
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert_invalid(response, "fast")
    assert_invalid(response, "slow")


def test_memory_objective_uses_maximum_tracked_allocation_not_timing():
    payload, benchmark = fixture(objective="memory")
    benchmark["results"][1]["cases"][0]["memory_bytes"] = 300
    response = recommend(payload, benchmark)
    assert response["winner"] == "fast"
    assert row(response, "slow")["peak_memory_bytes"] == 300
    assert "not RSS" in response["reason"]


def test_memory_winner_can_be_slower():
    payload, benchmark = fixture(objective="memory")
    response = recommend(payload, benchmark)
    assert response["winner"] == "slow"
    assert [r["candidate"] for r in response["rankings"]] == ["slow", "fast"]


@pytest.mark.parametrize("limit,winner", [(100, "slow"), (200, "fast"), (99, None)])
def test_python_memory_limit_is_inclusive_and_applies_to_time(limit, winner):
    payload, benchmark = fixture()
    payload["memory_limit_bytes"] = limit
    response = recommend(payload, benchmark)
    assert response["winner"] == winner
    assert row(response, "fast")["eligible"] is (limit >= 200)
    assert row(response, "fast")["peak_memory_bytes"] == 200
    if winner is None:
        assert_insufficient(response)
    assert "not RSS or total RAM" in " ".join(response["limitations"])


@pytest.mark.parametrize("field,value", [("memory_bytes", None), ("memory_bytes", -1),
                                         ("memory_bytes", 1.5), ("memory_bytes", True),
                                         ("memory_bytes", float("nan")), ("memory_bytes", float("inf")),
                                         ("memory_metric", "rss"), ("memory_metric", None)])
def test_invalid_python_memory_invalidates_even_time_evidence(field, value):
    payload, benchmark = fixture()
    benchmark["results"][0]["cases"][0][field] = value
    assert_invalid(recommend(payload, benchmark))


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
@pytest.mark.parametrize("memory", [2**63, -(2**63) - 1, 10**1000])
def test_unstorable_memory_measurements_never_rank(language, memory):
    payload, benchmark = fixture(language)
    benchmark["results"][0]["cases"][0]["memory_bytes"] = memory
    response = recommend(payload, benchmark)
    assert_invalid(response)
    assert response["winner"] == "slow"
    assert "No speed comparison" in response["reason"]
    json.dumps(response, allow_nan=False)


def test_historical_measurements_cannot_fill_missing_current_evidence():
    payload, benchmark = fixture()
    historical = copy.deepcopy(benchmark)
    benchmark["results"] = []
    benchmark["historical_evidence"] = [historical]
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(not result["eligible"] for result in response["rankings"])


def test_zero_tracked_allocations_are_valid_and_memory_ties_have_no_time_tiebreak():
    payload, benchmark = fixture(objective="memory")
    for result in benchmark["results"]:
        for case in result["cases"]:
            case["memory_bytes"] = 0
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(r["eligible"] and r["peak_memory_bytes"] == 0 for r in response["rankings"])
    assert "no strict memory advantage" in response["reason"]
    benchmark["results"][1]["cases"][0]["memory_bytes"] = 1
    assert recommend(payload, benchmark)["winner"] == "fast"


@pytest.mark.parametrize("language", ["javascript", "typescript", "js", "ts"])
def test_node_signed_retained_delta_is_not_reported_as_peak_but_time_is_supported(language):
    payload, benchmark = fixture(language)
    benchmark["results"][0]["cases"][0]["memory_bytes"] = -1000
    response = recommend(payload, benchmark)
    assert response["winner"] == "fast"
    assert all(r["peak_memory_bytes"] is None for r in response["rankings"])
    assert "signed retained heap delta" in " ".join(response["limitations"])


@pytest.mark.parametrize("language", ["javascript", "typescript"])
@pytest.mark.parametrize("objective,limit", [("memory", None), ("time", 1000), ("memory", 1000)])
def test_node_memory_objectives_and_limits_are_never_supported(language, objective, limit):
    payload, benchmark = fixture(language, objective)
    payload["memory_limit_bytes"] = limit
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert "not peak memory" in response["reason"]
    assert all(not r["eligible"] and r["peak_memory_bytes"] is None for r in response["rankings"])
    assert all(r["timing_score_seconds"] is not None for r in response["rankings"])


@pytest.mark.parametrize("second", [1.0, 1.001, 1.04, 1.05])
def test_timing_ties_and_near_ties_do_not_choose_arbitrarily(second):
    payload, benchmark = fixture()
    for case in benchmark["results"][1]["cases"]:
        case["timings_seconds"] = [second] * 3
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(r["eligible"] for r in response["rankings"])
    assert "5%" in response["reason"]


def test_just_above_threshold_recommends():
    payload, benchmark = fixture()
    for case in benchmark["results"][1]["cases"]:
        case["timings_seconds"] = [1.05001] * 3
    assert recommend(payload, benchmark)["winner"] == "fast"


def test_single_requested_candidate_does_not_establish_comparison():
    payload, benchmark = fixture()
    payload["candidates"].pop()
    benchmark["results"].pop()
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert row(response, "fast")["eligible"]


@pytest.mark.parametrize("key,value", [("language", []), ("language", "rust"), ("objective", []),
                                      ("objective", "energy"), ("sizes", [True]), ("sizes", [-1]),
                                      ("sizes", [1, 1]), ("sizes", []), ("distributions", [[]]),
                                      ("distributions", ["random", "random"]), ("distributions", []),
                                      ("repetitions", 0), ("repetitions", True), ("repetitions", 1.5),
                                      ("memory_limit_bytes", 0), ("memory_limit_bytes", -1),
                                      ("memory_limit_bytes", True), ("memory_limit_bytes", 1.5),
                                      ("candidates", []), ("candidates", [None]),
                                      ("candidates", [{"name": "x"}, {"name": "x"}])])
def test_malformed_request_is_insufficient_not_exception(key, value):
    payload, benchmark = fixture()
    payload[key] = value
    assert_insufficient(recommend(payload, benchmark))


def test_non_dictionary_payload():
    assert_insufficient(recommend(None, {}))


def test_default_objective_and_explicit_absent_limit():
    payload, benchmark = fixture()
    del payload["objective"]
    payload["memory_limit_bytes"] = None
    assert recommend(payload, benchmark)["winner"] == "fast"


@pytest.mark.parametrize("timing", [sys.float_info.max, math.ulp(0.0)])
def test_finite_positive_float_extremes_remain_json_safe(timing):
    payload, benchmark = fixture()
    payload["repetitions"] = 2
    for result in benchmark["results"]:
        for case in result["cases"]:
            case["timings_seconds"] = [timing, timing]
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(r["eligible"] for r in response["rankings"])
    assert all(r["median_seconds"] == timing for r in response["rankings"])
    json.dumps(response, allow_nan=False)


@pytest.mark.parametrize("timing", [sys.float_info.max, math.ulp(0.0)])
@pytest.mark.parametrize("case_count", [11, 44])
def test_geometric_mean_rounding_stays_within_finite_input_range(timing, case_count):
    payload, benchmark = fixture()
    payload["sizes"] = list(range(11))
    payload["distributions"] = ["random"] if case_count == 11 else ["random", "sorted", "reversed", "duplicates"]
    for result in benchmark["results"]:
        template = result["cases"][0]
        result["cases"] = [
            {**template, "size": size, "distribution": distribution, "timings_seconds": [timing] * 3}
            for size in payload["sizes"] for distribution in payload["distributions"]
        ]
    response = recommend(payload, benchmark)
    assert_insufficient(response)
    assert all(r["eligible"] and math.isfinite(r["timing_score_seconds"]) for r in response["rankings"])
    json.dumps(response, allow_nan=False)


def test_limitations_do_not_overstate_empirical_sorting_evidence():
    payload, benchmark = fixture()
    text = " ".join(recommend(payload, benchmark)["limitations"])
    for phrase in ("sampled", "no universal best", "numeric ascending", "stability",
                   "custom comparator", "No Big-O", "not a statistical significance test"):
        assert phrase in text
