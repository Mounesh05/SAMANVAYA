"""Finite observed growth on an explicitly reviewed, one-dimensional workload."""

import json
import math
from statistics import median


def prefix_workload(series, datasets):
    """Return ordered (size, case ID) pairs after independently checking the generator."""
    selected = {d["id"]: d for d in datasets}
    ids = series["dataset_ids"]
    index = series["argument_index"]
    if not 6 <= len(set(ids)) == len(ids) <= 32 or not set(ids) <= selected.keys():
        raise ValueError("Growth series needs six or more distinct reviewed cases")
    rows = []
    for case_id in ids:
        case = selected[case_id]
        args = case["args"]
        if index >= len(args) or not isinstance(args[index], list) or "expected" not in case:
            raise ValueError("Growth case lacks its array argument or expected output")
        n = len(args[index])
        if n < 2 or case.get("dimensions", {}).get(series["dimension"]) != n:
            raise ValueError("Growth dimension must equal the controlled array length")
        rows.append((n, case_id, args))
    rows.sort()
    if len({n for n, _, _ in rows}) != len(rows):
        raise ValueError("Growth series sizes must be distinct")
    largest = rows[-1][2]
    for n, _, args in rows:
        expected = [*largest[:index], largest[index][:n], *largest[index + 1:]]
        # JSON encoding distinguishes booleans, floats and integers.
        if json.dumps(args, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError("Workload differs from the approved prefix generator")
    return [(n, case_id) for n, case_id, _ in rows]


_MODELS = {
    "constant": lambda n: 1,
    "logarithmic": math.log2,
    "linear": lambda n: n,
    "linearithmic": lambda n: n * math.log2(n),
    "quadratic": lambda n: n * n,
    "cubic": lambda n: n ** 3,
}


def _fit(model, train, held_out):
    # Fit a + b*f(n), a,b >= 0, minimizing squared relative residuals.
    # Consider the interior solution and both nonnegative boundary solutions.
    x = [1 / y for n, y in train]
    z = [model(n) / y for n, y in train]
    xx, zz, xz = sum(v*v for v in x), sum(v*v for v in z), sum(i*j for i, j in zip(x, z))
    sx, sz = sum(x), sum(z)
    solutions = [(sx / xx, 0.0), (0.0, sz / zz)]
    det = xx * zz - xz * xz
    if det > 1e-12 * xx * zz:
        a, b = (sx * zz - sz * xz) / det, (sz * xx - sx * xz) / det
        if min(a, b) >= 0:
            solutions.append((a, b))
    def residuals(coefficients, points):
        a, b = coefficients
        return [abs((a + b * model(n)) / y - 1) for n, y in points]
    best = min(solutions, key=lambda c: sum(r*r for r in residuals(c, train)))
    return {"offset_seconds": best[0], "coefficient_seconds": best[1],
            "train_relative_error": max(residuals(best, train)),
            "held_out_relative_error": max(residuals(best, held_out))}


def estimate_series(series, datasets, results):
    report = {"method": "prefix-relative-least-squares-v1", "status": "insufficient_evidence",
              "candidates": [], "scope": "Observed elapsed time within the reviewed size range"}
    if not series:
        return {**report, "reason": "No approved workload generator"}
    try:
        sizes = prefix_workload(series, datasets)
    except ValueError as exc:
        return {**report, "reason": str(exc)}
    for result in results:
        row = {"candidate": result["candidate"], "dimension": series["dimension"],
               "distribution": series["distribution"], "status": "insufficient_evidence",
               "train_sizes": [n for n, _ in sizes[:-2]], "held_out_sizes": [n for n, _ in sizes[-2:]]}
        report["candidates"].append(row)
        cases = {c.get("case_id"): c for c in result.get("cases", [])}
        points, spreads = [], []
        for n, key in sizes:
            case = cases.get(key, {})
            timings = case.get("timings_seconds") or []
            if (case.get("correct") is not True or case.get("timing_status") != "AVAILABLE"
                    or len(timings) < 3 or not all(type(v) in (float, int) and math.isfinite(v)
                                                   and 1e-12 <= v <= 3600 for v in timings)):
                break
            center = median(timings)
            points.append((n, center))
            spreads.append(median(abs(t - center) for t in timings) / center)
        if len(points) != len(sizes):
            row["reason"] = "Missing verified oracle or repeated timing samples"
            continue
        noise = max(spreads)
        row["max_relative_mad"] = noise
        fits = {label: _fit(model, points[:-2], points[-2:]) for label, model in _MODELS.items()}
        row["fits"] = fits
        # Policy tolerances describe resolution, not statistical confidence.
        tolerance = max(0.03, 3 * noise)
        row["relative_resolution"] = tolerance
        scores = {label: max(fit["train_relative_error"], fit["held_out_relative_error"])
                  for label, fit in fits.items()}
        best = min(scores, key=scores.get)
        plausible = [k for k, v in scores.items() if v <= scores[best] + tolerance]
        measured = [y for _, y in points]
        if max(measured) / min(measured) - 1 <= tolerance:
            # Higher-order models also contain a constant submodel at zero slope.
            row["status"], row["reason"] = "inconclusive", "No growth resolved above timing variability"
        elif noise > 0.15 or scores[best] > tolerance or len(plausible) != 1:
            row["status"], row["reason"] = "inconclusive", "Noise, fit error or competing models prevent discrimination"
        else:
            row.update(status="observed_fit", model=best)
    if report["candidates"]:
        statuses = {r["status"] for r in report["candidates"]}
        report["status"] = statuses.pop() if len(statuses) == 1 else "partial"
    return report
