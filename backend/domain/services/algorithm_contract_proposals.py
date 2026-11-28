"""Bounded model-generated contract drafts; never approve or execute them."""
import asyncio
import json
import logging

import httpx

from core.config import settings
from domain.schemas.behavioral_compatibility import ContractProposal
from intelligence.algorithms.decision import fingerprint

logger = logging.getLogger(__name__)


async def propose_from_model(doc, function, head_run, user, contracts):
    scope = {"repository": doc["repository"], "path": function["path"],
             "qualified_name": function["qualified_name"]}
    name = "ai-draft-" + fingerprint(scope)[:32]
    version = fingerprint([function["source_hash"], doc["head_sha"]])[:32]
    query = {"project_id": doc["project_id"], "organization_id": user["org_id"],
             "contract.name": name, "contract.version": version}
    existing = await contracts.collection.find_one(query, {"_id": 0, "contract_id": 1, "status": 1})
    if existing:
        return {"status": existing["status"].lower(), "contract_id": existing["contract_id"]}
    oracles = [e for e in function.get("evidence", []) if e.get("kind") == "test_expectation"
               and e.get("source_revision") == doc["head_sha"] and e.get("literal_fixture")]
    if not oracles:
        return {"status": "insufficient_evidence", "reason": "No linked literal input and expected result for this revision"}
    # The local model sees only data shapes and synthetic IDs. Fixtures stay server-owned.
    datasets = [{"id": f"case-{i}", **e["literal_fixture"]} for i, e in enumerate(oracles[:8], 1)]
    evidence = [{"id": d["id"], "argument_types": [type(v).__name__ for v in d["args"]],
                 "result_type": type(d["expected"]).__name__} for d in datasets]
    instruction = (
        'Describe the finite input/output checks for independent review. You may abstain with '
        '{"status":"insufficient_evidence"}. Otherwise return JSON with status proposed, input_schema '
        '(JSON schema for positional argument array), output_schema, mutation (allowed or forbidden), '
        'and requirements (description and dataset_ids for each group). Cover every given dataset ID. '
        'Keep descriptions limited to observed types and finite examples. Do not infer general intent or budgets. '
        'No datasets, source code or policy decisions in the response. Examples: '
    )
    try:
        async with httpx.AsyncClient(timeout=18) as client:
            response = await asyncio.wait_for(client.post(settings.OLLAMA_BASE_URL.rstrip("/") + "/api/generate", json={
                "model": settings.OLLAMA_MODEL, "format": "json", "stream": False,
                "options": {"temperature": 0, "num_predict": 1600},
                "prompt": instruction + json.dumps(evidence, ensure_ascii=True),
            }), timeout=20)
            response.raise_for_status()
            if len(response.content) > 48000:
                raise ValueError("Oversized response")
            value = json.loads(response.json()["response"])
        if value == {"status": "insufficient_evidence"}:
            return {"status": "insufficient_evidence"}
        if not isinstance(value, dict) or set(value) != {"status", "input_schema", "output_schema", "mutation", "requirements"} or value["status"] != "proposed":
            raise ValueError("Invalid proposal fields")
        requirements = value["requirements"]
        if not isinstance(datasets, list) or not 1 <= len(datasets) <= 8 or not isinstance(requirements, list) or not 1 <= len(requirements) <= 8:
            raise ValueError("Proposal exceeds bounded case count")
        if any(not isinstance(d, dict) or set(d) != {"id", "args", "expected"} for d in datasets):
            raise ValueError("Only explicit data fixtures accepted")
        if any(not isinstance(r, dict) or set(r) != {"description", "dataset_ids"} for r in requirements):
            raise ValueError("Invalid requirement fields")
        # All authority, identity and provenance are server-owned.
        refs = {d["id"]: e["id"] for d, e in zip(datasets, oracles)}
        payload = ContractProposal.model_validate({
            "project_id": doc["project_id"],
            "contract": {"kind": "function", "name": name, "version": version,
                         "input_schema": value["input_schema"], "output_schema": value["output_schema"],
                         "correctness": "expected", "mutation": value["mutation"],
                         "output": {"source": "return"}, "comparison": {"mode": "exact", "version": "1"}},
            "datasets": datasets, "required_dataset_ids": [d["id"] for d in datasets],
            "requirements": [{"id": f"draft-{i+1}", "description": r["description"],
                              "source_reference": head_run + "/evidence/" + ",".join(refs[key] for key in r["dataset_ids"]),
                              "dataset_ids": r["dataset_ids"]}
                             for i, r in enumerate(requirements)],
            "scope_description": "AI-generated hypotheses, not independently verified. Reviewer must verify expected outputs, "
                                 "intended behavior and reusable function scope before approval.",
            "function_bindings": [{"run_id": head_run, "function_id": function["function_id"]}],
            "automatic_scope": scope,
        }).model_dump()
        if len(json.dumps(payload).encode()) > 32000:
            raise ValueError("Oversized draft")
        try:
            draft = await contracts.propose(payload, user)
        except ValueError:
            existing = await contracts.collection.find_one(query, {"_id": 0, "contract_id": 1, "status": 1})
            if existing:
                return {"status": existing["status"].lower(), "contract_id": existing["contract_id"]}
            raise
        return {"status": "proposed", "contract_id": draft["contract_id"]}
    except (TimeoutError, httpx.HTTPError, ValueError, TypeError, KeyError, UnicodeError):
        logger.info("AI contract draft unavailable for scoped PR run %s", doc["run_id"])
        return {"status": "unavailable", "reason": "Model unavailable or draft did not satisfy the proposal schema"}
