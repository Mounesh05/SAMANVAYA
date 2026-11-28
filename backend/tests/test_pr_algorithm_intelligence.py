"""Automatic PR integration never executes developer code outside worker adapters."""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from domain.services.pr_algorithm_intelligence_service import PRAlgorithmIntelligenceService, changed_functions, METHOD
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from domain.services.requirement_discovery_service import RequirementDiscoveryService
from intelligence.algorithms.discovery.service import discover_sources
from repositories.pr_repository import PRRepository
from test_behavioral_compatibility import AUTHOR, REVIEWER, proposal, approved, passing_evidence
from test_requirement_discovery import publish, source, declaration

pytestmark = pytest.mark.anyio
BASE = "def solve(xs):\n    return xs\n"
HEAD = "def solve(xs):\n    return list(xs)\n"


@pytest.fixture
async def workflow(mock_db):
    await mock_db.projects.insert_one({"id": "P1", "org_id": "org", "status": "active"})
    await mock_db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "o", "repository_name": "r"})
    pr = {"number": 7, "state": "open", "base": {"sha": "base"}, "head": {"sha": "head"}}
    await mock_db.pull_requests.insert_one({"id": "PR1", "project_id": "P1", "repo_id": "o/r", "pr_number": 7, "status": "open", "head_sha": "head"})
    snapshots = {"base": {"module.py": BASE}, "head": {"module.py": HEAD}}
    api = SimpleNamespace(client=SimpleNamespace(get_pull_request=AsyncMock(side_effect=lambda *args: copy.deepcopy(pr))),
                          fetch_analysis_sources=AsyncMock(side_effect=lambda o, r, files, rev, **kwargs: (copy.deepcopy(snapshots[rev]), [])))
    requirements = RequirementDiscoveryService(mock_db)
    runner = SimpleNamespace(run=AsyncMock(side_effect=passing_evidence))
    benchmarks = AlgorithmBenchmarkService(mock_db.algorithm_benchmark_runs, runner, requirements)
    service = PRAlgorithmIntelligenceService(api, mock_db, benchmarks, enabled=True)
    return SimpleNamespace(db=mock_db, service=service, api=api, pr=pr, snapshots=snapshots, runner=runner, benchmarks=benchmarks)


async def contract(workflow, **updates):
    payload = proposal()
    payload["automatic_scope"] = {"repository": "o/r", "path": "module.py", "qualified_name": "solve"}
    payload.update(updates)
    return await approved(workflow.service.contracts, payload)


async def run(workflow, files=None):
    created = await workflow.service.enqueue("P1", "o/r", workflow.pr,
        files or [{"filename": "module.py", "status": "modified"}], "PR1", launch=False)
    await workflow.service.execute(created["run_id"])
    return await workflow.service.get(created["run_id"])


async def test_missing_contract_preserves_static_findings_without_execution(workflow):
    result = await run(workflow)
    assert result["status"] == "insufficient_evidence"
    row = result["functions"][0]
    assert row["current"]["qualified_name"] == "solve"
    assert row["relationship"]["status"] == "PROVISIONAL"
    assert result["function_discovery"]["functions"]
    # Genuine base-vs-head replacement: the same declaration exists on both sides.
    assert row["mode"] == "B" and row["previous"]["qualified_name"] == "solve"
    assert row["comparison_status"] == "blocked" and row["static_status"] == "analyzed"
    assert row["static"]["status"] == "analyzed" and row["static_previous"]["status"] == "analyzed"
    assert row["complexity"]["method"] == "static-ast-complexity-v1"
    assert result["comparison_modes"] == {"B": 1}
    workflow.runner.run.assert_not_awaited()


async def test_approved_new_function_uses_one_candidate_without_comparison(workflow):
    workflow.snapshots["base"] = {"module.py": "VALUE = 1\n"}
    approved_contract = await contract(workflow)
    result = await run(workflow)
    row = result["functions"][0]
    assert row["mode"] == "A" and row["comparison_status"] == "not_applicable"
    assert row["benchmark_status"] == "completed"
    workflow.runner.run.assert_awaited_once()
    request = workflow.runner.run.call_args.args[0]
    assert [candidate["entrypoint"] for candidate in request["candidates"]] == ["solve"]
    stored = await workflow.benchmarks.get(row["benchmark_run_id"])
    assert stored["pr_automation"]["contract_id"] == approved_contract["contract_id"]
    assert stored["pr_automation"]["head_sha"] == "head"
    assert await workflow.db.recommendations.count_documents({}) == 0


async def test_approval_unblocks_same_revision_without_replaying_a_duplicate(workflow):
    workflow.snapshots["base"] = {"module.py": "VALUE = 1\n"}
    before = await run(workflow)
    assert before["functions"][0]["benchmark_status"] == "blocked"
    await contract(workflow)
    after = await run(workflow)
    assert before["run_id"] != after["run_id"]
    assert after["functions"][0]["benchmark_status"] == "completed"
    duplicate = await run(workflow)
    assert duplicate["run_id"] == after["run_id"]
    workflow.runner.run.assert_awaited_once()


async def test_approved_contract_datasets_requirements_and_evidence_reach_phase1(workflow):
    await contract(workflow)
    await publish(workflow.service.requirements, source(declaration(value=0.1)))
    result = await run(workflow)
    assert result["status"] == "completed", result.get("error")
    row = result["functions"][0]
    assert row["compatibility"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"
    assert row["finding_status"] == "CONDITIONAL_FINDING"
    assert row["datasets"][0]["validation_status"] == "APPROVED_FIXTURE"
    assert row["datasets"][0]["fingerprint"]
    child = await workflow.benchmarks.get(row["benchmark_run_id"])
    assert any(c["type"] == "MAX_LATENCY" and c["threshold"] == 0.1 for c in child["decision"]["policy_snapshot"]["constraints"])
    recommendation = await workflow.db.recommendations.find_one({"id": result["recommendation_ids"][0]})
    assert recommendation["generated_by"] == METHOD and recommendation["confidence"] is None
    assert recommendation["benchmark_run_id"] == child["run_id"]
    assert recommendation["evidence_ids"]
    payload = workflow.runner.run.call_args.args[0]
    assert payload["resources"]["timeout_seconds"] == 45 and payload["resources"]["pids"] == 64
    assert payload["contract"] == child["request"]["contract"]


async def test_duplicate_delivery_and_concurrent_claim_do_not_duplicate_benchmarks(workflow):
    await contract(workflow)
    a, b = await asyncio.gather(*[workflow.service.enqueue("P1", "o/r", workflow.pr, [{"filename": "module.py"}], "PR1", launch=False) for _ in range(2)])
    assert a["run_id"] == b["run_id"]
    assert a.get("duplicate") or b.get("duplicate")
    await asyncio.gather(workflow.service.execute(a["run_id"]), workflow.service.execute(b["run_id"]))
    workflow.runner.run.assert_awaited_once()
    assert await workflow.db.algorithm_benchmark_runs.count_documents({}) == 1


async def test_new_head_gets_new_analysis_and_stale_run_never_publishes(workflow):
    old = await workflow.service.enqueue("P1", "o/r", workflow.pr, [{"filename": "module.py"}], "PR1", launch=False)
    workflow.pr["head"]["sha"] = "head2"
    workflow.snapshots["head2"] = {"module.py": HEAD + "\n"}
    await workflow.db.pull_requests.update_one({"id": "PR1"}, {"$set": {"head_sha": "head2"}})
    new = await workflow.service.enqueue("P1", "o/r", workflow.pr, [{"filename": "module.py"}], "PR1", launch=False)
    assert old["run_id"] != new["run_id"]
    await workflow.service.execute(old["run_id"])
    assert (await workflow.service.get(old["run_id"]))["status"] == "superseded"
    pr = await workflow.db.pull_requests.find_one({"id": "PR1"})
    assert pr["algorithm_intelligence_run_id"] == new["run_id"] and pr["algorithm_intelligence_status"] == "pending"
    workflow.runner.run.assert_not_awaited()


async def test_head_change_while_worker_runs_retains_history_without_recommendation(workflow):
    await contract(workflow)
    async def worker(request):
        workflow.pr["head"]["sha"] = "newer"
        return passing_evidence(request)
    workflow.runner.run.side_effect = worker
    result = await run(workflow)
    assert result["status"] == "superseded"
    assert await workflow.db.recommendations.count_documents({}) == 0
    assert await workflow.db.algorithm_benchmark_runs.count_documents({"status": "completed"}) == 1


@pytest.mark.parametrize("filename,source_text", [("image.png", "image"), ("module.py", "def incomplete("), ("module.py", "async def solve(xs):\n    return xs\n")])
async def test_unsupported_changes_are_reported_without_execution(workflow, filename, source_text):
    workflow.snapshots["head"] = {filename: source_text}
    result = await run(workflow, [{"filename": filename, "status": "modified"}])
    assert result["status"] == "unsupported"
    workflow.runner.run.assert_not_awaited()


async def test_unchanged_function_body_is_not_benchmarked_for_unrelated_file_edit(workflow):
    workflow.snapshots["head"] = {"module.py": BASE + "\nother = 1\n"}
    result = await run(workflow)
    assert result["status"] == "unsupported"
    workflow.runner.run.assert_not_awaited()


async def test_new_or_renamed_function_has_no_assumed_previous_implementation(workflow):
    workflow.snapshots["head"] = {"module.py": HEAD.replace("solve", "different")}
    result = await run(workflow)
    row = result["functions"][0]
    assert row["previous"] is None
    assert row["mode"] == "A" and row["comparison_status"] == "not_applicable"
    assert row["status"] == "analyzed" and row["static_status"] == "analyzed"
    assert result["status"] == "completed"
    workflow.runner.run.assert_not_awaited()


async def test_multiple_approved_contracts_are_ambiguous_not_latest_wins(workflow):
    await contract(workflow)
    value = proposal(name="different")
    value["automatic_scope"] = {"repository": "o/r", "path": "module.py", "qualified_name": "solve"}
    await approved(workflow.service.contracts, value)
    result = await run(workflow)
    assert result["status"] == "insufficient_evidence"
    assert len(result["functions"][0]["contract_ids"]) == 2
    workflow.runner.run.assert_not_awaited()


async def test_unapproved_or_candidate_controlled_contract_cannot_trigger_execution(workflow):
    payload = proposal()
    payload["automatic_scope"] = {"repository": "o/r", "path": "module.py", "qualified_name": "solve"}
    await workflow.service.contracts.propose(payload, AUTHOR)
    result = await run(workflow)
    assert result["status"] == "insufficient_evidence"
    workflow.runner.run.assert_not_awaited()


async def test_unsupported_contract_validator_is_unverified_without_execution(workflow):
    await contract(workflow, validator_requirement="property_oracle")
    result = await run(workflow)
    assert result["status"] == "insufficient_evidence"
    workflow.runner.run.assert_not_awaited()


async def test_conflicting_authorized_requirements_skip_automatic_execution(workflow):
    await contract(workflow)
    await publish(workflow.service.requirements, source(declaration("OUTPUT_BEHAVIOR", "ordered", key="order")))
    await publish(workflow.service.requirements, source(declaration("OUTPUT_BEHAVIOR", "unordered", key="order"), source_revision="two"))
    result = await run(workflow)
    assert result["status"] == "insufficient_evidence"
    assert result["functions"][0]["requirements_discovery"]["conflicts"]
    workflow.runner.run.assert_not_awaited()


@pytest.mark.parametrize("error", [TimeoutError("timeout"), RuntimeError("worker stopped")])
async def test_worker_failures_are_terminal_and_do_not_create_replacement_recommendations(workflow, error):
    await contract(workflow)
    workflow.runner.run.side_effect = error
    result = await run(workflow)
    assert result["status"] == "failed"
    assert await workflow.db.recommendations.count_documents({}) == 0


async def test_correctness_failure_prevents_any_superiority_claim(workflow):
    await contract(workflow)
    workflow.runner.run.side_effect = lambda request: passing_evidence(request, ("current", "required"))
    result = await run(workflow)
    assert result["functions"][0]["finding_status"] == "CORRECTNESS_FAILURE"
    child = await workflow.benchmarks.get(result["functions"][0]["benchmark_run_id"])
    assert not child["phase1_eligibility"]["eligible"]
    assert not any(c["winner"] for c in child["decision"]["dataset_comparisons"])


async def test_global_execution_flag_is_preserved(workflow):
    await contract(workflow)
    workflow.service.enabled = False
    result = await run(workflow)
    assert result["status"] == "unsupported" and result["function_discovery"]["functions"]
    workflow.runner.run.assert_not_awaited()


async def test_no_exact_project_repository_organization_mapping_means_no_auto_execution(workflow):
    with pytest.raises(PermissionError):
        await workflow.service.enqueue("P1", "o/unrelated", workflow.pr, [], "PR1", launch=False)
    await workflow.db.projects.update_one({"id": "P1"}, {"$set": {"org_id": ""}})
    with pytest.raises(PermissionError):
        await workflow.service.enqueue("P1", "o/r", workflow.pr, [], "PR1", launch=False)


async def test_pr_sync_compare_and_swap_keeps_stable_id_and_newer_metadata(mock_db):
    repository = PRRepository.__new__(PRRepository)
    repository.col = mock_db.pull_requests
    original = {"id": "stable", "project_id": "P1", "repo_id": "o/r", "pr_number": 1, "head_sha": "new", "updated_at": "2026-11-11T10:00:00Z"}
    await repository.store_revision(original)
    record, accepted = await repository.store_revision({**original, "id": "replacement", "head_sha": "old", "updated_at": "2026-11-11T09:00:00Z"})
    assert not accepted and record["id"] == "stable" and record["head_sha"] == "new"
    record, accepted = await repository.store_revision({**original, "id": "replacement", "head_sha": "latest", "updated_at": "2026-11-11T11:00:00Z"})
    assert accepted and record["id"] == "stable" and record["head_sha"] == "latest"


@pytest.mark.parametrize("language,extension,first,second", [
    ("python", "py", BASE, HEAD),
    ("javascript", "js", "function solve(xs) { return xs; }", "function solve(xs) { return [...xs]; }"),
    ("typescript", "ts", "function solve(xs: number[]): number[] { return xs; }", "function solve(xs: number[]): number[] { return [...xs]; }"),
])
async def test_python_javascript_typescript_previous_current_identification(language, extension, first, second):
    path = "module." + extension
    base = (await discover_sources({path: first}, "P1", "base")).model_dump()
    head = (await discover_sources({path: second}, "P1", "head")).model_dump()
    pairs = changed_functions(base, head, [{"filename": path}], {path: first}, {path: second})
    assert len(pairs) == 1 and pairs[0]["unsupported_reason"] is None
    assert pairs[0]["current"]["language"] == language


async def test_exact_reviewed_base_binding_can_locate_previous_contract(workflow):
    snapshot = (await discover_sources({"module.py": BASE}, "P1", "base")).model_dump()
    await workflow.db.code_quality_runs.insert_one({"run_id": "trusted-base", "repository_id": "P1", "function_discovery": snapshot,
        "source_provenance": {"method": "github-exact-revision", "repository": "o/r", "revision": "base"}})
    await approved(workflow.service.contracts, {**proposal(), "function_bindings": [{"run_id": "trusted-base", "function_id": snapshot["functions"][0]["function_id"]}]})
    result = await run(workflow)
    assert result["status"] == "completed", result.get("error")
    workflow.runner.run.assert_awaited_once()


async def test_untrusted_binding_with_a_declared_git_label_does_not_enable_execution(workflow):
    snapshot = (await discover_sources({"module.py": BASE}, "P1", "base")).model_dump()
    await workflow.db.code_quality_runs.insert_one({"run_id": "untrusted", "repository_id": "P1", "function_discovery": snapshot})
    await approved(workflow.service.contracts, {**proposal(), "function_bindings": [{"run_id": "untrusted", "function_id": snapshot["functions"][0]["function_id"]}]})
    result = await run(workflow)
    assert result["status"] == "insufficient_evidence"
    workflow.runner.run.assert_not_awaited()


async def test_ollama_unavailability_does_not_block_deterministic_workflow(workflow, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(side_effect=RuntimeError("Ollama unavailable")))
    await contract(workflow)
    result = await run(workflow)
    assert result["status"] == "completed"
    # Mandatory advisory may fail independently without changing deterministic results.
    assert result.get("report_status") == "incomplete"


async def test_cancellation_releases_existing_benchmark_lease(workflow):
    await contract(workflow)
    entered = asyncio.Event()
    async def wait_worker(request):
        entered.set()
        await asyncio.Event().wait()
    workflow.runner.run.side_effect = wait_worker
    created = await workflow.service.enqueue("P1", "o/r", workflow.pr, [{"filename": "module.py"}], "PR1", launch=False)
    task = asyncio.create_task(workflow.service.execute(created["run_id"]))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    result = await workflow.service.get(created["run_id"])
    assert result["status"] == "failed"
    child = await workflow.db.algorithm_benchmark_runs.find_one({})
    assert child["active"] is False and child["status"] == "failed"


async def test_pr_revision_current_check_handles_identical_github_update_timestamps(mock_db):
    repository = PRRepository.__new__(PRRepository)
    repository.col = mock_db.pull_requests
    first = {"id": "PR", "project_id": "P1", "repo_id": "o/r", "pr_number": 1, "head_sha": "new", "updated_at": "2026-11-11T10:00:00Z"}
    await repository.store_revision(first)
    record, accepted = await repository.store_revision({**first, "head_sha": "old"}, validate_current=AsyncMock(return_value=False))
    assert not accepted and record["head_sha"] == "new"


LEGACY = "def legacy(xs):\n    return xs\n"
ALGORITHMS = (
    "def alpha(xs):\n"
    "    return sorted(xs)\n"
    "\n"
    "def beta(xs):\n"
    "    return list(sorted(xs))\n"
)
SHARED_ASSERTION = (
    "from module import alpha, beta\n"
    "\n"
    "def test_agree():\n"
    "    assert alpha([3, 1]) == beta([3, 1])\n"
)


async def test_mode_a_function_without_a_predecessor_is_analysed_not_marked_unsupported(workflow):
    workflow.snapshots["base"] = {"module.py": LEGACY}
    workflow.snapshots["head"] = {"module.py": ALGORITHMS}
    result = await run(workflow, [{"filename": "module.py", "status": "modified"}])
    assert result["status"] == "completed", result.get("error")
    assert {row["mode"] for row in result["functions"]} == {"A"}
    for row in result["functions"]:
        assert row["previous"] is None
        assert row["static_status"] == "analyzed"
        assert row["comparison_status"] == "not_applicable"
        assert row["status"] == "analyzed"
        assert row["classification"]["category"] == "application"
        assert row["complexity"]["method"] == "static-ast-complexity-v1"
        assert row["complexity"]["time_complexity"], row["complexity"]
    assert result["comparison_modes"] == {"A": 2}
    workflow.runner.run.assert_not_awaited()


async def test_mode_c_pairs_two_declarations_referenced_by_one_static_assertion(workflow):
    workflow.snapshots["base"] = {"module.py": LEGACY}
    workflow.snapshots["head"] = {"module.py": ALGORITHMS, "test_module.py": SHARED_ASSERTION}
    result = await run(workflow, [{"filename": "module.py", "status": "modified"}])
    rows = result["functions"]
    holders = [row for row in rows if row["mode"] == "C"]
    assert len(holders) == 1, [row["mode"] for row in rows]
    holder = holders[0]
    assert holder["previous"] is not None
    assert holder["previous"]["qualified_name"] in {"alpha", "beta"}
    assert holder["previous"]["qualified_name"] != holder["current"]["qualified_name"]
    assert any("same head revision" in reason for reason in holder["relationship"]["reasons"])
    assert any("neither chronology nor superiority" in limit for limit in holder["relationship"]["limitations"])
    # No approved contract exists, so the comparison must stop before execution.
    assert holder["status"] == "insufficient_evidence"
    assert holder["comparison_status"] == "blocked"
    assert holder["static_status"] == "analyzed"
    other = next(row for row in rows if row["mode"] == "A")
    assert any(holder["current"]["qualified_name"] in limit for limit in other["relationship"]["limitations"])
    assert result["comparison_modes"] == {"C": 1, "A": 1}
    assert result["status"] == "insufficient_evidence"
    workflow.runner.run.assert_not_awaited()


async def test_shared_assertion_does_not_turn_test_support_into_an_alternative(workflow):
    workflow.snapshots["base"] = {"module.py": LEGACY}
    workflow.snapshots["head"] = {
        "module.py": ALGORITHMS,
        "test_module.py": (
            "from module import alpha\n"
            "def sample(values):\n"
            "    return sorted(values)\n"
            "def test_agree():\n"
            "    assert alpha([3, 1]) == sample([3, 1])\n"
        ),
    }
    result = await run(workflow, [
        {"filename": "module.py", "status": "modified"},
        {"filename": "test_module.py", "status": "added"},
    ])
    by_name = {row["current"]["name"]: row for row in result["functions"]}
    assert by_name["alpha"]["mode"] == "A"
    assert by_name["sample"]["classification"]["category"] == "test_helper"
    assert by_name["sample"]["comparison_status"] == "not_applicable"
    assert by_name["test_agree"]["classification"]["category"] == "test"
    workflow.runner.run.assert_not_awaited()


async def test_static_findings_survive_a_comparison_that_could_not_run(workflow):
    workflow.snapshots["base"] = {"module.py": LEGACY}
    workflow.snapshots["head"] = {"module.py": ALGORITHMS}
    result = await run(workflow, [{"filename": "module.py", "status": "modified"}])
    for row in result["functions"]:
        assert row["static"]["status"] == "analyzed"
        assert row["static"]["patterns"], "structural patterns must be recorded"
        assert row["static"]["limitations"] is not None
        assert row["evidence_refs"], "discovery evidence must stay attached"
    assert result["function_discovery"]["functions"]


async def test_a_structurally_unsupported_comparison_still_reports_its_static_analysis(workflow):
    workflow.snapshots["head"] = {
        "module.py": "async def solve(graph, start):\n"
                     "    seen = {start}\n"
                     "    for node in graph[start]:\n"
                     "        if node not in seen:\n"
                     "            seen.add(node)\n"
                     "    return seen\n"}
    result = await run(workflow)
    assert result["status"] == "unsupported"
    row = result["functions"][0]
    assert row["mode"] == "B"
    assert row["comparison_status"] == "unsupported"
    assert row["static_status"] == "analyzed"
    assert row["static"]["classification"]["category"] == "application"
    assert "visited_set_tracking" in row["static"]["patterns"]
    workflow.runner.run.assert_not_awaited()


def test_run_status_distinguishes_nothing_analysed_from_analysis_without_a_comparison():
    from domain.services.pr_algorithm_intelligence_service import run_status
    assert run_status([]) == "unsupported"
    assert run_status([{"status": "unsupported"}]) == "unsupported"
    assert run_status([{"status": "analyzed"}]) == "completed"
    assert run_status([{"status": "analyzed"}, {"status": "unsupported"}]) == "completed"
    assert run_status([{"status": "analyzed"}, {"status": "insufficient_evidence"}]) == "insufficient_evidence"
    assert run_status([{"status": "completed"}]) == "completed"
    assert run_status([{"status": "failed"}]) == "failed"
    assert run_status([{"status": "insufficient_evidence", "finding_status": "CORRECTNESS_FAILURE"}]) == "completed"



async def test_approval_queues_new_revision_without_mutating_original(workflow):
    initial = await run(workflow)
    accepted = await contract(workflow)
    results = await workflow.service.resume_after_approval(accepted, launch=False)
    assert len(results) == 1
    assert results[0]["run_id"] != initial["run_id"]
    assert (await workflow.service.get(initial["run_id"]))["status"] == "insufficient_evidence"
    await workflow.service.execute(results[0]["run_id"])
    assert (await workflow.service.get(results[0]["run_id"]))["functions"][0]["compatibility"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"
    workflow.runner.run.assert_awaited_once()


async def test_approval_does_not_resume_stale_pr(workflow):
    await run(workflow)
    accepted = await contract(workflow)
    workflow.pr["head"]["sha"] = "new-head"
    assert await workflow.service.resume_after_approval(accepted, launch=False) == []
    workflow.runner.run.assert_not_awaited()


async def test_ai_draft_is_not_approval_or_execution(workflow, monkeypatch):
    import json
    import httpx
    from core.config import settings
    monkeypatch.setattr(settings, "ALGORITHM_AI_CONTRACT_PROPOSALS_ENABLED", True)
    value = {"status": "proposed", "input_schema": {"type": "array"}, "output_schema": {"type": "array"},
             "mutation": "forbidden",
             "requirements": [{"description": "Return the required values", "dataset_ids": ["case-1"]}]}
    response = httpx.Response(200, json={"response": json.dumps(value)}, request=httpx.Request("POST", "http://model/api/generate"))
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=response))
    workflow.snapshots["head"]["test_module.py"] = "from module import solve\ndef test_empty():\n    assert solve([]) == []\n"
    result = await run(workflow)
    draft_id = result["functions"][0]["requirement_proposal"]["contract_id"]
    draft = await workflow.service.contracts.get(draft_id)
    assert draft["status"] == "PROPOSED" and draft["approval"] is None
    assert draft["automatic_scope"]["qualified_name"] == "solve"
    assert draft["requirements"][0]["source_reference"].startswith(result["head_discovery_run_id"])
    workflow.runner.run.assert_not_awaited()


async def test_malformed_ai_draft_preserves_static_results(workflow, monkeypatch):
    import httpx
    from core.config import settings
    monkeypatch.setattr(settings, "ALGORITHM_AI_CONTRACT_PROPOSALS_ENABLED", True)
    response = httpx.Response(200, json={"response": '{"status":"APPROVED"}'}, request=httpx.Request("POST", "http://model/api/generate"))
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=response))
    workflow.snapshots["head"]["test_module.py"] = "from module import solve\ndef test_empty():\n    assert solve([]) == []\n"
    result = await run(workflow)
    assert result["functions"][0]["static_status"] == "analyzed"
    assert result["functions"][0]["requirement_proposal"]["status"] == "unavailable"
    assert await workflow.service.contracts.collection.count_documents({}) == 0
    workflow.runner.run.assert_not_awaited()


async def test_ai_draft_without_external_oracle_abstains(workflow, monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "ALGORITHM_AI_CONTRACT_PROPOSALS_ENABLED", True)
    result = await run(workflow)
    assert result["functions"][0]["requirement_proposal"]["status"] == "insufficient_evidence"
    assert not await workflow.service.contracts.collection.count_documents({})
