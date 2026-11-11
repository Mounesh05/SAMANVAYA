"""Pure evidence ranking for sorting and declared function contracts; never execute code."""

import math

from benchmark_worker.contracts import is_generic, validate_function_payload


__all__ = ["recommend"]

_PYTHON_MEMORY = "memray_peak_tracked_allocations_bytes"
_NODE_MEMORY = "node_heap_used_delta_bytes"
_TIME_MARGIN = 0.05
_LIMITATIONS = (
    "Results apply only to sampled sizes, distributions, repetitions and the benchmark environment; "
    "there is no universal best sorting algorithm.",
    "Only numeric ascending correctness was tested; stability and custom comparator behavior are not proven.",
    "No Big-O complexity is derived from these samples.",
    "Timing rank uses an equal-weight geometric mean of per-case medians; median_seconds is the "
    "median of those medians, not the ranking score.",
    "The 5% timing margin is a practical noise guard, not a statistical significance test or confidence interval.",
)
_GENERIC_LIMITATIONS = (
    "Results apply only to the supplied dataset cases, repetitions and benchmark environment; "
    "size dimensions are caller-defined, not inferred measures of input size.",
    "Expected values validate only the supplied cases. A declared semantic contract identity "
    "does not prove equivalence of candidate functions beyond those checks.",
    "No Big-O complexity, universal optimality or stability is established beyond the declared validation rules.",
    *_LIMITATIONS[3:],
)
_NO_ORACLE = "No correctness oracle: contract correctness is none; measurements alone cannot establish eligibility or a winner."


def _empty(candidate, reason):
    return {"candidate": candidate, "eligible": False, "median_seconds": None,
            "timing_score_seconds": None, "peak_memory_bytes": None, "reason": reason}


def _request(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")
    language = payload.get("language")
    if not isinstance(language, str) or language not in {"python", "javascript", "typescript", "js", "ts"}:
        raise ValueError("unsupported language")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a nonempty list")
    names = []
    for candidate in candidates:
        name = candidate.get("name") if isinstance(candidate, dict) else None
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("candidate names must be unique nonempty strings")
        names.append(name)
    if is_generic(payload):
        validate_function_payload(payload)
        expected = {dataset["id"]: dataset.get("dimensions", {}) for dataset in payload["datasets"]}
    else:
        sizes, distributions = payload.get("sizes"), payload.get("distributions")
        if (not isinstance(sizes, list) or not sizes
                or any(type(size) is not int or size < 0 for size in sizes)
                or len(set(sizes)) != len(sizes)):
            raise ValueError("sizes must be unique nonnegative integers")
        if (not isinstance(distributions, list) or not distributions
                or any(not isinstance(d, str) or d not in {"random", "sorted", "reversed", "duplicates"}
                       for d in distributions)
                or len(set(distributions)) != len(distributions)):
            raise ValueError("invalid or duplicate distributions")
        expected = {(n, d) for n in sizes for d in distributions}
    repetitions = payload.get("repetitions")
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    objective = payload.get("objective", "time")
    if not isinstance(objective, str) or objective not in {"time", "memory"}:
        raise ValueError("objective must be time or memory")
    limit = payload.get("memory_limit_bytes")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("memory_limit_bytes must be a positive integer")
    return names, language, expected, repetitions, objective, limit


def _positive_finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _median(values):
    # Positive ordered endpoints keep the midpoint finite, even at float extremes.
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    lower, upper = float(ordered[middle - 1]), float(ordered[middle])
    return lower + (upper - lower) / 2


def _case_key(case, expected, generic):
    if generic:
        key = case.get("case_id")
        if not isinstance(key, str):
            raise ValueError("Malformed case id.")
        dimensions = case.get("dimensions")
        if (not isinstance(dimensions, dict)
                or any(type(k) is not str or type(v) is not int for k, v in dimensions.items())
                or key not in expected or dimensions != expected[key]):
            raise ValueError("Unexpected case id or mismatched dimensions: the exact requested datasets are required.")
        return key
    size, distribution = case.get("size"), case.get("distribution")
    if type(size) is not int or not isinstance(distribution, str):
        raise ValueError("Malformed case size or distribution.")
    return size, distribution


def _candidate(name, results, expected, repetitions, python, limit, generic=False):
    invalid = lambda reason: _empty(name, reason)
    if not results:
        return invalid("Missing candidate result.")
    if len(results) != 1:
        return invalid("Duplicate candidate results.")
    result = results[0]
    if "error" not in result or result["error"] is not None:
        return invalid("Candidate error or missing error status; no complete evidence.")
    cases = result.get("cases")
    if not isinstance(cases, list) or len(cases) != len(expected):
        return invalid("Missing or extra cases: the exact requested grid is required.")
    seen, medians, memories = set(), [], []
    for case in cases:
        if not isinstance(case, dict):
            return invalid("Malformed case.")
        try:
            key = _case_key(case, expected, generic)
        except ValueError as exc:
            return invalid(str(exc))
        if key not in expected or key in seen:
            return invalid("Duplicate or unexpected case: the exact requested grid is required.")
        seen.add(key)
        if generic:
            if case.get("correct") is not True or case.get("validation_status") != "verified":
                return invalid("Not all requested cases have verified expected-value correctness.")
        elif case.get("correct") is not True:
            return invalid("Not all requested cases passed numeric ascending correctness.")
        if "error" not in case or case["error"] is not None:
            return invalid("Case error or missing error status.")
        timings = case.get("timings_seconds")
        if not isinstance(timings, list) or len(timings) != repetitions:
            return invalid("Every case requires exactly the requested repetitions.")
        if not all(_positive_finite(t) for t in timings):
            return invalid("Every timing sample must be finite and strictly positive; zero is not reliable evidence.")
        metric = _PYTHON_MEMORY if python else _NODE_MEMORY
        memory = case.get("memory_bytes")
        if case.get("memory_metric") != metric:
            return invalid("Missing or unsupported memory metric.")
        if (type(memory) is not int or not -(2**63) <= memory < 2**63
                or (python and memory < 0)):
            return invalid("Missing or invalid memory bytes for the declared metric.")
        medians.append(_median(timings))
        memories.append(memory)
    low, high = min(medians), max(medians)
    log_score = math.fsum(math.log(t) / len(medians) for t in medians)
    # Clamp before exp too: rounding above log(max_float) would otherwise overflow.
    score = math.exp(min(math.log(high), max(math.log(low), log_score)))
    score = min(high, max(low, score))
    peak = max(memories) if python else None
    within_limit = limit is None or not python or peak <= limit
    return {"candidate": name, "eligible": within_limit, "median_seconds": _median(medians),
            "timing_score_seconds": score, "peak_memory_bytes": peak,
            "reason": ("All requested cases and samples passed."
                       if within_limit else "Tracked allocation peak exceeds memory_limit_bytes (not a total RAM limit).")}


def recommend(payload: dict, benchmark: dict) -> dict:
    """Rank complete runner evidence without mutation, execution, I/O or dependencies.

    Invalid evidence yields insufficient_evidence, never guessed measurements. A
    lone eligible candidate among multiple requests may win on validity only.
    """
    generic = is_generic(payload)
    limitations = list(_GENERIC_LIMITATIONS if generic else _LIMITATIONS)
    response = {"status": "insufficient_evidence", "winner": None, "reason": "",
                "rankings": [], "limitations": limitations}

    def insufficient(reason):
        response["reason"] = reason
        return response

    if isinstance(payload, dict) and payload.get("requirements_discovery") is not None:
        return insufficient("Discovered requirements are evaluated by the preserved deterministic policy decision; legacy aggregate rankings cannot establish requirement compliance.")

    if isinstance(payload, dict) and "compatibility_context" in payload:
        from intelligence.algorithms.compatibility import phase1_prerequisites
        if not phase1_prerequisites(payload, benchmark):
            return insufficient("Approved behavioral compatibility prerequisites are not established; no replacement ranking is available.")

    try:
        names, language, expected, repetitions, objective, limit = _request(payload)
    except ValueError as exc:
        return insufficient(f"Invalid request: {exc}.")
    python = language == "python"
    if python:
        limitations.append("Python memory is the maximum Memray peak tracked allocations across cases, "
                            "not RSS or total RAM; any memory limit applies only to that tracked allocation peak.")
    else:
        limitations.append("Node node_heap_used_delta_bytes is a signed retained heap delta, not peak memory "
                            "or RSS; memory objectives and memory limits are unsupported.")
    if generic and payload["contract"]["correctness"] == "none":
        # Raw worker measurements remain untouched for storage/display, never ranking.
        response["rankings"] = [_empty(name, _NO_ORACLE) for name in names]
        return insufficient(_NO_ORACLE)
    if (not isinstance(benchmark, dict) or benchmark.get("error") is not None
            or not isinstance(benchmark.get("results"), list)):
        response["rankings"] = [_empty(name, "Missing or malformed benchmark results.") for name in names]
        return insufficient("Missing, failed or malformed benchmark results.")
    indexed = {name: [] for name in names}
    for result in benchmark["results"]:
        if (not isinstance(result, dict) or not isinstance(result.get("candidate"), str)
                or result["candidate"] not in indexed):
            response["rankings"] = [_empty(name, "Malformed or unexpected candidate result.") for name in names]
            return insufficient("Malformed or unexpected candidate result; cannot trust this benchmark.")
        indexed[result["candidate"]].append(result)
    rankings = [_candidate(name, indexed[name], expected, repetitions, python, limit, generic) for name in names]
    response["rankings"] = rankings
    if not python and (objective == "memory" or limit is not None):
        for row in rankings:
            row["eligible"] = False
            row["reason"] += " Node retained heap delta cannot support a peak memory objective or limit."
        return insufficient("Node memory is a signed retained heap delta, not peak memory; "
                            "memory objectives and memory limits are unsupported.")
    score_key = "timing_score_seconds" if objective == "time" else "peak_memory_bytes"
    # Stable input order preserves display order for ties without implying a winner.
    rankings.sort(key=lambda row: (not row["eligible"], row[score_key] if row["eligible"] else 0))
    eligible = [row for row in rankings if row["eligible"]]
    if not eligible:
        return insufficient("No candidate has complete passing evidence within the supported constraints.")
    if len(names) < 2:
        return insufficient("At least two requested candidates are needed for a comparison.")
    if len(eligible) == 1:
        reason = ("Only eligible candidate among the requested alternatives; selected on correctness, "
                  "complete evidence and supported constraints only. No speed comparison is possible.")
    elif objective == "time":
        best, second = (row[score_key] for row in eligible[:2])
        if (second - best) / best <= _TIME_MARGIN or math.isclose(second / best, 1 + _TIME_MARGIN, rel_tol=1e-12):
            return insufficient("Top timing scores are within the 5% meaningful-difference threshold; "
                                "a tie or noisy difference does not establish a winner.")
        reason = "Lowest equal-weight geometric mean of per-case median timings, with more than a 5% advantage over the runner-up."
    else:
        if eligible[0][score_key] == eligible[1][score_key]:
            return insufficient("Top tracked allocation peaks are identical; no strict memory advantage (timing is not a tie-breaker).")
        reason = "Strictly lowest maximum Memray tracked allocation peak across all requested cases, not RSS or total RAM."
    response.update(status="recommended", winner=eligible[0]["candidate"], reason=reason)
    return response
