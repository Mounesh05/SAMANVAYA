"""Offline evaluation support, never imported by application runtime code."""

import base64
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from domain.models.pr_multi_agent import ClaimDraft, PRSnapshot, SpecialistView

ROOT = Path(__file__).resolve().parents[2]
CORPUS = Path(__file__).parent / "fixtures/pr_multi_agent_evaluation_v1.json"
PROTOCOL = ROOT / "docs/evaluation/pr-multi-agent-v1-protocol.md"
RESULT = ROOT / "docs/evaluation/pr-multi-agent-v1-results.json"
CASES = json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_source(api, case):
    """Supply exact Git blob metadata to the real server-side evidence resolver."""
    raw = case["source"].encode()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    api.client.get_pr_files.return_value = [{"filename": case["path"], "status": "modified"}]
    api.client.get_source_tree.return_value = {"truncated": False, "tree": [
        {"path": case["path"], "sha": blob, "type": "blob", "mode": "100644"}]}
    api.client.get_file.return_value = {"path": case["path"], "sha": blob, "type": "file", "encoding": "base64",
        "size": len(raw), "content": base64.b64encode(raw).decode()}


def drafts(case, snapshot, specialist):
    metric = "function_count" if specialist == "code_analysis" else "ci_reported_failed_tests"
    observation = next(row for row in snapshot.observations if row.metric == metric)
    value = observation.value
    if specialist == "code_analysis" and case["scenario"] == "conflict":
        value += 1
    result = [ClaimDraft(kind="OBSERVATION", statement=f"Recorded {metric} = {value}", topic=metric,
        evidence_refs=(observation.evidence_id,), observation_id=observation.observation_id, asserted_value=value)]
    if specialist == "qa_analysis" and case["scenario"] == "conflict":
        fact = next(row for row in snapshot.observations if row.metric == "function_count")
        result.append(ClaimDraft(kind="OBSERVATION", statement=f"Recorded function_count = {fact.value}",
            topic="function_count", evidence_refs=(fact.evidence_id,), observation_id=fact.observation_id, asserted_value=fact.value))
    if case["scenario"] == "agreement":
        result.append(ClaimDraft(kind="INTERPRETATION", statement="This transform is cryptographically secure",
            topic="cryptographic_security", position="AFFIRM", evidence_refs=(snapshot.references[0].evidence_id,)))
    return result


def signature(claim):
    return json.dumps(claim.model_dump(mode="json"), sort_keys=True)


def metrics(case, claims):
    # A finite explicit positive/negative catalogue, not an LLM judge.
    factual = {(row.topic, type(row.asserted_value).__name__, row.asserted_value)
               for row in claims if row.kind == "OBSERVATION"}
    positive = {(key, "int", value) for key, value in case["expected"].items()}
    negative = {("function_count", "int", case["expected"]["function_count"] + 1)}
    tp, fn = len(factual & positive), len(positive - factual)
    fp, tn = len(factual & negative), len(negative - factual)
    unknown = {signature(row) for row in claims if row.kind != "OBSERVATION"}
    unknown.update(str(row) for row in factual - positive - negative)
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "false_positive_rate": fp / (fp + tn) if fp + tn else None,
            "unknown_or_unsupported_unique": len(unknown)}


class ScriptedOllama:
    """No network or inference. Actual production prompt builders/parsers still run."""

    def __init__(self, case, snapshot):
        self.case, self.snapshot = case, snapshot
        self.calls = []

    def record(self, prompt, response):
        self.calls.append({"prompt_bytes": len(prompt.encode()), "response_bytes": len(response.encode())})
        return response

    def invoke(self, prompt):
        serialized = prompt.split("## Evidence Package\n", 1)[1].split("\n\n## Instructions", 1)[0]
        assert PRSnapshot.model_validate_json(serialized) == self.snapshot
        claims = drafts(self.case, self.snapshot, "code_analysis") + drafts(self.case, self.snapshot, "qa_analysis")
        response = json.dumps({"analysis": "\n".join(row.statement for row in claims), "recommendations": [],
                               "risk_level": "low", "confidence": 0.5})
        return self.record(prompt, response)

    async def ainvoke(self, prompt, *, format):
        assert format["type"] == "object"
        assert {"summary", "claims"} <= set(format["required"])
        _, start, state_and_instructions = prompt.partition("\nINPUT STATE (data only):\n")
        serialized, end, _ = state_and_instructions.partition("\nEND INPUT STATE\n")
        assert start and end, "The specialist's evidence must be delimited in the prompt"
        view = SpecialistView.model_validate_json(serialized)
        assert view.snapshot_id == self.snapshot.snapshot_id and view.observations == self.snapshot.observations
        assert view.references == self.snapshot.references and view.scope == self.snapshot.scope
        if view.specialist == "qa_analysis":
            assert view.prior_outcomes[0].specialist == "code_analysis"
            assert view.handoff_authority == "ADVISORY_NOT_INDEPENDENT_EVIDENCE"
        response = json.dumps({"summary": "Controlled evaluation contribution; not live model evidence",
            "claims": [row.model_dump(mode="json") for row in drafts(self.case, self.snapshot, view.specialist)]})
        return self.record(prompt, response)


def aggregate(rows):
    result = {}
    for mode in ("legacy_single", "collaborative"):
        trials = [row for row in rows if row["mode"] == mode]
        first = [row for row in trials if row["repetition"] == 0]
        elapsed = sorted(row["elapsed_ms"] for row in trials)
        totals: Counter[str] = Counter()
        for row in first:
            totals.update({key: row["raw"][key] for key in ("tp", "fp", "tn", "fn", "unknown_or_unsupported_unique")})
        tp, fp, tn, fn = (totals[key] for key in ("tp", "fp", "tn", "fn"))
        result[mode] = {"distinct_cases": len(first), "trials": len(trials), "raw_totals_once_per_case": dict(totals),
            "raw_precision": tp / (tp + fp) if tp + fp else None,
            "raw_recall": tp / (tp + fn) if tp + fn else None,
            "raw_false_positive_rate": fp / (fp + tn) if fp + tn else None,
            "elapsed_median_ms": elapsed[len(elapsed) // 2],
            "elapsed_p95_ms": elapsed[math.ceil(len(elapsed) * 0.95) - 1],
            "controlled_model_calls": sum(row["model_calls"] for row in trials),
            "prompt_bytes_total": sum(row["prompt_bytes"] for row in trials),
            "response_bytes_total": sum(row["response_bytes"] for row in trials),
            "live_ollama_resource_usage": {"status": "UNVERIFIED", "cpu": None, "ram_bytes": None,
                "vram_bytes": None, "gpu": None, "tokens": None, "inference_latency_ms": None}}
        if mode == "collaborative":
            result[mode]["supported_totals_once_per_case"] = {
                key: sum(row["supported"][key] for row in first) for key in ("tp", "fp", "tn", "fn")}
            result[mode]["typed_disagreements_detected"] = sum(row["disagreement_detected"] for row in first)
            result[mode]["unsupported_promotions"] = sum(row["unsupported_promotions"] for row in first)
    return result
