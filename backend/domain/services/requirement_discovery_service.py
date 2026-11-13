"""Narrow, project-scoped adapters over existing MongoDB evidence and configuration.

Only independently reviewed structured sources and approved function contracts can
establish constraints. Descriptions, tests and history remain context. No Ollama
availability or developer-code execution is required.
"""

import copy
import hashlib
import json
import uuid
from core.permissions import Permission, get_user_permissions
from datetime import datetime, timezone

from core.database import col
from domain.schemas.requirement_discovery import RequirementContext, RequirementSourceProposal, RequirementReview
from domain.services.function_contract_service import FunctionContractService, actor
from intelligence.algorithms.decision import fingerprint
from intelligence.algorithms.requirements import candidate, resolve_requirements, prepare_policy, source_content, trusted_source


def bound_report(report):
    if len(json.dumps(report, allow_nan=False).encode()) > 2_000_000:
        raise ValueError("Requirement evidence exceeds the 2 MB report bound; select fewer context references. No partial policy was enforced")
    return report


class RequirementDiscoveryService:
    def __init__(self, database=None, contracts=None):
        self.database = database
        self.contracts = contracts or FunctionContractService(
            database["algorithm_function_contracts"] if database is not None else None,
            database["code_quality_runs"] if database is not None else None)

    def collection(self, name):
        return self.database[name] if self.database is not None else col(name)

    async def propose(self, body, user):
        content = RequirementSourceProposal.model_validate(body).model_dump()
        if not actor(user) or not user.get("org_id"):
            raise PermissionError("Authenticated project identity required")
        if content["supersedes"]:
            previous = await self.get(content["supersedes"])
            if not previous or previous["project_id"] != content["project_id"] or previous["organization_id"] != user["org_id"]:
                raise ValueError("Superseded source must belong to this project and organization")
        document = {**content, "source_id": "RQS-" + uuid.uuid4().hex[:16].upper(), "status": "PROPOSED",
                    "payload_fingerprint": fingerprint(content), "proposed_by": actor(user),
                    "organization_id": user["org_id"], "approval": None,
                    "created_at": datetime.now(timezone.utc).isoformat()}
        await self.collection("algorithm_requirement_sources").create_index("source_id", unique=True)
        await self.collection("algorithm_requirement_sources").insert_one(copy.deepcopy(document))
        return document

    async def get(self, source_id):
        return await self.collection("algorithm_requirement_sources").find_one({"source_id": source_id}, {"_id": 0})

    async def approve(self, document, body, user):
        review = RequirementReview.model_validate(body).model_dump()
        # Approval comes from APPROVE_ENGINEERING_CONTRACTS (not the admin flag, CR-008).
        if (Permission.APPROVE_ENGINEERING_CONTRACTS not in get_user_permissions(
                str(user.get("role", user.get("organizational_role", ""))), False, user.get("designation"))
                or not actor(user) or actor(user) == document["proposed_by"] or not user.get("org_id")
                or user["org_id"] != document["organization_id"]):
            raise PermissionError("Independent authorized review in the same project organization is required")
        expected = review["expected_fingerprint"]
        if document["status"] != "PROPOSED" or expected != document["payload_fingerprint"] or expected != fingerprint(source_content(document)):
            raise ValueError("Reviewed source revision changed or is no longer proposed")
        if document.get("supersedes"):
            old = await self.get(document["supersedes"])
            if not old or not trusted_source(old) or old["project_id"] != document["project_id"]:
                raise ValueError("Only a currently approved source revision can be superseded")
        review.update(approved_by=actor(user), organization_id=user["org_id"], approved_at=datetime.now(timezone.utc).isoformat())
        result = await self.collection("algorithm_requirement_sources").update_one(
            {"source_id": document["source_id"], "status": "PROPOSED", "payload_fingerprint": expected},
            {"$set": {"status": "APPROVED", "approval": review}})
        if result.matched_count != 1:
            raise ValueError("Source was concurrently changed")
        # Supersession is resolved from the new approved revision too. A crash here
        # cannot make both revisions silently compete or discard both originals.
        if document.get("supersedes"):
            await self.collection("algorithm_requirement_sources").update_one(
                {"source_id": document["supersedes"], "status": "APPROVED"},
                {"$set": {"status": "SUPERSEDED", "superseded_by": document["source_id"]}})
        await self.collection("project_configs").update_one({"project_id": document["project_id"]},
            {"$addToSet": {"algorithm_requirement_source_ids": document["source_id"]}}, upsert=True)
        return await self.get(document["source_id"])

    async def discover(self, project_id, context=None, dataset_ids=None):
        context = RequirementContext.model_validate(context or {}).model_dump()
        observations, suggestions, established, limitations = [], [], [], []
        config = await self.collection("project_configs").find_one({"project_id": project_id})
        if config is None:
            limitations.append("Project configuration is absent; code-quality defaults and worker resource limits are not acceptance budgets")
        sources = await self.collection("algorithm_requirement_sources").find({"project_id": project_id}, {"_id": 0}).limit(33).to_list(33)
        if len(sources) > 32:
            raise ValueError("More than 32 source revisions require a narrower project policy; no partial policy was enforced")
        project = await self.collection("projects").find_one({"id": project_id}, {"org_id": 1})
        organization_conflicts = []
        for doc in sources:
            if project and doc.get("organization_id") != project.get("org_id"):
                if doc.get("status") == "APPROVED":
                    organization_conflicts.append("algorithm_requirement_sources/" + doc["source_id"])
                doc["status"] = "ORGANIZATION_MISMATCH"
        superseders = {}
        for doc in sources:
            # A reviewed intermediate revision still establishes supersession
            # history after it is itself replaced. Do not reactivate ancestors
            # if an earlier predecessor status update was interrupted.
            if trusted_source(doc, include_superseded=True) and doc.get("supersedes"):
                superseders.setdefault(doc["supersedes"], []).append(doc["source_id"])
        for doc in sources:
            if doc["source_id"] in superseders and len(superseders[doc["source_id"]]) == 1:
                doc["status"] = "SUPERSEDED"
        resolution = await self.contracts.resolve(project_id, context["contract_ids"])
        snapshot = resolution.get("snapshot")
        if snapshot:
            reference = ",".join(resolution["evidence_refs"])
            revision = resolution["fingerprint"]
            approved = resolution["status"] == "APPROVED"
            for key in ("input_schema", "output_schema"):
                observations.append(candidate("SCHEMA", snapshot["contract"].get(key, {}), reference + "/" + key, revision, "OBSERVED",
                    description="Explicit schema restriction; applicability remains bound to this contract"))
            for d in snapshot["datasets"]:
                observations.append(candidate("TEST_INPUT", {"dataset_id": d["id"], "dimensions": d.get("dimensions", {}),
                    "argument_lengths": [len(a) if isinstance(a, (list, dict, str)) else None for a in d.get("args", [])]},
                    reference + "/datasets/" + d["id"], revision, "OBSERVED", description="Finite test input; no supported maximum or production frequency follows"))
            if approved:
                established.append(candidate("INPUT_SCHEMA", snapshot["contract"]["input_schema"], reference + "/input_schema", revision,
                    "AUTHORITATIVE", key="contract.input_schema", validated_by_contract=resolution["validator_available"], description="Approved functional-contract input schema"))
                established.append(candidate("OUTPUT_BEHAVIOR", {"contract": snapshot["contract"], "requirements": snapshot["requirements"], "required_dataset_ids": snapshot["required_dataset_ids"]},
                    reference, revision, "AUTHORITATIVE", key="contract.output", validated_by_contract=resolution["validator_available"],
                    description="Approved finite contract requirements; compatibility still requires isolated validation"))
                if not resolution["validator_available"]:
                    limitations.append("Approved contract requires an unavailable validator; requirements are established but behavioral validation and eligibility remain unverified")
            else:
                suggestions.append(candidate("FUNCTIONAL_CONTRACT", snapshot["requirements"], reference, revision, "SUGGESTED"))
        if resolution["status"] != "APPROVED":
            limitations.append("Approved applicable functional contract is missing, proposed or conflicting; purpose hypotheses cannot approve one")
        # Exact references are intentionally required. No text similarity or broad
        # project search silently attaches unrelated task acceptance criteria.
        for ids_key, collection, text_fields in (("task_ids", "tasks", ("title",)), ("story_ids", "stories", ("title", "description")),
                                                 ("pr_ids", "pull_requests", ("title", "description"))):
            for source_id in context[ids_key]:
                doc = await self.collection(collection).find_one({"id": source_id, "project_id": project_id}, {"_id": 0})
                if not doc:
                    limitations.append(f"{collection}/{source_id}: source absent or outside project; no requirement imported")
                    continue
                content = {key: doc.get(key) for key in (*text_fields, "head_sha", "updated_at", "repo_id")}
                revision = fingerprint(content)
                if collection == "pull_requests" and (not context["repository"] or doc.get("repo_id") != context["repository"]
                        or context["source_revision"] and doc.get("head_sha") != context["source_revision"]):
                    limitations.append(f"{collection}/{source_id}: repository or source revision applicability is unresolved")
                    continue
                for field in text_fields:
                    text = doc.get(field)
                    if isinstance(text, str) and text.strip():
                        suggestions.append(candidate("CONTEXT_STATEMENT", text[:2000], f"{collection}/{source_id}/{field}", revision,
                            "SUGGESTED", extraction_method="source-quotation-v1", description="Original source quotation; confirmation and explicit implementation scope are required"))
                if collection == "tasks":
                    limitations.append(f"tasks/{source_id}: task model has no acceptance criteria or approval fields")
                    if doc.get("story_id") and doc["story_id"] not in context["story_ids"]:
                        if len(context["story_ids"]) < 8:
                            context["story_ids"].append(doc["story_id"])
                        else:
                            limitations.append("Linked-story context bound reached; additional story evidence was not imported")
                if collection == "pull_requests" and not doc.get("description"):
                    limitations.append(f"pull_requests/{source_id}: PR description is absent; code-review approval does not approve requirements")
        for run_id in context["discovery_run_ids"]:
            run = await self.collection("code_quality_runs").find_one({"run_id": run_id, "repository_id": project_id}, {"_id": 0})
            if not run:
                limitations.append(f"code_quality_runs/{run_id}: discovery source unavailable in project")
                continue
            for source in run.get("function_discovery", {}).get("requirement_sources", [])[:1]:
                for requirement in source.get("requirements", [])[:32]:
                    suggestions.append(candidate(requirement["type"], requirement["value"],
                        f"code_quality_runs/{run_id}/{source['path']}/{requirement['id']}", source.get("source_revision") or source["source_hash"],
                        "SUGGESTED", requirement.get("scope"), unit=requirement.get("unit"), metric=requirement.get("metric"),
                        description="Repository configuration declaration needs independent authorized review", extraction_method="repository-configuration-v1"))
            for fn in run.get("function_discovery", {}).get("functions", [])[:256]:
                if context["function_ids"] and fn["function_id"] not in context["function_ids"]:
                    continue
                observations.append(candidate("FUNCTION_STRUCTURE", {"function_id": fn["function_id"], "patterns": fn.get("detected_patterns", []),
                    "calls": fn.get("calls", [])[:16]}, f"code_quality_runs/{run_id}/functions/{fn['function_id']}", fn.get("source_revision") or fn.get("source_hash"), "OBSERVED",
                    evidence_refs=[e["id"] for e in fn.get("evidence", [])][:32]))
                for hypothesis in fn.get("task_hypotheses", [])[:8]:
                    suggestions.append(candidate("PURPOSE_HYPOTHESIS", hypothesis, f"code_quality_runs/{run_id}/functions/{fn['function_id']}", fn.get("source_hash"), "SUGGESTED"))
        for run_id in context["benchmark_run_ids"]:
            run = await self.collection("algorithm_benchmark_runs").find_one({"run_id": run_id, "project_id": project_id, "status": "completed"}, {"_id": 0})
            if run:
                observations.append(candidate("HISTORICAL_BENCHMARK", {"run_id": run_id, "workload_key": run.get("workload_key"),
                    "environment": run.get("environment", {}), "results": [{"candidate": r.get("candidate"), "cases": r.get("cases", [])[:32]} for r in run.get("results", [])[:5]]},
                    "algorithm_benchmark_runs/" + run_id, fingerprint(run.get("results", [])), "OBSERVED",
                    description="Historical measurements on recorded inputs; not a production acceptance limit or workload frequency"))
        report = resolve_requirements(project_id, context, sources, observations, suggestions, limitations, dataset_ids, established)
        if organization_conflicts:
            report["conflicts"].append({"reason": "Requirement approval does not belong to the project's current organization; renewed authorized review is required",
                                        "evidence_refs": organization_conflicts, "requirement_ids": []})
        for old_id, replacements in superseders.items():
            if len(replacements) > 1:
                report["conflicts"].append({"reason": "Concurrent approved replacements of one source revision require review", "evidence_refs": replacements, "requirement_ids": []})
        if resolution["status"] == "CONFLICTING":
            report["conflicts"].append({"reason": "Functional contract sources conflict", "evidence_refs": resolution["evidence_refs"], "requirement_ids": []})
        report["fingerprint"] = fingerprint({k: v for k, v in report.items() if k != "fingerprint"})
        return bound_report(report)

    async def prepare(self, request):
        request = copy.deepcopy(request)
        context = request.get("requirement_context") or {}
        if "compatibility_context" in request:
            compatibility = request["compatibility_context"]
            context = {**context, "contract_ids": compatibility["resolution"]["contract_ids"]}
            context["function_ids"] = [i["function_reference"]["function_id"] for i in (compatibility["previous"], compatibility["current"]) if i.get("function_reference")]
            context["discovery_run_ids"] = list(dict.fromkeys(i["function_reference"]["run_id"] for i in (compatibility["previous"], compatibility["current"]) if i.get("function_reference")))
        # Bind static identity to the actual submitted bytes. Client-supplied
        # function IDs, repositories and revision labels are not authority.
        configuration = await self.collection("github_project_configs").find_one({"project_id": request["project_id"]})
        context["repository"] = (configuration["repository_owner"] + "/" + configuration["repository_name"]
                                 if configuration and configuration.get("repository_owner") and configuration.get("repository_name") else None)
        matches = []
        bound_candidates = set()
        for run_id in context.get("discovery_run_ids", []):
            run = await self.collection("code_quality_runs").find_one({"run_id": run_id, "repository_id": request["project_id"]})
            discovery = (run or {}).get("function_discovery", {})
            provenance = (run or {}).get("source_provenance", {})
            if (provenance.get("method") != "github-exact-revision" or not context["repository"]
                    or provenance.get("repository") != context["repository"] or not provenance.get("revision")
                    or provenance["revision"] != (run or {}).get("commit_sha")):
                continue
            for fn in discovery.get("functions", []) if discovery.get("method") == "function-purpose-v1" and discovery.get("status") in {"available", "partial"} else []:
                matching_candidates = {c["name"] for c in request["candidates"] if fn.get("source_hash") == hashlib.sha256(c["source"].encode()).hexdigest()
                       and fn.get("source_revision") == provenance["revision"] and fn.get("qualified_name") == c["entrypoint"]
                       and fn.get("name") == c["entrypoint"] and fn.get("language") == request.get("compatibility_context", {}).get("candidate_languages", {}).get(c["name"], request["language"])
                       }
                if matching_candidates:
                    matches.append(fn)
                    bound_candidates.update(matching_candidates)
        complete_scope = bound_candidates == {c["name"] for c in request["candidates"]}
        context["function_ids"] = list(dict.fromkeys(fn["function_id"] for fn in matches))[:8] if complete_scope else []
        revisions = {fn.get("source_revision") for fn in matches}
        context["source_revision"] = next(iter(revisions)) if complete_scope and len(revisions) == 1 else None
        # Functional contracts require explicit references and exact payload matching.
        report = await self.discover(request["project_id"], context, [d["id"] for d in request.get("datasets", [])])
        if context.get("contract_ids"):
            resolution = await self.contracts.resolve(request["project_id"], context["contract_ids"])
            snapshot = resolution.get("snapshot") or {}
            if fingerprint(snapshot.get("contract")) != fingerprint(request.get("contract")):
                report["conflicts"].append({"reason": "Submitted contract differs from the referenced approved contract", "evidence_refs": resolution["evidence_refs"], "requirement_ids": []})
            approved_datasets = {d["id"]: d for d in snapshot.get("datasets", [])}
            if any(d["id"] not in approved_datasets or fingerprint(d) != fingerprint(approved_datasets[d["id"]]) for d in request.get("datasets", [])):
                report["conflicts"].append({"reason": "Submitted inputs, expected outputs or dataset metadata differ from the reviewed validation evidence", "evidence_refs": resolution["evidence_refs"], "requirement_ids": []})
            if snapshot.get("function_bindings") and not any(b["function_id"] in context["function_ids"] for b in snapshot["function_bindings"]):
                report["conflicts"].append({"reason": "Approved function binding is not established by the submitted source evidence", "evidence_refs": resolution["evidence_refs"], "requirement_ids": []})
        if request.get("contract") and not context.get("contract_ids"):
            report["limitations"].append("Submitted manual contract has no approved contract reference; its schema is observed, not approved")
            report["observations"].append(candidate("SCHEMA", request["contract"].get("input_schema", {}), "request/contract/input_schema", fingerprint(request["contract"]), "OBSERVED"))
        for dataset in request.get("datasets", []):
            report["observations"].append(candidate("TEST_INPUT", {"dataset_id": dataset["id"], "dimensions": dataset.get("dimensions", {}),
                "argument_lengths": [len(a) if isinstance(a, (list, dict, str)) else None for a in dataset.get("args", [])]},
                "request/datasets/" + dataset["id"], fingerprint(dataset), "OBSERVED", description="Tested input sizes are not maximum supported sizes"))
        report["fingerprint"] = fingerprint({k: v for k, v in report.items() if k != "fingerprint"})
        policy = request.get("decision_policy") or {"id": "discovered-requirements", "version": "1",
            "objective": "MINIMIZE_MEMORY" if request.get("objective") == "memory" else "MINIMIZE_TIME",
            **({"memory_metric": "memray_peak_tracked_allocations_bytes"} if request.get("objective") == "memory" else {})}
        if request.get("decision_policy") is None and request.get("memory_limit_bytes") is not None:
            policy["constraints"] = [{"id": "legacy-tracked-allocation-limit", "type": "MAX_MEMORY", "classification": "MANDATORY",
                "threshold": request["memory_limit_bytes"], "unit": "bytes", "metric": "memray_peak_tracked_allocations_bytes",
                "evaluation_policy": "OBSERVED_PEAK", "source_reference": "request/memory_limit_bytes", "applicability": "APPLIES"}]
        previous_report = request.get("requirements_discovery") or {}
        previous_input = previous_report.get("policy_input")
        manual_required = list(policy.get("required_dataset_ids", []))
        if previous_input is not None:
            imported_required = {key for row in previous_report.get("established", [])
                if row["type"] == "WORKLOAD" or row["type"] == "OUTPUT_BEHAVIOR" and row.get("validated_by_contract")
                for key in row["value"]["required_dataset_ids"]}
            manual_required = [key for key in manual_required if key not in imported_required or key in previous_input["required_dataset_ids"]]
        # Preserve the original explicit scope so retiring imported coverage does
        # not remove an overlapping manually required check on reevaluation.
        report["policy_input"] = {"required_dataset_ids": manual_required}
        policy = {**policy, "required_dataset_ids": manual_required}
        report["fingerprint"] = fingerprint({k: v for k, v in report.items() if k != "fingerprint"})
        request["decision_policy"] = prepare_policy(policy, report, previous_report)
        request["requirements_discovery"] = bound_report(report)
        return request
