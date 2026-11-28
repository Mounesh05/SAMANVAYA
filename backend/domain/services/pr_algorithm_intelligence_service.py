"""PR integration over existing discovery, compatibility, requirement and job services.

The webhook processor remains the event queue. This bounded background continuation
persists its manifest in code_quality_runs and uses existing benchmark jobs/workers.
It never imports or invokes repository code on the host.
"""

import asyncio
import ast
import copy
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from pymongo.errors import DuplicateKeyError

from core.config import settings
from core.database import col
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService, BenchmarkBusy
from domain.services.behavioral_compatibility_service import BehavioralCompatibilityService
from domain.services.requirement_discovery_service import RequirementDiscoveryService
from intelligence.algorithms.decision import fingerprint
from intelligence.algorithms.discovery import complexity
from intelligence.algorithms.discovery.classification import NESTED, TEST, TEST_HELPER, classify
from intelligence.algorithms.discovery.service import discover_sources, source_language, safe_relative_path

METHOD = "pr-algorithm-intelligence-v1"
ANALYSIS_REVISION = "authority-lifecycle-v3"
TERMINAL = {"completed", "insufficient_evidence", "unsupported", "failed", "superseded"}
_SLOTS = asyncio.Semaphore(2)
_TASKS = set()
logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


async def expire_pr_jobs(runs, prs, run_id=None, project_ids=None):
    """Expire manifests and their matching PR cache with a guarded state change."""
    query = {"kind": "pr_algorithm_intelligence", "status": {"$nin": list(TERMINAL)}, "lease_expires_at": {"$lt": now()}}
    if run_id is not None:
        query["run_id"] = run_id
    if project_ids is not None:
        query["project_id"] = {"$in": project_ids}
    expired = await runs.find(query, {"_id": 0, "run_id": 1, "pr_id": 1, "project_id": 1, "head_sha": 1}).limit(100).to_list(100)
    for doc in expired:
        outcome = await runs.update_one({**query, "run_id": doc["run_id"]}, {"$set": {
            "status": "failed", "error": "Local analysis lease expired; execution was not replayed", "completed_at": now()}})
        if outcome.matched_count:
            await prs.update_one({"id": doc["pr_id"], "project_id": doc["project_id"], "head_sha": doc["head_sha"],
                "algorithm_intelligence_run_id": doc["run_id"]}, {"$set": {"algorithm_intelligence_status": "failed"}})


def function_text(source, function):
    lines = source.splitlines()[(function.get("definition_line") or function["line"]) - 1:function["end_line"]]
    if not lines or function.get("end_column") is None:
        return "\n".join(lines)  # Legacy snapshots do not have precise end columns.
    # Python AST columns count UTF-8 bytes; the TypeScript compiler counts UTF-16
    # code units. Slicing decoded text with either index misidentifies Unicode.
    encoding, width = ("utf-8", 1) if function["language"] == "python" else ("utf-16-le", 2)
    start, end = function.get("column", 0) * width, function["end_column"] * width
    if len(lines) == 1:
        lines[0] = lines[0].encode(encoding)[start:end].decode(encoding)
    else:
        lines[0] = lines[0].encode(encoding)[start:].decode(encoding)
        lines[-1] = lines[-1].encode(encoding)[:end].decode(encoding)
    return "\n".join(lines)


def automatic_candidate_reason(function):
    category = classify(function["path"], function["qualified_name"], function["name"])["category"]
    if category in {TEST, TEST_HELPER, NESTED}:
        return "Test code and nested definitions are retained as static context"
    if function["is_async"] or function["qualified_name"] != function["name"]:
        return "Automatic execution currently supports synchronous module-level named functions"
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]{0,127}", function["name"]):
        return "Entrypoint is not supported by the existing worker protocol"
    return None


def changed_functions(base, head, files, before, after):
    """Exact path/lexical identity; a rename requires GitHub's explicit path mapping.

    Every changed function is returned with a comparison mode:

    * ``B`` — a previous implementation with an unambiguous lexical identity exists
      at the base revision, so a base-versus-head replacement can be considered.
    * ``A`` — no previous implementation exists at these revisions. The function is
      still analysed statically; only the *comparison* is unavailable.

    ``unsupported_reason`` therefore describes the comparison, never the analysis.
    """
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
        mode = "B" if old is not None else "A"
        reason = None
        candidate_reason = automatic_candidate_reason(fn)
        if current_counts[(fn["path"], fn["qualified_name"], fn["language"])] != 1:
            candidate_reason = "Multiple current declarations share this identity"
        if candidate_reason:
            reason = candidate_reason
        elif old is None:
            reason = "No previous implementation exists at these revisions, so a base-versus-head comparison cannot be formed"
        else:
            reason = automatic_candidate_reason(old)
        if mode == "B":
            relationship = {"status": "PROVISIONAL",
                            "reasons": ["Same repository, explicit base/head revisions, path and lexical identity"],
                            "limitations": ["Identity does not prove equivalent required behavior"]}
        else:
            relationship = {"status": "PROVISIONAL",
                            "reasons": ["New or renamed declaration at the head revision; no base counterpart is claimed"],
                            "limitations": ["Absence of a base counterpart does not establish novelty, renaming or required behavior",
                                            "Static findings for this function are independent of any comparison"]}
        rows.append({"current": fn, "previous": old, "mode": mode, "unsupported_reason": reason,
                     "candidate_eligible": candidate_reason is None,
                     "relationship": relationship})
    return rows


def same_revision_alternatives(rows):
    """Functions one static assertion compares with each other are Mode C candidates.

    v4 AL-16: an assertion that compares two distinct changed functions as equals
    (``assert f(x) == g(x)``, ``expect(f(x)).toEqual(g(x))``) is structural evidence
    that the author treats them as interchangeable answers to the same requirement.
    Merely appearing in one assertion is not: composition (``f(g(x))``), round
    trips and unrelated checks joined with ``and`` are never paired. Both sides
    must name each other at the same assertion site. Nothing about chronology or
    superiority is implied.
    """
    ids = {row["current"]["function_id"] for row in rows}
    compared: set[tuple] = set()
    for row in rows:
        me = row["current"]["function_id"]
        for evidence in row["current"].get("evidence", []):
            if evidence.get("kind") != "test_expectation":
                continue
            key = (evidence.get("path"), evidence.get("line"))
            peer = evidence.get("related")
            if key[0] is None or key[1] is None or peer not in ids or peer == me:
                continue
            compared.add((me, peer, key))
    links: dict[str, dict[str, list]] = {}
    for left, right, key in compared:
        if (right, left, key) in compared:
            links.setdefault(left, {}).setdefault(right, []).append(key)
    return links


def apply_same_revision_alternatives(pairs):
    """Upgrade eligible Mode A rows to Mode C using one shared static assertion.

    Each function is claimed at most once so a single pair of declarations is
    never benchmarked twice.
    """
    links = same_revision_alternatives(pairs)
    by_id = {row["current"]["function_id"]: row for row in pairs}
    claimed: set[str] = set()
    for pair in pairs:
        if pair["mode"] != "A" or not pair["candidate_eligible"]:
            continue
        current_id = pair["current"]["function_id"]
        if current_id in claimed:
            continue
        for other_id in sorted(links.get(current_id) or {}):
            other = by_id.get(other_id)
            if (other is None or other["mode"] != "A" or not other["candidate_eligible"]
                    or other["current"]["language"] != pair["current"]["language"] or other_id in claimed):
                continue
            shared = sorted(set(links[current_id][other_id]))
            pair["mode"] = "C"
            pair["previous"] = other["current"]
            pair["unsupported_reason"] = None
            pair["relationship"] = {
                "status": "PROVISIONAL",
                "reasons": ["Both candidates are declared in the same head revision",
                            "One static assertion references both declarations",
                            "Shared assertion sites: " + ", ".join(f"{path}:{line}" for path, line in shared)],
                "limitations": ["Both candidates come from the same revision; the previous/current labels "
                                "establish neither chronology nor superiority",
                                "A shared assertion shows the author treats the declarations as interchangeable, "
                                "not that either one is correct",
                                "Approved contract validation is required before any execution"],
            }
            other["relationship"] = {**other["relationship"], "limitations": [
                *other["relationship"]["limitations"],
                f"This declaration is the alternative candidate in a same-revision comparison recorded on "
                f"{pair['current']['qualified_name']}"]}
            claimed.add(current_id)
            claimed.add(other_id)
            break
    return pairs


def _function_node(source, function):
    """Locate the definition node for a discovered function. Parsing only, never execution."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, MemoryError):
        return None
    wanted_line = function.get("definition_line") or function.get("line")
    wanted_name = function.get("name")
    candidates = [node for node in ast.walk(tree)
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                  and getattr(node, "lineno", None) == wanted_line]
    if not candidates:
        return None
    if wanted_name == "<lambda>":
        for node in candidates:
            if isinstance(node, ast.Lambda):
                return node
    elif wanted_name:
        for node in candidates:
            if getattr(node, "name", None) == wanted_name:
                return node
    return candidates[0]


def static_findings(function, source):
    """Static analysis for one function: structure, classification and complexity.

    This runs for every changed function regardless of whether a comparison is
    possible, so a function with no predecessor still produces auditable findings.
    """
    record = {
        "status": "not_analyzed", "method": METHOD,
        "patterns": [p.get("kind") for p in function.get("detected_patterns") or []],
        "task_status": function.get("task_status"),
        "task_hypotheses": [h.get("kind") for h in function.get("task_hypotheses") or []],
        "requirement_evidence_refs": list(function.get("requirement_evidence_refs") or []),
        "callers": list(function.get("callers") or []),
        "test_expectations": [{"path": e.get("path"), "line": e.get("line"), "detail": e.get("detail")}
                              for e in function.get("evidence") or [] if e.get("kind") == "test_expectation"],
        "classification": None, "complexity": None, "limitations": [],
    }
    if not source:
        record["limitations"].append("Source text for this revision was not available; no static analysis was performed.")
        return record
    language = function.get("language") or "python"
    facts = [SimpleNamespace(**e) for e in (function.get("evidence") or [])]
    node = _function_node(source, function) if language == "python" else None
    annotations = {}
    if node is not None:
        args = getattr(node, "args", None)
        if args is not None:
            for argument in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                annotations[argument.arg] = ast.unparse(argument.annotation) if argument.annotation else ""
    try:
        parser_cost = (function.get("structure") or {}).get("static_cost") if language != "python" else None
        # Discovery output never carries confidence; the analysis record derives it
        # from the parser's own status (estimated -> medium, otherwise none).
        record["complexity"] = ({**parser_cost, "language": language,
                                 "confidence": "medium" if parser_cost.get("status") == "estimated" else "none"}
                                if parser_cost else
                                complexity.estimate(node, function.get("name") or "", facts=facts,
                                                    parameter_annotations=annotations, language=language))
    except Exception:  # pragma: no cover - defensive; a bound is never guessed
        record["complexity"] = complexity.estimate(None, function.get("name") or "", facts=[],
                                                   parameter_annotations={}, language=language)
        record["limitations"].append("Static complexity estimation could not complete; no bound is claimed.")
    if language == "python" and node is None:
        record["limitations"].append("The definition could not be located in the stored source, so no complexity bound is claimed.")
    if language != "python" and not (function.get("structure") or {}).get("static_cost"):
        record["limitations"].append("The source-only parser did not return a supported cost analysis; no bound is claimed.")
    record["classification"] = classify(function.get("path"), function.get("qualified_name"),
                                        function.get("name"), language, patterns=record["patterns"],
                                        complexity=record["complexity"])
    record["status"] = "analyzed"
    return record


def run_status(rows):
    """Terminal run status from per-row outcomes.

    A run is only ``unsupported`` when nothing could be analysed or compared.
    Static findings without a possible comparison are a completed analysis, and a
    comparison blocked by a missing approved contract is insufficient evidence.
    """
    statuses = {row.get("status") for row in rows}
    if "failed" in statuses:
        return "failed"
    if any(row.get("finding_status") == "CORRECTNESS_FAILURE" for row in rows) or "completed" in statuses:
        return "completed"
    if "insufficient_evidence" in statuses:
        return "insufficient_evidence"
    if statuses <= {"analyzed", "unsupported"}:
        return "completed" if "analyzed" in statuses else "unsupported"
    return "unsupported"


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

    async def enqueue(self, project_id, repository, pr, files, pr_id, launch=True, expected_run_id=None):
        user = await self.authority(project_id, repository)
        base, head = pr.get("base", {}).get("sha"), pr.get("head", {}).get("sha")
        if not base or not head or pr.get("state") != "open":
            return {"status": "unsupported", "reason": "Open PR with immutable base and head revisions is required"}
        identity = [METHOD, ANALYSIS_REVISION, project_id, repository, pr["number"], base, head]
        # A new approval can unblock an unchanged PR. Draft contracts do not invalidate a job.
        approvals = await self.contracts.collection.find(
            {"project_id": project_id, "organization_id": user["org_id"], "status": "APPROVED",
             "$or": [{"automatic_scope.repository": repository}, {"function_bindings.0": {"$exists": True}}]},
            {"_id": 0, "contract_id": 1, "payload_fingerprint": 1},
        ).sort("contract_id", 1).limit(101).to_list(101)
        if approvals:
            identity.append(fingerprint(approvals))
        requirement_approvals = await self.collection("algorithm_requirement_sources").find(
            {"project_id": project_id, "organization_id": user["org_id"], "status": "APPROVED"},
            {"_id": 0, "source_id": 1, "payload_fingerprint": 1},
        ).sort("source_id", 1).limit(33).to_list(33)
        if requirement_approvals:
            identity.append(fingerprint(requirement_approvals))
        # Revocation is distinct from the original no-approval state.
        revoked_contracts = await self.contracts.collection.find(
            {"project_id": project_id, "organization_id": user["org_id"], "status": "REVOKED"},
            {"_id": 0, "contract_id": 1, "payload_fingerprint": 1}).sort("contract_id", 1).limit(101).to_list(101)
        revoked_sources = await self.collection("algorithm_requirement_sources").find(
            {"project_id": project_id, "organization_id": user["org_id"], "status": "REVOKED"},
            {"_id": 0, "source_id": 1, "payload_fingerprint": 1}).sort("source_id", 1).limit(33).to_list(33)
        identity.extend([fingerprint(revoked_contracts), fingerprint(revoked_sources)])
        key = hashlib.sha256(str(identity).encode()).hexdigest()
        run_id = "PRI-" + key[:24].upper()
        runs = self.collection("code_quality_runs")
        await runs.create_index("algorithm_job_key", unique=True, sparse=True)
        doc = {"run_id": run_id, "algorithm_job_key": key, "kind": "pr_algorithm_intelligence", "method": METHOD,
               "approved_contracts": approvals, "approved_requirement_sources": requirement_approvals,
               "organization_id": user["org_id"],
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
        current_filter = {"id": pr_id, "project_id": project_id, "head_sha": head}
        if expected_run_id:
            current_filter.update(status="open", algorithm_intelligence_run_id=expected_run_id)
        attached = await self.collection("pull_requests").update_one(current_filter,
            {"$set": {"algorithm_intelligence_run_id": run_id, "algorithm_intelligence_status": "pending"}})
        if expected_run_id and attached.matched_count != 1:
            await runs.update_one({"run_id": run_id, "status": "pending"},
                                  {"$set": {"status": "superseded", "completed_at": now()}})
            return {"run_id": run_id, "status": "superseded"}
        await self.collection("recommendations").update_many({"entity_id": pr_id, "project_id": project_id,
            "generated_by": METHOD, "head_sha": {"$ne": head}}, {"$set": {"status": "obsolete", "historical_only": True}})
        if launch:
            task = asyncio.create_task(self.execute(run_id))
            _TASKS.add(task)
            task.add_done_callback(_TASKS.discard)
        return {"run_id": run_id, "status": "pending"}

    async def resume_after_approval(self, approved, launch=True):
        """Bounded continuation of current blocked PRs, using new immutable jobs."""
        project_id = approved["project_id"]
        organization_id = approved["organization_id"]
        scope = approved.get("automatic_scope")
        is_contract = bool(approved.get("contract_id"))
        # Legacy binding-only contracts remain available to regular PR sync.
        if is_contract and not scope:
            return []
        query = {"kind": "pr_algorithm_intelligence", "project_id": project_id,
                 "organization_id": organization_id, "status": {"$in": ["completed", "insufficient_evidence", "unsupported"]}}
        if scope:
            query["repository"] = scope["repository"]
        docs = await self.collection("code_quality_runs").find(query, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
        queued = []
        for doc in docs:
            if len(queued) >= 10:
                break
            blocked = [row for row in doc.get("functions", []) if row.get("comparison_status") == "blocked"
                       or row.get("benchmark_status") == "blocked"]
            if scope:
                blocked = [row for row in blocked if (row.get("current") or {}).get("path") == scope["path"]
                           and (row.get("current") or {}).get("qualified_name") == scope["qualified_name"]]
            if not blocked:
                continue
            current = await self.collection("pull_requests").find_one(
                {"id": doc["pr_id"], "project_id": project_id, "status": "open",
                 "head_sha": doc["head_sha"], "algorithm_intelligence_run_id": doc["run_id"]})
            if not current:
                continue
            try:
                actor = await self.authority(project_id, doc["repository"])
                if actor["org_id"] != organization_id:
                    continue
                owner, name = doc["repository"].split("/")
                pr = await self.api.client.get_pull_request(owner, name, doc["pr_number"])
                if (pr.get("state") != "open" or pr.get("base", {}).get("sha") != doc["base_sha"]
                        or pr.get("head", {}).get("sha") != doc["head_sha"]):
                    continue
                result = await self.enqueue(project_id, doc["repository"], pr, doc["files"], doc["pr_id"],
                                            launch=launch, expected_run_id=doc["run_id"])
                queued.append(result)
            except Exception:
                logger.exception("Approval continuation could not enqueue scoped PR %s", doc["run_id"])
        return queued

    async def fresh(self, doc):
        if await self.collection("code_quality_runs").find_one({"run_id": doc["run_id"], "authority_review_required": True}):
            return False
        owner, repo = doc["repository"].split("/")
        current = await self.api.client.get_pull_request(owner, repo, doc["pr_number"])
        return (current.get("state") == "open" and current.get("head", {}).get("sha") == doc["head_sha"]
                and current.get("base", {}).get("sha") == doc["base_sha"])

    async def set_status(self, doc, status, **fields):
        await self.collection("code_quality_runs").update_one({"run_id": doc["run_id"]}, {"$set": {"status": status, **fields}})
        if status == "superseded":
            await self.collection("recommendations").update_many(
                {"algorithm_analysis_run_id": doc["run_id"], "project_id": doc["project_id"]},
                {"$set": {"status": "obsolete", "historical_only": True}})
        await self.collection("pull_requests").update_one(
            {"id": doc["pr_id"], "project_id": doc["project_id"], "head_sha": doc["head_sha"], "algorithm_intelligence_run_id": doc["run_id"]},
            {"$set": {"algorithm_intelligence_status": status}})

    async def snapshot(self, doc, revision, files):
        owner, repo = doc["repository"].split("/")
        sources, diagnostics = await self.api.fetch_analysis_sources(
            owner, repo, files, revision, include_context=True, verified_snapshot=True, include_quality_context=False,
        )
        discovery = (await discover_sources(sources, doc["project_id"], revision, diagnostics)).model_dump(mode="json")
        run_id = doc["run_id"] + ("-base" if revision == doc["base_sha"] else "-head")
        await self.collection("code_quality_runs").update_one({"run_id": run_id}, {"$setOnInsert": {
            "run_id": run_id, "repository_id": doc["project_id"], "commit_sha": revision, "status": "completed",
            "org_id": doc["organization_id"], "created_at": now(),
            "source_provenance": {"method": "github-exact-revision", "repository": doc["repository"], "revision": revision},
            "function_discovery": discovery}}, upsert=True)
        return run_id, discovery, sources

    async def resolve_contracts(self, doc, pair, base_run):
        matches = []
        bound_function = pair["previous"] or pair["current"]
        records = await self.contracts.collection.find({"project_id": doc["project_id"], "status": "APPROVED"}, {"_id": 0}).limit(101).to_list(101)
        if len(records) > 100:
            return [], "Approved-contract search bound exceeded; no arbitrary contract was selected"
        for contract in records:
            if contract.get("organization_id") != doc["organization_id"]:
                continue
            accepted = doc.get("approved_contracts")
            if accepted is not None and {"contract_id": contract["contract_id"],
                                         "payload_fingerprint": contract["payload_fingerprint"]} not in accepted:
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
                    if (fn["function_id"] == binding["function_id"] and all(
                            fn.get(k) == bound_function.get(k) for k in ("source_hash", "path", "qualified_name", "language"))):
                        found = True
            if found:
                resolution = await self.contracts.resolve(doc["project_id"], [contract["contract_id"]])
                if resolution["status"] == "APPROVED" and resolution.get("validator_available"):
                    matches.append({**resolution["snapshot"], "contract_id": contract["contract_id"]})
        if len(matches) != 1:
            return matches, "No uniquely applicable approved functional contract; names and inferred purpose cannot supply one"
        return matches, None

    async def benchmark_standalone(self, doc, pair, row, sources, head_run, contract, user):
        """Validate and measure one verified implementation on approved checks."""
        function = pair["current"]
        checks = set(contract["required_dataset_ids"])
        request = {
            "project_id": doc["project_id"], "language": function["language"],
            "candidates": [{"name": "current", "entrypoint": function["name"], "source": sources[function["path"]]}],
            "contract": contract["contract"], "datasets": [d for d in contract["datasets"] if d["id"] in checks],
            "repetitions": 5, "resources": {"cpus": 1, "memory_bytes": 536870912, "pids": 64, "timeout_seconds": 45},
            "decision_policy": {"id": "automatic-pr-standalone", "version": "1", "objective": "TRADEOFF_ONLY",
                                "required_dataset_ids": contract["required_dataset_ids"]},
            "requirement_context": {"pr_ids": [doc["pr_id"]], "contract_ids": [contract["contract_id"]],
                                    "discovery_run_ids": [head_run], "function_ids": [function["function_id"]]},
        }
        from domain.schemas.algorithm_benchmark import BenchmarkRequest
        validated = BenchmarkRequest.model_validate(request).model_dump()
        created = await self.benchmarks.create(validated, user, metadata={
            "kind": "pr_standalone", "pr_automation": {
                "run_id": doc["run_id"], "repository": doc["repository"], "pr_id": doc["pr_id"],
                "head_sha": doc["head_sha"], "function_id": function["function_id"], "discovery_run_id": head_run,
                "contract_id": contract["contract_id"], "contract_fingerprint": fingerprint(contract),
            },
        })
        row.update(benchmark_run_id=created["run_id"], benchmark_status="pending")
        child = await self.benchmarks.get(created["run_id"])
        report = child.get("requirements_discovery", {})
        constraints = child["request"]["decision_policy"]["constraints"]
        if (not await self.fresh(doc) or report.get("conflicts")
                or any(c.get("applicability") == "UNRESOLVED" for c in constraints)):
            await self.benchmarks._finish(child["run_id"], {
                "status": "failed", "error": "Revision or applicable requirements could not be verified before execution",
            })
            row["benchmark_status"] = "blocked"
            return
        await self.benchmarks.execute(child["run_id"])
        child = await self.benchmarks.get(child["run_id"])
        row["benchmark_status"] = child["status"]
        row["evidence_refs"].append(child["run_id"])

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
                 "decision_revision_id": decision.get("revision_id"),
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
                await expire_pr_jobs(self.collection("code_quality_runs"), self.collection("pull_requests"), run_id=run_id)
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
        pairs = apply_same_revision_alternatives(changed_functions(base, head, files, before, after))
        discovery_incomplete = base["status"] != "available" or head["status"] != "available"
        await self.set_status(doc, "analyzing", base_discovery_run_id=base_run, head_discovery_run_id=head_run,
                              function_discovery=head, evidence_refs=[base_run, head_run], organization_id=user["org_id"],
                              analysis_truncated=bool(doc.get("input_truncated") or discovery_incomplete))
        rows, recommendations, executed = [], [], 0
        proposals = 0

        async def draft_missing(pair, row):
            nonlocal proposals
            if not settings.ALGORITHM_AI_CONTRACT_PROPOSALS_ENABLED:
                row["requirement_proposal"] = {"status": "disabled"}
                return
            if proposals >= 2:
                row["requirement_proposal"] = {"status": "deferred"}
                return
            if not pair["candidate_eligible"] or row["static_status"] != "analyzed":
                return
            fn = pair["current"]
            source = after.get(fn["path"])
            if not isinstance(source, str) or not await self.fresh(doc):
                return
            proposals += 1
            from domain.services.algorithm_contract_proposals import propose_from_model
            row["requirement_proposal"] = await propose_from_model(
                doc, fn, function_text(source, fn), head_run, row["static"], user, self.contracts)
        if not pairs:
            await self.set_status(doc, "unsupported", reason="No changed function body could be extracted; inspect source diagnostics and module/caller changes", completed_at=now())
            return
        for pair in pairs[:64]:
            def identity(fn):
                return {k: copy.deepcopy(fn.get(k)) for k in ("function_id", "path", "qualified_name", "name", "language", "source_hash", "source_revision", "is_async", "detected_patterns", "task_hypotheses")}
            row = {"current": identity(pair["current"]), "previous": identity(pair["previous"]) if pair["previous"] else None,
                   "mode": pair["mode"], "relationship": pair["relationship"]}
            row.update(status="unsupported", comparison_status="not_analyzed", evidence_refs=[base_run, head_run])
            # Static analysis runs for every changed function, including those with
            # no base counterpart, so absence of a comparison never suppresses findings.
            static = static_findings(pair["current"], after.get(pair["current"]["path"]))
            row["static"] = static
            row["classification"] = static["classification"]
            row["complexity"] = static["complexity"]
            row["static_status"] = static["status"]
            if pair["previous"]:
                # A predecessor or same-revision alternative is analysed with the same
                # method so the two sides are comparable rather than asymmetric.
                previous_source = before if pair["mode"] == "B" else after
                row["static_previous"] = static_findings(pair["previous"],
                                                         previous_source.get(pair["previous"]["path"]))
            rows.append(row)
            if pair["unsupported_reason"]:
                if pair["mode"] == "A":
                    row.update(status="analyzed", comparison_status="not_applicable", reason=pair["unsupported_reason"])
                    row["benchmark_status"] = "not_applicable"
                    if not pair["candidate_eligible"]:
                        continue
                    approved, blocked = await self.resolve_contracts(doc, pair, base_run)
                    enabled = self.enabled if self.enabled is not None else settings.ALGORITHM_BENCHMARK_ENABLED
                    if blocked and not approved and blocked.startswith("No uniquely applicable"):
                        await draft_missing(pair, row)
                    if blocked or not enabled or executed >= 4:
                        row.update(benchmark_status="blocked", benchmark_reason=blocked or (
                            "Automatic benchmark budget reached" if enabled else "Benchmark execution is disabled"))
                        continue
                    try:
                        await self.benchmark_standalone(doc, pair, row, after, head_run, approved[0], user)
                    except BenchmarkBusy:
                        row.update(benchmark_status="blocked", benchmark_reason="An existing benchmark holds the project slot")
                    else:
                        executed += 1
                else:
                    row.update(status="unsupported", comparison_status="unsupported", reason=pair["unsupported_reason"])
                continue
            contracts, reason = await self.resolve_contracts(doc, pair, base_run)
            if reason:
                row.update(status="insufficient_evidence", comparison_status="blocked", reason=reason,
                           contract_ids=[c["contract_id"] for c in contracts])
                if not contracts and reason.startswith("No uniquely applicable"):
                    await draft_missing(pair, row)
                continue
            contract = contracts[0]
            row["contract_id"] = contract["contract_id"]
            row["datasets"] = [{"id": d["id"], "fingerprint": fingerprint(d), "contract_version": contract["contract"]["version"],
                "input_characteristics": {"declared_dimensions": d.get("dimensions", {}), "arguments": [
                    {"type": type(arg).__name__, **({"length": len(arg)} if isinstance(arg, (list, dict, str)) else {})} for arg in d.get("args", [])]},
                "expected_output_method": contract["contract"].get("comparison", {"mode": "exact"}),
                "source_reference": "algorithm_function_contracts/" + contract["contract_id"], "validation_status": "APPROVED_FIXTURE"} for d in contract["datasets"]]
            if not (self.enabled if self.enabled is not None else settings.ALGORITHM_BENCHMARK_ENABLED):
                row.update(status="unsupported", comparison_status="unsupported",
                           reason="Existing administrator benchmark execution flag is disabled")
                continue
            if executed >= 4:
                row.update(status="insufficient_evidence", comparison_status="deferred",
                           reason="Automatic comparison budget reached; static findings retained")
                continue
            if not await self.fresh(doc):
                await self.set_status(doc, "superseded", functions=rows, completed_at=now())
                return
            def candidate(fn, source, label, discovery_run):
                return {"name": label, "source": source[fn["path"]], "entrypoint": fn["name"], "language": fn["language"],
                        "function_reference": {"run_id": discovery_run, "function_id": fn["function_id"]}}
            # Mode B compares the base revision against the head revision; Mode C
            # compares two declarations that both come from the head revision.
            previous_source, previous_run = (before, base_run) if pair["mode"] == "B" else (after, head_run)
            body = {"project_id": doc["project_id"], "contract_ids": [contract["contract_id"]],
                "previous": candidate(pair["previous"], previous_source, "previous", previous_run), "current": candidate(pair["current"], after, "current", head_run),
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
                row.update(status="insufficient_evidence", comparison_status="blocked",
                           reason="Existing project benchmark concurrency slot is occupied; no parallel bypass was attempted")
                continue
            executed += 1
            child = await self.benchmarks.get(created["run_id"])
            row["benchmark_run_id"] = child["run_id"]
            report = child.get("requirements_discovery", {})
            if created["status"] == "pending" and (not await self.fresh(doc) or report.get("conflicts") or any(c.get("applicability") == "UNRESOLVED" for c in child["request"]["decision_policy"]["constraints"])):
                await self.benchmarks._finish(child["run_id"], {"status": "completed", "error": "Applicable requirement or validator is unresolved; automatic execution skipped"})
                row.update(status="insufficient_evidence", comparison_status="blocked",
                           reason="Requirements need resolution before automatic execution", requirements_discovery=report)
                continue
            if created["status"] == "pending":
                await self.set_status(doc, "benchmarking", functions=rows)
                await self.benchmarks.execute(child["run_id"])
            child = await self.benchmarks.get(child["run_id"])
            if not await self.fresh(doc):
                await self.set_status(doc, "superseded", functions=rows, completed_at=now())
                return
            if child["status"] != "completed":
                row.update(status="failed", comparison_status="failed",
                           reason=child.get("error") or "Isolated worker did not complete")
                continue
            row.update(status="completed" if child.get("behavioral_compatibility", {}).get("phase1_eligible") else "insufficient_evidence",
                       comparison_status="completed" if child.get("behavioral_compatibility", {}).get("phase1_eligible") else "inconclusive",
                       compatibility=child.get("behavioral_compatibility", {}).get("status"), evidence_refs=[base_run, head_run, child["run_id"]])
            rec_id, finding = await self.publish_recommendation(doc, row, child)
            row["finding_status"] = finding
            recommendations.append(rec_id)
        if not await self.fresh(doc):
            await self.set_status(doc, "superseded", functions=rows, completed_at=now())
            return
        status = run_status(rows)
        modes = {}
        for row in rows:
            modes[row.get("mode", "A")] = modes.get(row.get("mode", "A"), 0) + 1
        await self.set_status(doc, status, functions=rows, recommendation_ids=recommendations, completed_at=now(),
                              comparison_modes=modes, report_status="incomplete",
                              analysis_truncated=bool(doc.get("input_truncated") or discovery_incomplete or len(pairs) > 64))
        # Persist deterministic output before invoking AI. An interrupted AI stage
        # never replaces the already published measurements.
        try:
            from agents.algorithm_agent import generate
            persisted = await self.get(doc["run_id"])
            async def current():
                return bool(await self.collection("pull_requests").find_one({
                    "id": doc["pr_id"], "project_id": doc["project_id"], "head_sha": doc["head_sha"],
                    "algorithm_intelligence_run_id": doc["run_id"], "status": "open"})) and await self.fresh(doc)
            await generate(self.collection("code_quality_runs"), persisted, "pr", freshness=current)
        except Exception:
            logger.exception("Algorithm advisory could not complete for %s", doc["run_id"])

    async def get(self, run_id):
        await expire_pr_jobs(self.collection("code_quality_runs"), self.collection("pull_requests"), run_id=run_id)
        return await self.collection("code_quality_runs").find_one({"run_id": run_id, "kind": "pr_algorithm_intelligence"}, {"_id": 0})
