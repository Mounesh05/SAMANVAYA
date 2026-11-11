"""Compatibility requests reuse the existing benchmark job collection and runner."""

import copy
import hashlib
import asyncio

from domain.schemas.behavioral_compatibility import BehavioralComparisonRequest
from domain.services.function_contract_service import FunctionContractService
from intelligence.algorithms.compatibility import evaluate_compatibility, provisional_relationships


class BehavioralCompatibilityService:
    def __init__(self, benchmarks, contracts=None, runs=None):
        self.benchmarks = benchmarks
        self.contracts = contracts or FunctionContractService()
        self._runs = runs

    @property
    def runs(self):
        return self._runs if self._runs is not None else self.contracts.runs

    async def _context(self, candidate, project_id):
        source_hash = hashlib.sha256(candidate.source.encode()).hexdigest()
        identity = {"name": candidate.name, "entrypoint": candidate.entrypoint, "language": candidate.language,
                    "source_hash": source_hash, "function_reference": candidate.function_reference.model_dump() if candidate.function_reference else None,
                    "source_revision": None, "phase2_context": None}
        if candidate.function_reference is None:
            return identity, []
        reference = candidate.function_reference
        run = await self.runs.find_one({"run_id": reference.run_id, "repository_id": project_id})
        snapshot = run.get("function_discovery", {}) if run else {}
        functions = snapshot.get("functions", []) if snapshot.get("method") == "function-purpose-v1" and snapshot.get("status") in {"available", "partial"} else []
        matches = [f for f in functions if f["function_id"] == reference.function_id]
        if len(matches) != 1:
            return identity, ["Referenced Phase 2 function evidence is unavailable in this project."]
        function = matches[0]
        if (function["source_hash"] != source_hash or function["language"] != candidate.language
                or function["name"] != candidate.entrypoint or function["qualified_name"] != candidate.entrypoint):
            return identity, ["Submitted source, language or entrypoint does not match the referenced Phase 2 snapshot."]
        identity.update(source_revision=function.get("source_revision"), phase2_context=function)
        return identity, []

    async def create(self, body, user, metadata=None):
        body = BehavioralComparisonRequest.model_validate(body)
        resolution = await self.contracts.resolve(body.project_id, body.contract_ids)
        previous, before_errors = await self._context(body.previous, body.project_id)
        current, after_errors = await self._context(body.current, body.project_id)
        relationship = {"status": "PROVISIONAL", "reasons": ["Explicit previous/current comparison request"],
                        "evidence_refs": ["request/previous", "request/current"],
                        "limitations": ["Previous/current labels do not establish chronology or substitutability."]}
        if previous["phase2_context"] and current["phase2_context"]:
            candidates = provisional_relationships({"functions": [previous["phase2_context"]]}, {"functions": [current["phase2_context"]]},
                body.previous.function_reference.run_id, body.current.function_reference.run_id)
            if candidates:
                relationship = candidates[0]
        snapshot = resolution.get("snapshot") or {}
        datasets = copy.deepcopy(snapshot.get("datasets", []))
        if body.dataset_ids is not None:
            if set(body.dataset_ids) - {d["id"] for d in datasets}:
                raise ValueError("Requested checks are not in the resolved contract")
            datasets = [d for d in datasets if d["id"] in body.dataset_ids]
        context = {"version": "behavioral-compatibility-v1", "resolution": resolution, "previous": previous, "current": current,
                   "relationship": relationship, "context_errors": before_errors + after_errors,
                   "required_dataset_ids": snapshot.get("required_dataset_ids", []), "requirements": snapshot.get("requirements", []),
                   "candidate_languages": {body.previous.name: body.previous.language, body.current.name: body.current.language}}
        policy = body.decision_policy.model_dump() if body.decision_policy else {
            "id": "compatibility-scope", "version": "1", "objective": "TRADEOFF_ONLY",
            "required_dataset_ids": snapshot.get("required_dataset_ids", []),
        }
        request = {"project_id": body.project_id, "language": body.current.language,
                   "candidates": [{"name": c.name, "source": c.source, "entrypoint": c.entrypoint} for c in (body.previous, body.current)],
                   "contract": snapshot.get("contract"), "datasets": datasets, "resources": body.resources,
                   "repetitions": body.repetitions, "seed": 42, "sizes": [0], "distributions": ["random"],
                   "objective": "time", "memory_limit_bytes": None, "decision_policy": policy, "compatibility_context": context,
                   "requirement_context": body.requirement_context.model_dump() if body.requirement_context else None}
        result = await self.benchmarks.create(request, user, metadata={**(metadata or {}), "kind": "behavioral_compatibility"})
        if resolution["status"] != "APPROVED" or not resolution.get("validator_available") or before_errors or after_errors or not datasets:
            report = evaluate_compatibility(request, {"results": []}, result["run_id"])
            await self.benchmarks._finish(result["run_id"], {"status": "completed", "behavioral_compatibility": report,
                "phase1_eligibility": {"eligible": False, "evidence_reference": result["run_id"] + "/behavioral_compatibility"}})
            result["status"] = "completed"
        return result


async def collect_compatibility_evidence(runner, request):
    """Use the existing isolated worker runner, including mixed-language pairs."""
    languages = request["compatibility_context"]["candidate_languages"]
    groups = {}
    for candidate in request["candidates"]:
        groups.setdefault(languages[candidate["name"]], []).append(candidate)
    evidence = {"results": [], "environment": {}, "tools": {}}
    images, workers = {}, []
    timeout = min(getattr(runner, "timeout_seconds", 30), request.get("resources", {}).get("timeout_seconds", 120))
    deadline = asyncio.get_running_loop().time() + timeout
    for language, candidates in groups.items():
        payload = {**request, "language": language, "candidates": candidates}
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("Behavioral comparison exceeded its total isolated-run deadline")
        current = await asyncio.wait_for(runner.run(payload), remaining)
        evidence["results"].extend(current["results"])
        evidence["environment"].update(current.get("environment", {}))
        evidence["tools"].update(current.get("tools", {}))
        images.update(current.get("environment", {}).get("images", {}))
        workers.extend(current.get("environment", {}).get("workers", []))
    evidence["environment"].update(images=images, workers=workers)
    return evidence
