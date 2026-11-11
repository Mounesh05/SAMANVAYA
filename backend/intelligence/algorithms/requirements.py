"""Pure provenance, applicability, cumulative constraints and policy preparation.

No source code executes here. Natural language and model output cannot grant authority.
"""

import copy

from domain.schemas.decision_policy import DecisionPolicy
from intelligence.algorithms.decision import fingerprint

METHOD = "requirement-discovery-v1"
SOURCE_FIELDS = ("project_id", "source_kind", "source_reference", "source_revision", "requirements", "supersedes")


def source_content(doc):
    return {key: copy.deepcopy(doc.get(key)) for key in SOURCE_FIELDS}


def trusted_source(doc, include_superseded=False):
    approval = doc.get("approval") or {}
    allowed = {"APPROVED", "SUPERSEDED"} if include_superseded else {"APPROVED"}
    return (doc.get("status") in allowed and approval.get("scope_reviewed") is True
            and approval.get("approved_by") and approval.get("approved_by") != doc.get("proposed_by")
            and approval.get("organization_id") == doc.get("organization_id")
            and approval.get("expected_fingerprint") == doc.get("payload_fingerprint") == fingerprint(source_content(doc)))


def applicability(scope, context, dataset_ids):
    unresolved = False
    for key, target in (("repository", context.get("repository")), ("source_revision", context.get("source_revision"))):
        if scope.get(key):
            if target is None:
                unresolved = True
            elif scope[key] != target:
                return "NOT_APPLICABLE"
    for key, targets in (("contract_id", context.get("contract_ids", [])), ("function_id", context.get("function_ids", []))):
        if scope.get(key):
            if not targets:
                unresolved = True
            elif scope[key] not in targets:
                return "NOT_APPLICABLE"
    # Missing scoped workloads must be checked, never silently removed.
    if scope.get("dataset_ids") and dataset_ids is not None and not set(scope["dataset_ids"]) & set(dataset_ids):
        unresolved = True
    return "UNRESOLVED" if unresolved else "APPLIES"


def candidate(requirement_type, value, reference, revision, authority, scope=None, **extra):
    identity = fingerprint([reference, revision, requirement_type, value, scope, extra]).rsplit(":", 1)[-1][:24]
    return {"id": "REQ-" + identity, "type": requirement_type, "value": copy.deepcopy(value),
            "unit": None, "metric": None, "scope": scope or {}, "source_reference": reference,
            "source_revision": revision, "extraction_method": METHOD, "authority_status": authority,
            "applicability_status": "APPLIES", "evidence_refs": [reference], **extra}


def resolve_requirements(project_id, context, sources, observations=(), suggestions=(), limitations=(), dataset_ids=None, established=()):
    report = {"method": METHOD, "project_id": project_id, "context": copy.deepcopy(context),
              "established": list(established), "observations": list(observations), "suggestions": list(suggestions),
              "unknown": [], "conflicts": [], "excluded": [], "limitations": list(limitations)}
    for doc in sources:
        if doc.get("project_id") != project_id:
            continue
        trusted = trusted_source(doc)
        if doc.get("status") == "APPROVED" and not trusted:
            report["conflicts"].append({"reason": "Previously approved source failed revision or approval integrity checks; renewed review required",
                                        "evidence_refs": ["algorithm_requirement_sources/" + doc["source_id"]], "requirement_ids": []})
        for raw in doc.get("requirements", []):
            reference = "algorithm_requirement_sources/" + doc["source_id"] + "/" + raw["id"]
            row = candidate(raw["type"], raw["value"], reference, doc["source_revision"],
                            "AUTHORITATIVE" if trusted else "SUGGESTED", raw.get("scope"),
                            unit=raw.get("unit"), metric=raw.get("metric"), key=raw["key"],
                            description=raw["description"], override_of=raw.get("override_of"),
                            source_fingerprint=doc.get("payload_fingerprint"))
            row["applicability_status"] = applicability(row["scope"], context, dataset_ids)
            if doc.get("status") == "SUPERSEDED" or not trusted and doc.get("status") != "PROPOSED":
                row["exclusion_reason"] = "Superseded or invalid source approval/fingerprint"
                report["excluded"].append(row)
            elif row["applicability_status"] == "NOT_APPLICABLE":
                report["excluded"].append(row)
            else:
                report["established" if trusted else "suggestions"].append(row)
    for row in report["established"]:
        if row.get("override_of"):
            report["conflicts"].append({"reason": "Override has no reviewed conflict-resolution mechanism; cumulative originals remain active",
                                         "evidence_refs": row["evidence_refs"], "requirement_ids": [row["id"]]})
        if row["applicability_status"] == "UNRESOLVED":
            report["conflicts"].append({"reason": "Explicit scope cannot be established", "evidence_refs": row["evidence_refs"], "requirement_ids": [row["id"]]})
    for i, left in enumerate(report["established"]):
        for right in report["established"][i + 1:]:
            if left.get("key") != right.get("key") or left["type"] != right["type"]:
                continue
            a, b = left["scope"].get("dataset_ids", []), right["scope"].get("dataset_ids", [])
            if a and b and not set(a) & set(b):
                continue
            # Upper bounds are cumulative; distinct maxima are not a contradiction.
            if left["type"] in {"MAX_LATENCY", "MAX_MEMORY"}:
                continue
            if fingerprint(left["value"]) != fingerprint(right["value"]):
                report["conflicts"].append({"reason": "Applicable explicit requirements disagree; no later-source preference",
                    "evidence_refs": left["evidence_refs"] + right["evidence_refs"], "requirement_ids": [left["id"], right["id"]]})
    for kind, description in (("MAX_LATENCY", "Production latency acceptance limit is unknown"),
                              ("MAX_MEMORY", "Production peak-memory acceptance limit and metric are unknown"),
                              ("WORKLOAD", "Production workload sizes and frequencies are unknown; tested or required datasets do not establish them")):
        if kind == "WORKLOAD" or not any(r["type"] == kind and r["applicability_status"] == "APPLIES" for r in report["established"]):
            report["unknown"].append({"id": "discovered-" + kind.lower(), "description": description, "status": "UNKNOWN"})
    report["fingerprint"] = fingerprint(report)
    return report


def prepare_policy(policy, report, previous_report=None):
    result = copy.deepcopy(policy or {"id": "discovered-requirements", "version": "1", "objective": "TRADEOFF_ONLY"})
    # Replace only concrete server-imported IDs. The API permits ordinary manual
    # IDs beginning with "discovered-"; a prefix alone is not source provenance.
    imported_ids = set()
    for snapshot in (previous_report or {}, report):
        for row in snapshot.get("established", []):
            if row["type"] in {"MAX_LATENCY", "MAX_MEMORY"}:
                imported_ids.add("discovered-" + row["id"])
            elif row["type"] == "WORKLOAD" or row["type"] == "OUTPUT_BEHAVIOR" and row.get("validated_by_contract"):
                imported_ids.add("discovered-" + row["id"] + "-coverage")
        if snapshot.get("conflicts") or any(r["type"] in {"INPUT_SCHEMA", "OUTPUT_BEHAVIOR"} and not r.get("validated_by_contract") for r in snapshot.get("established", [])):
            imported_ids.add("discovered-unresolved")
    result["constraints"] = [c for c in result.get("constraints", []) if c["id"] not in imported_ids]
    for row in report["established"]:
        if row["type"] == "WORKLOAD" or row["type"] == "OUTPUT_BEHAVIOR" and row.get("validated_by_contract"):
            ids = row["value"]["required_dataset_ids"]
            result["constraints"].append({"id": "discovered-" + row["id"] + "-coverage", "type": "DATASET_COVERAGE",
                "classification": "MANDATORY", "required_dataset_ids": ids, "evaluation_policy": "ALL_REQUIRED",
                "source_reference": row["source_reference"], "applicability": row["applicability_status"]})
            result["required_dataset_ids"] = list(dict.fromkeys([*result.get("required_dataset_ids", []), *ids]))
        if row["type"] not in {"MAX_LATENCY", "MAX_MEMORY"}:
            continue
        result["constraints"].append({"id": "discovered-" + row["id"], "type": row["type"], "classification": "MANDATORY",
            "threshold": row["value"], "metric": row["metric"], "unit": row["unit"],
            "dataset_ids": row["scope"].get("dataset_ids", []),
            "source_reference": row["source_reference"], "applicability": row["applicability_status"],
            "evaluation_policy": "MAX_OBSERVED_INVOCATION" if row["type"] == "MAX_LATENCY" else "OBSERVED_PEAK"})
    blocked = bool(report["conflicts"]) or any(r["type"] in {"INPUT_SCHEMA", "OUTPUT_BEHAVIOR"}
                                              and not r.get("validated_by_contract") for r in report["established"])
    if blocked:
        result["constraints"].append({"id": "discovered-unresolved", "type": "EXPECTED_OUTPUT", "classification": "MANDATORY",
            "evaluation_policy": "ALL_EXPECTED", "source_reference": "requirements/" + report["fingerprint"], "applicability": "UNRESOLVED"})
    known = {r["id"] for snapshot in (previous_report or {}, report) for r in snapshot.get("unknown", [])}
    result["unknown_requirements"] = [r for r in result.get("unknown_requirements", []) if r["id"] not in known]
    result["unknown_requirements"].extend({"id": r["id"], "description": r["description"]} for r in report["unknown"])
    return DecisionPolicy.model_validate(result).model_dump()
