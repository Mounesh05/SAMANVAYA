"""Finite-scope compatibility. No execution or algorithm-name judgments here."""

from intelligence.algorithms.decision import fingerprint
from benchmark_worker.contracts import VALIDATION_VERSION
import hashlib

VERSION = "behavioral-compatibility-v1"
COMPATIBLE = "COMPATIBLE_WITHIN_TESTED_CONTRACT"


def execution_binding(request, results):
    context = request["compatibility_context"]
    return fingerprint({"contract_fingerprint": context["resolution"].get("fingerprint"),
                        "contract": request.get("contract"), "datasets": request.get("datasets", []),
                        "candidates": request["candidates"], "languages": context["candidate_languages"],
                        "repetitions": request["repetitions"], "results": results})


def evaluate_compatibility(request, evidence, run_id):
    context = request["compatibility_context"]
    resolution = context["resolution"]
    required = context.get("required_dataset_ids", [])
    ref = run_id + "/behavioral_compatibility"
    base_refs = [run_id + "/request/compatibility_context/resolution", run_id + "/request"]
    result = {"version": VERSION, "status": "UNVERIFIED", "previous": context["previous"],
              "current": context["current"], "relationship": context["relationship"],
              "contract_resolution": resolution, "required_checks": required,
              "requirements": context.get("requirements", []), "checks": [], "evidence_refs": base_refs,
              "unverified_behavior": [], "phase1_eligible": False,
              "limitations": ["Finite approved validation scope only; no universal equivalence or replacement guarantee.",
                              "Names, signatures, static hypotheses and past implementations are not compatibility proof.",
                              "Worker evidence retains the existing non-tamper-proof harness limitation.",
                              "No arbitrary validators, trusted property-oracle registry or unrestricted test generation was introduced."],
              "evidence_binding": execution_binding(request, evidence.get("results", []))}
    if resolution["status"] == "MISSING":
        result.update(status="CONTRACT_MISSING", unverified_behavior=["No trustworthy approved comparison contract was resolved."])
        return result
    if resolution["status"] != "APPROVED":
        result["unverified_behavior"] = ["Contract evidence is proposed, conflicting, incomplete or not approved."]
        return result
    if resolution.get("validator_available") is not True:
        result["unverified_behavior"] = ["The approved scope requires a validator that is not implemented; no oracle was invented."]
        return result
    if context.get("context_errors"):
        result["unverified_behavior"] = list(context["context_errors"])
        return result
    snapshot = resolution.get("snapshot") or {}
    approved_data = {d["id"]: d for d in snapshot.get("datasets", [])}
    if (fingerprint(snapshot) != resolution.get("fingerprint") or request.get("contract") != snapshot.get("contract")
            or required != snapshot.get("required_dataset_ids")
            or any(fingerprint(d) != fingerprint(approved_data.get(d["id"])) for d in request.get("datasets", []))):
        result["unverified_behavior"] = ["The executed contract or datasets do not match the approved immutable scope."]
        return result
    for candidate, identity in zip(request["candidates"], (context["previous"], context["current"])):
        if (hashlib.sha256(candidate["source"].encode()).hexdigest() != identity["source_hash"]
                or candidate["entrypoint"] != identity["entrypoint"] or candidate["name"] != identity["name"]):
            result["unverified_behavior"] = ["Candidate identity no longer matches the comparison snapshot."]
            return result
    if not required:
        result["unverified_behavior"] = ["The reviewed contract declares no required checks."]
        return result
    names = [candidate["name"] for candidate in request["candidates"]]
    raw = evidence.get("results", [])
    rows = raw if isinstance(raw, list) else []
    environment = evidence.get("environment", {})
    environment = environment if isinstance(environment, dict) else {}
    selected = {d["id"]: d for d in request.get("datasets", [])}
    all_ids = list(dict.fromkeys(required + list(selected)))
    for name in names:
        matches = [row for row in rows if isinstance(row, dict) and row.get("candidate") == name]
        row = matches[0] if len(matches) == 1 else {}
        cases = row.get("cases", []) if row.get("error") is None else []
        if not isinstance(cases, list):
            cases = []
        malformed = (any(not isinstance(c, dict) or c.get("case_id") not in selected for c in cases)
                     or any(not isinstance(row, dict) or row.get("candidate") not in names for row in rows)
                     or environment.get("isolation") != "docker"
                     or environment.get("network") != "none")
        for check_id in all_ids:
            matches = [c for c in cases if isinstance(c, dict) and c.get("case_id") == check_id]
            case = matches[0] if len(matches) == 1 and not malformed else {}
            behavior = case.get("behavioral_validation", {})
            behavior = behavior if isinstance(behavior, dict) else {}
            state = "UNVERIFIED"
            descriptor = selected.get(check_id)
            shape = descriptor is not None and fingerprint(case.get("dimensions")) == fingerprint(descriptor.get("dimensions", {}))
            if shape and behavior.get("version") == VALIDATION_VERSION:
                if (case.get("correct") is False and case.get("validation_status") == "failed"
                        and case.get("error") and behavior.get("status") == "FAIL"):
                    state = "FAIL"
                elif (case.get("correct") is True and case.get("validation_status") == "verified"
                      and case.get("error") is None and behavior.get("status") == "PASS"
                      and type(behavior.get("validated_calls")) is int
                      and behavior["validated_calls"] >= request["repetitions"] + 3):
                    state = "PASS"
            evidence_ref = f"{run_id}/results/{name}/datasets/{check_id}"
            result["checks"].append({"candidate": name, "dataset_id": check_id, "status": state,
                                     "evidence_reference": evidence_ref,
                                     "input_fingerprint": fingerprint(descriptor["args"]) if descriptor else None,
                                     "violation": case.get("error") if state == "FAIL" else None,
                                     "reason": behavior.get("reason", "Required validation evidence is unavailable.")})
            result["evidence_refs"].append(evidence_ref)
    states = [check["status"] for check in result["checks"]]
    result["unverified_behavior"] = [f"{c['candidate']}: required check {c['dataset_id']} lacks complete validation."
                                     for c in result["checks"] if c["status"] == "UNVERIFIED"]
    if "FAIL" in states:
        result["status"] = "INCOMPATIBLE"
    elif states and all(state == "PASS" for state in states):
        result.update(status=COMPATIBLE, phase1_eligible=True)
        result["unverified_behavior"] = ["Inputs outside the approved finite dataset scope are not validated.",
                                         "External side effects, concurrency and unlisted requirements are not established."]
    result["phase1_evidence_reference"] = ref
    return result


def phase1_prerequisites(request, evidence):
    if "compatibility_context" not in request:
        return True  # Existing explicit manual benchmark semantics are unchanged.
    if not isinstance(request["compatibility_context"], dict) or not request["compatibility_context"]:
        return False
    report = evidence.get("behavioral_compatibility", {})
    if not isinstance(report, dict) or report.get("status") != COMPATIBLE or report.get("phase1_eligible") is not True:
        return False
    try:
        expected = evaluate_compatibility(request, evidence, "phase1-validation")
    except (ValueError, KeyError, TypeError, AttributeError):
        return False
    return (expected["status"] == COMPATIBLE and report.get("evidence_binding") == expected["evidence_binding"])


def provisional_relationships(previous, current, previous_run_id, current_run_id, contract_bindings=()):
    result = []
    for before in previous.get("functions", []):
        for after in current.get("functions", []):
            reasons, refs = [], []
            if before["path"] == after["path"] and before["qualified_name"] == after["qualified_name"]:
                reasons.append("same_lexical_function_identity")
            before_tasks = {h["kind"] for h in before.get("task_hypotheses", [])}
            if before_tasks & {h["kind"] for h in after.get("task_hypotheses", [])}:
                reasons.append("related_inferred_task_context")
            if {(c["path"], c["line"]) for c in before.get("callers", [])} & {(c["path"], c["line"]) for c in after.get("callers", [])}:
                reasons.append("shared_lexical_call_site")
            if {e["path"] for e in before.get("evidence", []) if e["kind"] == "test_expectation"} & {e["path"] for e in after.get("evidence", []) if e["kind"] == "test_expectation"}:
                reasons.append("shared_static_test_context")
            for binding in contract_bindings:
                ids = {(b["run_id"], b["function_id"]) for b in binding.get("function_bindings", [])}
                if (previous_run_id, before["function_id"]) in ids and (current_run_id, after["function_id"]) in ids:
                    reasons.append("shared_approved_contract_reference")
                    refs.append("algorithm_function_contracts/" + binding["contract_id"])
            if not reasons:
                continue
            result.append({"status": "PROVISIONAL", "previous": {"run_id": previous_run_id, "function_id": before["function_id"], "source_revision": before.get("source_revision"), "source_hash": before["source_hash"]},
                           "current": {"run_id": current_run_id, "function_id": after["function_id"], "source_revision": after.get("source_revision"), "source_hash": after["source_hash"]},
                           "reasons": list(dict.fromkeys(reasons)), "evidence_refs": refs + [f"{previous_run_id}/functions/{before['function_id']}", f"{current_run_id}/functions/{after['function_id']}"],
                           "limitations": ["Revision labels do not establish Git ancestry or interchangeability.", "Contract validation is required; this is only a candidate relationship."]})
            if len(result) == 50:
                return result
    return result
