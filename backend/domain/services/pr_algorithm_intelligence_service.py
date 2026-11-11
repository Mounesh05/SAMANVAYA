"""PR integration over existing discovery, compatibility, requirement and job services.

The webhook processor remains the event queue. This bounded background continuation
persists its manifest in code_quality_runs and uses existing benchmark jobs/workers.
It never imports or invokes repository code on the host.
"""

import asyncio
import copy
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

from core.config import settings
from core.database import col
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService, BenchmarkBusy
from domain.services.behavioral_compatibility_service import BehavioralCompatibilityService
from domain.services.requirement_discovery_service import RequirementDiscoveryService
from intelligence.algorithms.decision import fingerprint
from intelligence.algorithms.discovery.service import discover_sources, source_language, safe_relative_path

METHOD = "pr-algorithm-intelligence-v1"
TERMINAL = {"completed", "insufficient_evidence", "unsupported", "failed", "superseded"}
_SLOTS = asyncio.Semaphore(2)
_TASKS = set()
logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


def function_text(source, function):
    return "\n".join(source.splitlines()[function["line"] - 1:function["end_line"]])


def changed_functions(base, head, files, before, after):
    """Exact path/lexical identity; a rename requires GitHub's explicit path mapping."""
    paths = {f["filename"]: f.get("previous_filename", f["filename"]) for f in files
             if f.get("status") != "removed" and isinstance(f.get("filename"), str)}
    previous = {}
    for fn in base["functions"]:
        previous.setdefault((fn["path"], fn["qualified_name"], fn["language"]), []).append(fn)
    current_counts = {}
    for fn in head["functions"]:
        key = (fn["path"], fn["qualified_name"], fn["language"])
        current_counts[key] = current_counts.get(key, 0) + 1
    rows = []
    for fn in head["functions"]:
        if fn["path"] not in paths:
            continue
        matches = previous.get((paths[fn["path"]], fn["qualified_name"], fn["language"]), [])
        old = matches[0] if len(matches) == 1 else None
        if old and function_text(before[old["path"]], old) == function_text(after[fn["path"]], fn):
            continue
        reason = None
        if old is None:
            reason = "Previous implementation with an unambiguous lexical identity is unavailable"
        elif current_counts[(fn["path"], fn["qualified_name"], fn["language"])] != 1:
            reason = "Multiple current declarations share this identity"
        elif fn["is_async"] or old["is_async"] or fn["qualified_name"] != fn["name"] or old["qualified_name"] != old["name"]:
            reason = "Automatic execution currently supports synchronous module-level named functions"
        elif not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]{0,127}", fn["name"]):
            reason = "Entrypoint is not supported by the existing worker protocol"
        rows.append({"current": fn, "previous": old, "unsupported_reason": reason,
                     "relationship": {"status": "PROVISIONAL", "reasons": ["Same repository, explicit base/head revisions, path and lexical identity"],
                                      "limitations": ["Identity does not prove equivalent required behavior"]}})
    return rows


def recommendation_status(run):
    compatibility = (run.get("behavioral_compatibility") or {}).get("status")
    if compatibility == "INCOMPATIBLE":
        return "CORRECTNESS_FAILURE"
    if compatibility != "COMPATIBLE_WITHIN_TESTED_CONTRACT":
        return "INSUFFICIENT_EVIDENCE"
    decision = run.get("decision") or {}
    task = decision.get("task_suitability", {}).get("status")
    if task in {"INSUFFICIENT_EVIDENCE", "REQUIREMENT_CONFLICT"}:
        return "INSUFFICIENT_EVIDENCE"
    if task == "NO_ELIGIBLE_IMPLEMENTATION":
        return "CONSTRAINT_FAILURE"
    return "CONDITIONAL_FINDING" if decision.get("unknown_requirements") or task == "CONDITIONAL_COMPARISON" else "VERIFIED_WITHIN_TESTED_WORKLOADS"


class PRAlgorithmIntelligenceService:
    def __init__(self, api, database=None, benchmarks=None, enabled=None):
        self.api, self.database = api, database
        self.requirements = RequirementDiscoveryService(database)
        self.contracts = self.requirements.contracts
        self.benchmarks = benchmarks or AlgorithmBenchmarkService(
            self.collection("algorithm_benchmark_runs"), requirements=self.requirements)
        self.compatibility = BehavioralCompatibilityService(self.benchmarks, self.contracts)
        self.enabled = enabled

    def collection(self, name):
        return self.database[name] if self.database is not None else col(name)

    async def authority(self, project_id, repository):
        owner, name = repository.split("/")
        project = await self.collection("projects").find_one({"id": project_id})
        configs = await self.collection("github_project_configs").find({"repository_owner": owner, "repository_name": name}).limit(2).to_list(2)
        if (not project or not project.get("org_id") or project.get("status", "active") != "active"
                or len(configs) != 1 or configs[0]["project_id"] != project_id):
            raise PermissionError("Automatic analysis requires one exact connected repository and an active project organization")
        return {"employee_id": "github-automation:" + project_id, "org_id": project["org_id"], "role": "DEVOPS",
                "authority_basis": "server-resolved connected project; approved functional scope; existing worker execution feature flag"}

    async def enqueue(self, project_id, repository, pr, files, pr_id, launch=True):
        await self.authority(project_id, repository)
        base, head = pr.get("base", {}).get("sha"), pr.get("head", {}).get("sha")
        if not base or not head or pr.get("state") != "open":
            return {"status": "unsupported", "reason": "Open PR with immutable base and head revisions is required"}
        key = hashlib.sha256(str([METHOD, project_id, repository, pr["number"], base, head]).encode()).hexdigest()
        run_id = "PRI-" + key[:24].upper()
        runs = self.collection("code_quality_runs")
        await runs.create_index("algorithm_job_key", unique=True, sparse=True)
        doc = {"run_id": run_id, "algorithm_job_key": key, "kind": "pr_algorithm_intelligence", "method": METHOD,
               "repository_id": project_id, "project_id": project_id, "repository": repository, "pr_id": pr_id,
               "pr_number": pr["number"], "base_sha": base, "head_sha": head, "commit_sha": head,
               "created_at": now(), "lease_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=8)).isoformat(),
               "status": "pending", "functions": [], "evidence_refs": [], "limitations": [
                   "Finite approved contracts only; no universal equivalence or production-optimality claim",
                   "Background continuation uses the existing local executor; expired jobs fail without replaying code",
                   "Module dependencies must already exist in the pinned worker image; repository code is never installed",
                   "Only changed function bodies with exact lexical relationships are eligible; dynamic and unchanged caller behavior remains uncertain"],
               "files": [{k: f[k] for k in ("filename", "previous_filename", "status") if k in f} for f in files[:100]],
               "input_truncated": len(files) > 100 or pr.get("changed_files", len(files)) > len(files)}
        try:
            await runs.insert_one(copy.deepcopy(doc))
        except DuplicateKeyError:
            existing = await runs.find_one({"algorithm_job_key": key}, {"_id": 0})
            return {"run_id": run_id, "status": existing["status"], "duplicate": True}
        await self.collection("pull_requests").update_one({"id": pr_id, "project_id": project_id, "head_sha": head},
            {"$set": {"algorithm_intelligence_run_id": run_id, "algorithm_intelligence_status": "pending"}})
        await self.collection("recommendations").update_many({"entity_id": pr_id, "project_id": project_id,
            "generated_by": METHOD, "head_sha": {"$ne": head}}, {"$set": {"status": "obsolete", "historical_only": True}})
        if launch:
            task = asyncio.create_task(self.execute(run_id))
            _TASKS.add(task)
            task.add_done_callback(_TASKS.discard)
        return {"run_id": run_id, "status": "pending"}

    async def fresh(self, doc):
        owner, repo = doc["repository"].split("/")
        current = await self.api.client.get_pull_request(owner, repo, doc["pr_number"])
        return (current.get("state") == "open" and current.get("head", {}).get("sha") == doc["head_sha"]
                and current.get("base", {}).get("sha") == doc["base_sha"])

    async def set_status(self, doc, status, **fields):
        await self.collection("code_quality_runs").update_one({"run_id": doc["run_id"]}, {"$set": {"status": status, **fields}})
        await self.collection("pull_requests").update_one(
            {"id": doc["pr_id"], "project_id": doc["project_id"], "head_sha": doc["head_sha"], "algorithm_intelligence_run_id": doc["run_id"]},
            {"$set": {"algorithm_intelligence_status": status}})

    async def snapshot(self, doc, revision, files):
        owner, repo = doc["repository"].split("/")
        sources, diagnostics = await self.api.fetch_analysis_sources(owner, repo, files, revision, include_context=True)
        discovery = (await discover_sources(sources, doc["project_id"], revision, diagnostics)).model_dump(mode="json")
        run_id = doc["run_id"] + ("-base" if revision == doc["base_sha"] else "-head")
        await self.collection("code_quality_runs").update_one({"run_id": run_id}, {"$setOnInsert": {
            "run_id": run_id, "repository_id": doc["project_id"], "commit_sha": revision, "status": "completed", "created_at": now(),
            "source_provenance": {"method": "github-exact-revision", "repository": doc["repository"], "revision": revision},
            "function_discovery": discovery}}, upsert=True)
        return run_id, discovery, sources

    async def resolve_contracts(self, doc, pair, base_run):
        matches = []
        records = await self.contracts.collection.find({"project_id": doc["project_id"], "status": "APPROVED"}, {"_id": 0}).limit(101).to_list(101)
        if len(records) > 100:
            return [], "Approved-contract search bound exceeded; no arbitrary contract was selected"
        for contract in records:
            if contract.get("organization_id") != doc["organization_id"]:
                continue
            scope = contract.get("automatic_scope")
            found = scope == {"repository": doc["repository"], "path": pair["current"]["path"], "qualified_name": pair["current"]["qualified_name"]}
            # Existing reviewed Phase 3 bindings can authorize this exact base source.
            for binding in contract.get("function_bindings", []):
                snapshot = await self.collection("code_quality_runs").find_one({"run_id": binding["run_id"], "repository_id": doc["project_id"]})
                provenance = (snapshot or {}).get("source_provenance", {})
                if provenance.get("method") != "github-exact-revision" or provenance.get("repository") != doc["repository"]:
                    continue
                for fn in snapshot.get("function_discovery", {}).get("functions", []):
                    if (fn["function_id"] == binding["function_id"] and pair["previous"] and all(fn.get(k) == pair["previous"].get(k) for k in ("source_hash", "path", "qualified_name", "language"))):
                        found = True
            if found:
                resolution = await self.contracts.resolve(doc["project_id"], [contract["contract_id"]])
                if resolution["status"] == "APPROVED":
                    matches.append(contract)
        if len(matches) != 1:
            return matches, "No uniquely applicable approved functional contract; names and inferred purpose cannot supply one"
        return matches, None

    async def publish_recommendation(self, doc, row, run):
        status = recommendation_status(run)
        rec_id = "REC-" + hashlib.sha256((doc["run_id"] + row["current"]["function_id"]).encode()).hexdigest()[:24].upper()
        decision = run.get("decision") or {}
        value = {"id": rec_id, "entity_type": "pr", "entity_id": doc["pr_id"], "project_id": doc["project_id"],
                 "title": f"Algorithm analysis: {row['current']['qualified_name']} — {status}",
                 "description": "Fresh base/head validation and deterministic comparisons on the approved finite datasets",
                 "action": "Review correctness, applicable constraints and workload evidence before considering a replacement",
                 "category": "performance", "priority": "high" if status in {"CORRECTNESS_FAILURE", "CONSTRAINT_FAILURE"} else "info",
                 "reasoning": "Phase 1 deterministic policy; Phase 3 compatibility; Phase 4 requirements provenance",
                 "confidence": None, "target_roles": ["DEVELOPER", "LEAD", "QA", "DEVOPS"], "status": "pending",
                 "generated_by": METHOD, "generated_at": now(), "head_sha": doc["head_sha"], "algorithm_analysis_run_id": doc["run_id"],
                 "finding_status": status, "benchmark_run_id": run["run_id"], "evidence_ids": [doc["run_id"], run["run_id"]],
                 "algorithm_summary": {"compatibility": run.get("behavioral_compatibility", {}).get("status"),
                     "task_suitability": decision.get("task_suitability"), "dataset_comparisons": decision.get("dataset_comparisons", [])}}
        await self.collection("recommendations").update_one({"id": rec_id}, {"$setOnInsert": value}, upsert=True)
        current = await self.collection("pull_requests").find_one({"id": doc["pr_id"], "head_sha": doc["head_sha"], "algorithm_intelligence_run_id": doc["run_id"]})
        if not current:
            await self.collection("recommendations").update_one({"id": rec_id}, {"$set": {"status": "obsolete", "historical_only": True}})
        return rec_id, status

    async def execute(self, run_id):
        doc = None
        try:
            async with _SLOTS:
                doc = await self.collection("code_quality_runs").find_one_and_update(
                    {"run_id": run_id, "status": "pending", "lease_expires_at": {"$gt": now()}}, {"$set": {"status": "analyzing"}})
                if not doc:
                    return
                await asyncio.wait_for(self._analyze(doc), timeout=360)
        except asyncio.CancelledError:
            if doc:
                await self.set_status(doc, "failed", error="Automatic analysis was cancelled; no replacement claim was published", completed_at=now())
            raise
        except Exception as error:
            logger.exception("PR algorithm analysis failed: %s", run_id)
            if doc:
                await self.set_status(doc, "failed", error=type(error).__name__ + ": automatic analysis could not complete safely", completed_at=now())

    async def _analyze(self, doc):
        user = await self.authority(doc["project_id"], doc["repository"])
        doc["organization_id"] = user["org_id"]
        if not await self.fresh(doc):
            await self.set_status(doc, "superseded", completed_at=now())
            return
        files = [f for f in doc["files"] if source_language(f["filename"]) and safe_relative_path(f["filename"])]
        if not files:
            await self.set_status(doc, "unsupported", reason="No supported Python, JavaScript or TypeScript source changes", completed_at=now())
            return
        old_files = [{**f, "filename": f.get("previous_filename", f["filename"]), "status": "modified"} for f in files if f.get("status") != "added"]
        base_run, base, before = await self.snapshot(doc, doc["base_sha"], old_files)
        head_run, head, after = await self.snapshot(doc, doc["head_sha"], files)
        pairs = changed_functions(base, head, files, before, after)
        await self.set_status(doc, "analyzing", base_discovery_run_id=base_run, head_discovery_run_id=head_run,
                              function_discovery=head, evidence_refs=[base_run, head_run], organization_id=user["org_id"])
        rows, recommendations, executed = [], [], 0
        if not pairs:
            await self.set_status(doc, "unsupported", reason="No changed function body could be extracted; inspect source diagnostics and module/caller changes", completed_at=now())
            return
        for pair in pairs[:64]:
            def identity(fn):
                return {k: copy.deepcopy(fn.get(k)) for k in ("function_id", "path", "qualified_name", "name", "language", "source_hash", "source_revision", "is_async", "detected_patterns", "task_hypotheses")}
            row = {"current": identity(pair["current"]), "previous": identity(pair["previous"]) if pair["previous"] else None,
                   "relationship": pair["relationship"]}
            row.update(status="unsupported", evidence_refs=[base_run, head_run])
            rows.append(row)
            if pair["unsupported_reason"]:
                row["reason"] = pair["unsupported_reason"]
                continue
            contracts, reason = await self.resolve_contracts(doc, pair, base_run)
            if reason:
                row.update(status="insufficient_evidence", reason=reason, contract_ids=[c["contract_id"] for c in contracts])
                continue
            contract = contracts[0]
            row["contract_id"] = contract["contract_id"]
            row["datasets"] = [{"id": d["id"], "fingerprint": fingerprint(d), "contract_version": contract["contract"]["version"],
                "input_characteristics": {"declared_dimensions": d.get("dimensions", {}), "arguments": [
                    {"type": type(arg).__name__, **({"length": len(arg)} if isinstance(arg, (list, dict, str)) else {})} for arg in d.get("args", [])]},
                "expected_output_method": contract["contract"].get("comparison", {"mode": "exact"}),
                "source_reference": "algorithm_function_contracts/" + contract["contract_id"], "validation_status": "APPROVED_FIXTURE"} for d in contract["datasets"]]
            if not (self.enabled if self.enabled is not None else settings.ALGORITHM_BENCHMARK_ENABLED):
                row.update(status="unsupported", reason="Existing administrator benchmark execution flag is disabled")
                continue
            if executed >= 4:
                row.update(status="insufficient_evidence", reason="Automatic comparison budget reached; static findings retained")
                continue
            if not await self.fresh(doc):
                await self.set_status(doc, "superseded", functions=rows, completed_at=now())
                return
            def candidate(fn, source, label, discovery_run):
                return {"name": label, "source": source[fn["path"]], "entrypoint": fn["name"], "language": fn["language"],
                        "function_reference": {"run_id": discovery_run, "function_id": fn["function_id"]}}
            body = {"project_id": doc["project_id"], "contract_ids": [contract["contract_id"]],
                "previous": candidate(pair["previous"], before, "previous", base_run), "current": candidate(pair["current"], after, "current", head_run),
                "repetitions": 5, "resources": {"cpus": 1, "memory_bytes": 536870912, "pids": 64, "timeout_seconds": 45},
                "decision_policy": {"id": "automatic-pr-workloads", "version": "1", "objective": "MINIMIZE_TIME", "required_dataset_ids": contract["required_dataset_ids"]},
                "requirement_context": {"pr_ids": [doc["pr_id"]]}}
            pr_context = await self.collection("pull_requests").find_one({"id": doc["pr_id"], "project_id": doc["project_id"]}) or {}
            text = (pr_context.get("title") or "") + " " + (pr_context.get("description") or "")
            for key, prefix in (("task_ids", "TASK"), ("story_ids", "STORY")):
                body["requirement_context"][key] = list(dict.fromkeys(re.findall(r"\b" + prefix + r"-[A-Za-z0-9]+\b", text)))[:8]
            try:
                created = await self.compatibility.create(body, user, metadata={"pr_automation": {"run_id": doc["run_id"], "repository": doc["repository"],
                    "pr_id": doc["pr_id"], "base_sha": doc["base_sha"], "head_sha": doc["head_sha"], "method": METHOD}})
            except BenchmarkBusy:
                row.update(status="insufficient_evidence", reason="Existing project benchmark concurrency slot is occupied; no parallel bypass was attempted")
                continue
            executed += 1
            child = await self.benchmarks.get(created["run_id"])
            row["benchmark_run_id"] = child["run_id"]
            report = child.get("requirements_discovery", {})
            if created["status"] == "pending" and (report.get("conflicts") or any(c.get("applicability") == "UNRESOLVED" for c in child["request"]["decision_policy"]["constraints"])):
                await self.benchmarks._finish(child["run_id"], {"status": "completed", "error": "Applicable requirement or validator is unresolved; automatic execution skipped"})
                row.update(status="insufficient_evidence", reason="Requirements need resolution before automatic execution", requirements_discovery=report)
                continue
            if created["status"] == "pending":
                await self.set_status(doc, "benchmarking", functions=rows)
                await self.benchmarks.execute(child["run_id"])
            child = await self.benchmarks.get(child["run_id"])
            if not await self.fresh(doc):
                await self.set_status(doc, "superseded", functions=rows, completed_at=now())
                return
            if child["status"] != "completed":
                row.update(status="failed", reason=child.get("error") or "Isolated worker did not complete")
                continue
            row.update(status="completed" if child.get("behavioral_compatibility", {}).get("phase1_eligible") else "insufficient_evidence",
                       compatibility=child.get("behavioral_compatibility", {}).get("status"), evidence_refs=[base_run, head_run, child["run_id"]])
            rec_id, finding = await self.publish_recommendation(doc, row, child)
            row["finding_status"] = finding
            recommendations.append(rec_id)
        if not await self.fresh(doc):
            await self.set_status(doc, "superseded", functions=rows, completed_at=now())
            return
        status = "completed" if any(r["status"] == "completed" or r.get("finding_status") == "CORRECTNESS_FAILURE" for r in rows) else "failed" if any(r["status"] == "failed" for r in rows) else "insufficient_evidence" if any(r["status"] == "insufficient_evidence" for r in rows) else "unsupported"
        await self.set_status(doc, status, functions=rows, recommendation_ids=recommendations, completed_at=now(),
                              analysis_truncated=doc.get("input_truncated") or len(pairs) > 64)

    async def get(self, run_id):
        await self.collection("code_quality_runs").update_many(
            {"kind": "pr_algorithm_intelligence", "status": {"$nin": list(TERMINAL)}, "lease_expires_at": {"$lt": now()}},
            {"$set": {"status": "failed", "error": "Local analysis lease expired; results are not automatically replayed", "completed_at": now()}})
        return await self.collection("code_quality_runs").find_one({"run_id": run_id, "kind": "pr_algorithm_intelligence"}, {"_id": 0})
