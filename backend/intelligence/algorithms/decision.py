"""Pure, same-run constraint evaluation and exact-workload comparison.

No source execution, I/O, global rankings, or inferred requirements. The result
is authoritative only for the preserved evidence and explicit policy snapshot.
"""

import hashlib
import json
import math

from benchmark_worker.contracts import is_generic
from benchmark_worker.python_worker import make_input
from domain.schemas.decision_policy import DecisionPolicy, PEAK_TRACKED
from intelligence.algorithms.measurements import availability

ENGINE_VERSION = "deterministic-decision-v1"
FINGERPRINT_VERSION = "typed-json-sha256-v1"


def fingerprint(value):
    """Typed canonical JSON: preserve arrays/arguments, bool/int/float distinctions."""
    def typed(item):
        if isinstance(item, dict):
            return ["object", [[k, typed(v)] for k, v in sorted(item.items())]]
        if isinstance(item, list):
            return ["array", [typed(v) for v in item]]
        if item is None:
            return ["null"]
        if type(item) not in (str, bool, int, float):
            raise ValueError("Fingerprints require JSON")
        return [type(item).__name__, item]
    raw = json.dumps(typed(value), ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    return FINGERPRINT_VERSION + ":" + hashlib.sha256(raw.encode()).hexdigest()


def datasets_for(request):
    if is_generic(request):
        return request["datasets"]
    rows = []
    for size in request["sizes"]:
        for distribution in request["distributions"]:
            data = make_input(size, distribution, request.get("seed", 42))
            rows.append({"id": f"sort:{size}:{distribution}", "args": [data], "expected": sorted(data)})
    return rows


def identities(request, evidence):
    generic = is_generic(request)
    contract = ({"mutation": "allowed", "output": {"source": "return"}, **request["contract"]}
                if generic else {"kind": "numeric-ascending-sort", "version": "1",
                                 "domain": "finite-integers", "output": "return-or-inplace"})
    if generic and contract["output"].get("source") == "argument":
        contract["output"] = {"index": 0, **contract["output"]}
    contract_fp = fingerprint({"language": request["language"], "contract": contract})
    datasets = {d["id"]: {"inputs": fingerprint(d["args"]),
                           "validation": fingerprint({"contract": contract_fp,
                               "has_expected": "expected" in d, "expected": d.get("expected")})}
                for d in datasets_for(request)}
    implementations = {c["name"]: fingerprint({"source": c["source"], "entrypoint": c["entrypoint"]}) for c in request["candidates"]}
    execution = fingerprint({"contract": contract_fp, "datasets": datasets, "implementations": implementations,
                             "resources": request.get("resources", {}), "repetitions": request["repetitions"],
                             "seed": request.get("seed", 42)})
    return {"fingerprint_version": FINGERPRINT_VERSION, "contract": contract_fp,
            "datasets": datasets, "implementations": implementations,
            "execution": execution, "evidence": fingerprint(evidence)}


def _methodology(request, evidence, name):
    env, tools = evidence.get("environment", {}), evidence.get("tools", {})
    if not isinstance(env, dict) or not isinstance(tools, dict) or not tools:
        return None
    required = ("images", "cpus", "memory_limit_bytes", "timing_method", "workers")
    if any(not env.get(k) for k in required):
        return None
    if not isinstance(env["workers"], list):
        return None
    workers = [w for w in env["workers"] if isinstance(w, dict) and w.get("candidate") == name]
    if len(workers) != 1 or not workers[0].get("runtime") or not workers[0].get("platform"):
        return None
    return fingerprint({"environment": {k: v for k, v in env.items() if k not in ("workers", "seed")},
                        "worker": {k: v for k, v in workers[0].items() if k != "candidate"},
                        "tools": tools, "repetitions": request["repetitions"]})


def _stats(case, state):
    values = case.get("timings_seconds", [])
    values = values if isinstance(values, list) else []
    if state != "AVAILABLE":
        return {"status": state, "count": len(values), "median": None, "minimum": None,
                "maximum": None, "variability_ratio": None}
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else ordered[middle - 1] + (ordered[middle] - ordered[middle - 1]) / 2
    variability = (max(values) - min(values)) / median
    return {"status": state, "count": len(values), "median": median,
            "minimum": min(values), "maximum": max(values),
            "variability_ratio": variability if math.isfinite(variability) else None}


def _eligibility(evaluations, correctness, conflict=False):
    if correctness == "FAIL":
        return "INELIGIBLE"
    if conflict:
        return "CONFLICT"
    mandatory = [e["status"] for e in evaluations if e["classification"] == "MANDATORY"]
    if "FAIL" in mandatory:
        return "INELIGIBLE"
    if correctness != "PASS" or "UNVERIFIED" in mandatory:
        return "UNVERIFIED"
    return "ELIGIBLE"


def evaluate_constraints(request, evidence, policy, run_id="evidence"):
    """Evaluate every established constraint separately, retaining exact scope."""
    policy = DecisionPolicy.model_validate(policy).model_dump()
    datasets = datasets_for(request)
    ids = [d["id"] for d in datasets]
    required = policy["required_dataset_ids"] or ids
    generic = is_generic(request)
    expected_correctness = not generic or request["contract"]["correctness"] == "expected"
    results = evidence.get("results", [])
    if not isinstance(results, list):
        results = []
    names = [c["name"] for c in request["candidates"]]
    malformed = (evidence.get("error") is not None or any(not isinstance(r, dict)
                 or r.get("candidate") not in names for r in results))
    candidate_rows = []
    for name in names:
        matches = [r for r in results if isinstance(r, dict) and r.get("candidate") == name]
        result = matches[0] if len(matches) == 1 and not malformed else {}
        cases = result.get("cases", [])
        if not isinstance(cases, list):
            cases = []
        case_map, duplicate = {}, False
        for case in cases:
            if not isinstance(case, dict):
                duplicate = True
                continue
            key = case.get("case_id") if generic else f"sort:{case.get('size')}:{case.get('distribution')}"
            if key not in ids or key in case_map:
                duplicate = True
            case_map[key] = case
        if duplicate or result.get("error") is not None:
            case_map = {}
        per_dataset = {}
        for d in datasets:
            key, case = d["id"], case_map.get(d["id"], {})
            ref = f"{run_id}/results/{name}/datasets/{key}"
            protocol_error = None
            try:
                states = availability(case, request["repetitions"], request["language"] == "python")
            except (ValueError, TypeError, OverflowError) as exc:
                states = {"timing": "INVALID", "memory": "INVALID"}
                protocol_error = str(exc)
            shape_valid = not generic or case.get("dimensions") == d.get("dimensions", {})
            if case.get("correct") is False and shape_valid:
                correctness = "FAIL"
            elif (case.get("correct") is True and case.get("error") is None and shape_valid
                  and expected_correctness and (not generic or case.get("validation_status") == "verified")):
                correctness = "PASS"
            else:
                correctness = "UNVERIFIED"
            if protocol_error:
                correctness = "UNVERIFIED" if correctness != "FAIL" else "FAIL"
            per_dataset[key] = {"dataset_id": key, "correctness": correctness,
                                "timing": _stats(case, states["timing"]),
                                "memory": {"status": states["memory"], "metric": case.get("memory_metric"),
                                           "bytes": case.get("memory_bytes") if states["memory"] == "AVAILABLE" else None},
                                "evidence_reference": ref, "protocol_error": protocol_error,
                                "evaluations": []}
        correctness = ("FAIL" if any(r["correctness"] == "FAIL" for r in per_dataset.values())
                       else "PASS" if all(r["correctness"] == "PASS" for r in per_dataset.values()) else "UNVERIFIED")
        evaluations = []
        def record(constraint, scope, status, **details):
            row = {"constraint_id": constraint["id"], "type": constraint["type"],
                   "classification": constraint["classification"], "dataset_id": scope,
                   "status": status, "source_reference": constraint["source_reference"], **details}
            evaluations.append(row)
            if scope in per_dataset:
                per_dataset[scope]["evaluations"].append(row)
        for constraint in policy["constraints"]:
            coverage = constraint["type"] == "DATASET_COVERAGE"
            scopes = [None] if coverage else list(dict.fromkeys(ids + constraint["dataset_ids"]))
            for key in scopes:
                applies = coverage or not constraint["dataset_ids"] or key in constraint["dataset_ids"]
                conflict = constraint["applicability"] == "UNRESOLVED" or constraint["unresolved_override_of"] is not None
                details = {k: constraint[k] for k in ("threshold", "metric", "unit", "evaluation_policy")}
                details["conflict"] = bool(applies and conflict and constraint["applicability"] != "NOT_APPLICABLE")
                if not applies or constraint["applicability"] == "NOT_APPLICABLE":
                    record(constraint, key, "NOT_APPLICABLE", **details)
                    continue
                if conflict:
                    record(constraint, key, "UNVERIFIED", **details)
                    continue
                if coverage:
                    missing = [i for i in constraint["required_dataset_ids"]
                               if i not in per_dataset or per_dataset[i]["correctness"] == "UNVERIFIED"]
                    status = "UNVERIFIED" if missing else "PASS"
                    record(constraint, None, status, missing_dataset_ids=missing,
                           required_dataset_ids=constraint["required_dataset_ids"], **details)
                    continue
                row = per_dataset.get(key)
                details["evidence_reference"] = row["evidence_reference"] if row else None
                if not row:
                    record(constraint, key, "UNVERIFIED", **details)
                elif constraint["type"] == "EXPECTED_OUTPUT":
                    record(constraint, key, row["correctness"] if expected_correctness else "UNVERIFIED", **details)
                elif constraint["type"] == "MAX_LATENCY":
                    stats = row["timing"]
                    observed = stats["maximum"]
                    status = "UNVERIFIED" if stats["status"] != "AVAILABLE" else "PASS" if observed <= constraint["threshold"] else "FAIL"
                    record(constraint, key, status, observed_maximum=observed, sample_count=stats["count"],
                           method="maximum_of_configured_valid_repetitions", **details)
                else:
                    memory = row["memory"]
                    compatible = memory["status"] == "AVAILABLE" and memory["metric"] == constraint["metric"] == PEAK_TRACKED
                    status = "UNVERIFIED" if not compatible else "PASS" if memory["bytes"] <= constraint["threshold"] else "FAIL"
                    record(constraint, key, status, observed_peak=memory["bytes"] if compatible else None, **details)
        for key, row in per_dataset.items():
            # Required-set coverage governs whole-task suitability. An absent
            # different dataset does not erase verified eligibility on this one.
            checks = row["evaluations"] + [e for e in evaluations if e["dataset_id"] is None and e.get("conflict")]
            row["requirement_conflict"] = any(e.get("conflict") for e in checks)
            row["eligibility"] = _eligibility(checks, "FAIL" if correctness == "FAIL" else row["correctness"],
                                              any(e.get("conflict") for e in checks))
        missing_required = [key for key in required if key not in per_dataset]
        task_checks = [e for e in evaluations if e["dataset_id"] is None or e["dataset_id"] in required]
        task = _eligibility(task_checks, correctness, any(e.get("conflict") for e in task_checks))
        if missing_required and task == "ELIGIBLE":
            task = "UNVERIFIED"
        candidate_rows.append({"candidate": name, "correctness": correctness,
                               "datasets": list(per_dataset.values()), "constraint_evaluations": evaluations,
                               "task_eligibility": task, "missing_required_dataset_ids": missing_required,
                               "requirement_conflict": any(e.get("conflict") for e in task_checks),
                               "methodology_fingerprint": _methodology(request, evidence, name)})
    return candidate_rows


def compare_workloads(candidates, policy):
    """Compare only eligible same-run candidates on each exact tested dataset."""
    objective = policy.get("objective") or "TRADEOFF_ONLY"
    comparisons = []
    for dataset in candidates[0]["datasets"]:
        key = dataset["dataset_id"]
        pairs = [(candidate, next(d for d in candidate["datasets"] if d["dataset_id"] == key)) for candidate in candidates]
        eligible = [(c, d) for c, d in pairs if d["eligibility"] == "ELIGIBLE"]
        states = [d["eligibility"] for _, d in pairs]
        result = {"dataset_id": key, "objective": objective, "winner": None,
                  "eligible_candidates": [c["candidate"] for c, _ in eligible],
                  "evidence_references": [d["evidence_reference"] for _, d in pairs]}
        def conclude(status, reason):
            result.update(status=status, reason=reason)
        if any(d.get("requirement_conflict") for _, d in pairs):
            conclude("REQUIREMENT_CONFLICT", "Applicability or an authorized override relationship is unresolved.")
        elif not eligible:
            conclude("NO_ELIGIBLE_IMPLEMENTATION" if all(s == "INELIGIBLE" for s in states) else "INSUFFICIENT_EVIDENCE",
                     "All candidates fail mandatory checks." if all(s == "INELIGIBLE" for s in states) else "At least one candidate lacks verified mandatory evidence.")
        elif len(eligible) == 1:
            conclude("INSUFFICIENT_EVIDENCE" if "UNVERIFIED" in states else "ELIGIBILITY_ONLY",
                     "Eligibility established for one candidate; comparative superiority is not established.")
        elif objective == "TRADEOFF_ONLY":
            conclude("MULTIPLE_ELIGIBLE", "Tradeoffs only: no optimization objective selects a winner.")
        elif any(c["methodology_fingerprint"] is None for c, _ in eligible) or len({c["methodology_fingerprint"] for c, _ in eligible}) != 1:
            conclude("INCOMPARABLE_IMPLEMENTATIONS", "Compatible measurement methodology/environment provenance is absent or differs.")
        elif objective == "MINIMIZE_TIME":
            timing = policy["timing"]
            if any(d["timing"]["status"] != "AVAILABLE" or d["timing"]["count"] < timing["minimum_samples"] for _, d in eligible):
                conclude("INSUFFICIENT_EVIDENCE", "Complete timing and the minimum sample count are required.")
            elif any(d["timing"]["variability_ratio"] is None or (
                    d["timing"]["variability_ratio"] > timing["maximum_variability_ratio"] and not math.isclose(
                        d["timing"]["variability_ratio"], timing["maximum_variability_ratio"], rel_tol=1e-12, abs_tol=1e-15))
                    for _, d in eligible):
                conclude("MULTIPLE_ELIGIBLE", "Inconclusive: timing variability exceeds the policy threshold.")
            else:
                ordered = sorted(eligible, key=lambda pair: pair[1]["timing"]["median"])
                best, second = [d["timing"]["median"] for _, d in ordered[:2]]
                ratio = (second - best) / best
                threshold = timing["practical_difference_ratio"]
                if ratio <= threshold or math.isclose(ratio, threshold, rel_tol=1e-12, abs_tol=1e-15):
                    conclude("MULTIPLE_ELIGIBLE", "Inconclusive: median difference is at or below the practical threshold; no statistical confidence is inferred.")
                else:
                    conclude("CONDITIONAL_COMPARISON" if "UNVERIFIED" in states else "ELIGIBLE_WINNER", "Lowest stable median on this exact dataset among comparable eligible candidates only.")
                    result["winner"] = ordered[0][0]["candidate"]
        else:
            metric = policy.get("memory_metric")
            if any(d["memory"]["status"] != "AVAILABLE" or d["memory"]["metric"] != metric or metric != PEAK_TRACKED for _, d in eligible):
                conclude("INSUFFICIENT_EVIDENCE", "Approved compatible peak-memory measurements are required; heap delta and RSS are not tracked-allocation peak.")
            else:
                ordered = sorted(eligible, key=lambda pair: pair[1]["memory"]["bytes"])
                if ordered[0][1]["memory"]["bytes"] == ordered[1][1]["memory"]["bytes"]:
                    conclude("MULTIPLE_ELIGIBLE", "Inconclusive: equal tracked allocation peaks; no time tie-breaker.")
                else:
                    conclude("CONDITIONAL_COMPARISON" if "UNVERIFIED" in states else "ELIGIBLE_WINNER", "Strictly lowest tracked allocation peak on this exact dataset only.")
                    result["winner"] = ordered[0][0]["candidate"]
        comparisons.append(result)
    return comparisons


def evaluate_decision(request, evidence, policy, run_id="evidence"):
    """Reconstruct a decision without mutating requests, raw evidence, or policies."""
    policy = DecisionPolicy.model_validate(policy).model_dump()
    candidates = evaluate_constraints(request, evidence, policy, run_id)
    comparisons = compare_workloads(candidates, policy)
    states = [c["task_eligibility"] for c in candidates]
    suitable = [c["candidate"] for c in candidates if c["task_eligibility"] == "ELIGIBLE"]
    status = ("REQUIREMENT_CONFLICT" if any(c["requirement_conflict"] for c in candidates) else
              "NO_ELIGIBLE_IMPLEMENTATION" if all(s == "INELIGIBLE" for s in states) else
              "INSUFFICIENT_EVIDENCE" if not suitable else
              "CONDITIONAL_COMPARISON" if policy["unknown_requirements"] or "UNVERIFIED" in states else
              "ELIGIBILITY_ONLY" if len(suitable) == 1 else "MULTIPLE_ELIGIBLE")
    missing = [{"candidate": c["candidate"], "dataset_id": d["dataset_id"], "measurement": kind,
                "status": d[kind]["status"], "evidence_reference": d["evidence_reference"]}
               for c in candidates for d in c["datasets"] for kind in ("timing", "memory") if d[kind]["status"] != "AVAILABLE"]
    missing.extend({"candidate": c["candidate"], "dataset_id": key, "measurement": "required_dataset", "status": "UNAVAILABLE"}
                   for c in candidates for key in c["missing_required_dataset_ids"])
    unverified = [{"candidate": c["candidate"], **check} for c in candidates for check in c["constraint_evaluations"]
                  if check["status"] == "UNVERIFIED"]
    return {"engine_version": ENGINE_VERSION, "policy_id": policy["id"], "policy_version": policy["version"],
            "policy_snapshot": policy, "policy_fingerprint": fingerprint(policy),
            "identities": identities(request, evidence), "candidates": candidates,
            "dataset_comparisons": comparisons, "unknown_requirements": policy["unknown_requirements"],
            "missing_evidence": missing, "unverified_requirements": unverified,
            "task_suitability": {"status": status, "eligible_candidates": suitable,
                "global_winner": None, "required_dataset_ids": policy["required_dataset_ids"] or [d["id"] for d in datasets_for(request)]},
            "limitations": ["Expected-output success establishes tested correctness only, not universal equivalence.",
                            "Dataset winners do not establish global optimality or performance on untested inputs.",
                            "Unknown requirements are not acceptance constraints; no compliance with them is claimed.",
                            "Practical difference and variability thresholds are deterministic policies, not statistical confidence.",
                            "Worker evidence is not tamper-proof against deliberately malicious submissions."]}
