"""Data-only compatibility policy and approval checks; no candidate code runs on the host."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from benchmark_worker.contracts import matches_expected, validate_function_payload
from domain.schemas.behavioral_compatibility import ContractProposal, ContractApproval, BehavioralComparisonRequest
from domain.services.function_contract_service import FunctionContractService
from domain.services.behavioral_compatibility_service import BehavioralCompatibilityService
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from intelligence.algorithms.compatibility import evaluate_compatibility, COMPATIBLE, provisional_relationships
from intelligence.algorithms.decision import evaluate_decision, fingerprint
from intelligence.algorithms.evidence import recommend

AUTHOR = {"employee_id": "author", "org_id": "org", "role": "DEVELOPER"}
REVIEWER = {"employee_id": "reviewer", "org_id": "org", "role": "LEAD"}


def proposal(mode="exact", name="requirements"):
    return {"project_id": "P1", "contract": {"kind": "function", "name": name, "version": "1",
        "input_schema": {"type": "array"}, "output_schema": {"type": "array"},
        "correctness": "expected", "mutation": "forbidden", "comparison": {"mode": mode, "version": "1"}},
        "datasets": [{"id": "empty", "args": [[]], "expected": []}, {"id": "required", "args": [[1, 2]], "expected": [1, 2]}],
        "required_dataset_ids": ["empty", "required"], "requirements": [{"id": "req", "description": "Return the required values", "source_reference": "specification:1", "dataset_ids": ["empty", "required"]}],
        "scope_description": "Only these reviewed inputs; no universal-equivalence claim"}


def body(contract_ids=()):
    return {"project_id": "P1", "contract_ids": list(contract_ids),
        "previous": {"name": "before", "source": "def solve(xs): return xs", "entrypoint": "solve", "language": "python"},
        "current": {"name": "after", "source": "def solve(xs): return list(xs)", "entrypoint": "solve", "language": "python"}}


async def approved(contracts, payload=None):
    document = await contracts.propose(proposal() if payload is None else payload, AUTHOR)
    review = ContractApproval(expected_fingerprint=document["payload_fingerprint"], source_reference="review:1", rationale="Reviewed expected outputs and required scope", scope_reviewed=True)
    return await contracts.approve(document, review.model_dump(), REVIEWER)


def passing_evidence(request, failure=None):
    rows = []
    for candidate in request["candidates"]:
        cases = []
        for dataset in request["datasets"]:
            fail = failure == (candidate["name"], dataset["id"])
            cases.append({"case_id": dataset["id"], "dimensions": dataset.get("dimensions", {}),
                "correct": not fail, "validation_status": "failed" if fail else "verified",
                "error": "ContractViolation: wrong output" if fail else None,
                "behavioral_validation": {"version": "functional-validation-v1", "status": "FAIL" if fail else "PASS", "validated_calls": 0 if fail else request["repetitions"] + 3},
                "timings_seconds": [0.01] * request["repetitions"], "memory_bytes": 10,
                "memory_metric": "memray_peak_tracked_allocations_bytes"})
        rows.append({"candidate": candidate["name"], "error": None, "cases": cases})
    return {"results": rows, "environment": {"isolation": "docker", "network": "none"}, "tools": {}}


@pytest.fixture
def services(mock_db):
    contracts = FunctionContractService(mock_db.algorithm_function_contracts, mock_db.code_quality_runs)
    runner = SimpleNamespace(run=AsyncMock())
    benchmarks = AlgorithmBenchmarkService(mock_db.algorithm_benchmark_runs, runner)
    return SimpleNamespace(contracts=contracts, benchmarks=benchmarks, runner=runner,
                           compatibility=BehavioralCompatibilityService(benchmarks, contracts, mock_db.code_quality_runs), db=mock_db)


@pytest.mark.parametrize("mode,output,expected,match", [
    ("exact", [2, 1], [1, 2], False),
    ("unordered_set", [2, 1], [1, 2], True),
    ("unordered_set", [1, 1, 2], [1, 2], True),
    ("unordered_multiset", [2, 1, 1], [1, 2, 1], True),
    ("unordered_multiset", [1, 2], [1, 2, 1], False),
    ("unordered_set", [True], [1], False),
    ("unordered_set", [[2, 1]], [[1, 2]], False),
])
def test_comparison_is_explicit_and_preserves_nested_order_and_types(mode, output, expected, match):
    contract = proposal(mode)["contract"]
    assert matches_expected(output, {"expected": expected}, contract) is match


def test_approved_finite_acceptable_outputs_preserve_order_within_each_path():
    contract = proposal("one_of")["contract"]
    dataset = {"id": "paths", "args": [], "expected": ["s", "a", "t"], "acceptable_outputs": [["s", "a", "t"], ["s", "b", "t"]]}
    validate_function_payload({"contract": contract, "datasets": [dataset]})
    assert matches_expected(["s", "b", "t"], dataset, contract)
    assert not matches_expected(["t", "b", "s"], dataset, contract)


def test_stable_order_is_not_erased_from_exact_contract():
    contract = proposal()["contract"]
    expected = [{"key": 1, "original": "a"}, {"key": 1, "original": "b"}]
    assert not matches_expected(list(reversed(expected)), {"expected": expected}, contract)


def test_native_python_sets_need_explicit_set_semantics():
    from benchmark_worker.python_worker import check_function_result
    from benchmark_worker.contracts import ContractViolation
    data = {"args": [], "expected": [1, 2]}
    check_function_result({2, 1}, [], data, proposal("unordered_set")["contract"])
    with pytest.raises(ContractViolation):
        check_function_result({2, 1}, [], data, proposal("exact")["contract"])


def test_validator_code_and_unapproved_comparison_options_are_rejected(tmp_path):
    value = proposal()
    value["contract"]["validator"] = "def validate(output): return True"
    with pytest.raises(ValidationError):
        ContractProposal.model_validate(value)
    value = proposal()
    value["contract"]["comparison"] = {"mode": "exact", "version": "1", "ignore_order": True}
    with pytest.raises(ValidationError):
        ContractProposal.model_validate(value)
    request = body()
    request["compatibility_context"] = {"resolution": {"status": "APPROVED"}}
    with pytest.raises(ValidationError):
        BehavioralComparisonRequest.model_validate(request)


@pytest.mark.anyio
async def test_contract_approval_is_independent_role_scoped_atomic_and_immutable(services):
    document = await services.contracts.propose(proposal(), AUTHOR)
    review = {"expected_fingerprint": document["payload_fingerprint"], "source_reference": "review", "rationale": "scope checked", "scope_reviewed": True}
    with pytest.raises(PermissionError):
        await services.contracts.approve(document, review, AUTHOR)
    with pytest.raises(PermissionError):
        await services.contracts.approve(document, review, {**AUTHOR, "employee_id": "other"})
    with pytest.raises(ValueError):
        await services.contracts.approve(document, {**review, "expected_fingerprint": "changed"}, REVIEWER)
    result = await services.contracts.approve(document, review, REVIEWER)
    assert result["status"] == "APPROVED"
    with pytest.raises(ValueError):
        await services.contracts.approve(result, review, REVIEWER)
    assert (await services.contracts.resolve("P1", [document["contract_id"]]))["status"] == "APPROVED"
    assert (await services.contracts.resolve("foreign", [document["contract_id"]]))["status"] == "MISSING"


@pytest.mark.anyio
async def test_missing_and_proposed_contracts_do_not_execute_or_establish_compatibility(services):
    created = await services.compatibility.create(body(), AUTHOR)
    run = await services.benchmarks.get(created["run_id"])
    assert run["behavioral_compatibility"]["status"] == "CONTRACT_MISSING"
    assert run["behavioral_compatibility"]["evidence_refs"]
    document = await services.contracts.propose(proposal(), AUTHOR)
    created = await services.compatibility.create(body([document["contract_id"]]), AUTHOR)
    run = await services.benchmarks.get(created["run_id"])
    assert run["behavioral_compatibility"]["status"] == "UNVERIFIED"
    assert not run["phase1_eligibility"]["eligible"]
    services.runner.run.assert_not_awaited()


@pytest.mark.anyio
async def test_conflicting_approved_contracts_cannot_be_silently_selected(services):
    one = await approved(services.contracts)
    two = await approved(services.contracts, proposal("unordered_set", "other-requirements"))
    created = await services.compatibility.create(body([one["contract_id"], two["contract_id"]]), AUTHOR)
    run = await services.benchmarks.get(created["run_id"])
    assert run["behavioral_compatibility"]["status"] == "UNVERIFIED"
    assert run["behavioral_compatibility"]["contract_resolution"]["status"] == "CONFLICTING"
    services.runner.run.assert_not_awaited()


@pytest.mark.anyio
async def test_matching_signatures_need_actual_behavioral_evidence_and_complete_coverage(services):
    contract = await approved(services.contracts)
    created = await services.compatibility.create(body([contract["contract_id"]]), AUTHOR)
    run = await services.benchmarks.get(created["run_id"])
    request = run["request"]
    evidence = passing_evidence(request)
    result = evaluate_compatibility(request, evidence, run["run_id"])
    assert result["status"] == COMPATIBLE and result["phase1_eligible"]
    evidence["behavioral_compatibility"] = result
    decision = evaluate_decision(request, evidence, request["decision_policy"], run["run_id"])
    assert decision["task_suitability"]["eligible_candidates"] == ["before", "after"]
    failing = passing_evidence(request, failure=("after", "required"))
    failing["behavioral_compatibility"] = evaluate_compatibility(request, failing, run["run_id"])
    assert failing["behavioral_compatibility"]["status"] == "INCOMPATIBLE"
    assert recommend(request, failing)["winner"] is None
    decision = evaluate_decision(request, failing, request["decision_policy"])
    assert not decision["task_suitability"]["eligible_candidates"]
    assert all(row["winner"] is None for row in decision["dataset_comparisons"])


@pytest.mark.anyio
async def test_insufficient_coverage_cannot_be_fixed_by_policy_reevaluation(services):
    document = await approved(services.contracts)
    request_body = {**body([document["contract_id"]]), "dataset_ids": ["empty"]}
    created = await services.compatibility.create(request_body, AUTHOR)
    run = await services.benchmarks.get(created["run_id"])
    request = run["request"]
    evidence = passing_evidence(request)
    evidence["behavioral_compatibility"] = evaluate_compatibility(request, evidence, run["run_id"])
    assert evidence["behavioral_compatibility"]["status"] == "UNVERIFIED"
    await services.benchmarks._finish(run["run_id"], {**evidence, "status": "completed"})
    revision = await services.benchmarks.reevaluate(run["run_id"], {"id": "cannot-bypass", "version": "1", "required_dataset_ids": ["empty"], "objective": "MINIMIZE_TIME"}, REVIEWER)
    assert not revision["task_suitability"]["eligible_candidates"]


@pytest.mark.anyio
async def test_execution_errors_and_old_worker_flags_are_unverified_not_behavioral_proof(services):
    document = await approved(services.contracts)
    created = await services.compatibility.create(body([document["contract_id"]]), AUTHOR)
    request = (await services.benchmarks.get(created["run_id"]))["request"]
    evidence = passing_evidence(request)
    for row in evidence["results"]:
        for case in row["cases"]:
            case.pop("behavioral_validation")
    assert evaluate_compatibility(request, evidence, "run")["status"] == "UNVERIFIED"
    evidence = passing_evidence(request)
    evidence["results"][0]["cases"][0].update(correct=False, validation_status="failed", error="MemoryError")
    evidence["results"][0]["cases"][0]["behavioral_validation"]["status"] = "UNVERIFIED"
    assert evaluate_compatibility(request, evidence, "run")["status"] == "UNVERIFIED"


@pytest.mark.anyio
async def test_changed_datasets_or_source_cannot_reuse_approved_validation(services):
    document = await approved(services.contracts)
    created = await services.compatibility.create(body([document["contract_id"]]), AUTHOR)
    request = (await services.benchmarks.get(created["run_id"]))["request"]
    evidence = passing_evidence(request)
    evidence["behavioral_compatibility"] = evaluate_compatibility(request, evidence, "run")
    modified = copy.deepcopy(request)
    modified["datasets"][0]["expected"] = ["changed"]
    assert evaluate_compatibility(modified, evidence, "run")["status"] == "UNVERIFIED"
    modified = copy.deepcopy(request)
    modified["candidates"][1]["source"] += "\n# changed revision"
    assert evaluate_compatibility(modified, evidence, "run")["status"] == "UNVERIFIED"


@pytest.mark.anyio
@pytest.mark.parametrize("requirement", ["numerical_tolerance", "property_oracle", "stability_oracle"])
async def test_approved_but_unsupported_oracles_remain_unverified_without_execution(services, requirement):
    payload = {**proposal(), "validator_requirement": requirement}
    document = await approved(services.contracts, payload)
    created = await services.compatibility.create(body([document["contract_id"]]), AUTHOR)
    report = (await services.benchmarks.get(created["run_id"]))["behavioral_compatibility"]
    assert report["status"] == "UNVERIFIED"
    assert "validator" in report["unverified_behavior"][0]
    services.runner.run.assert_not_awaited()


@pytest.mark.anyio
async def test_phase2_task_hypothesis_is_context_not_contract_authority(services):
    from intelligence.algorithms.discovery.service import discover_sources
    request = body()
    request["previous"]["source"] = "def solve(xs): return sorted(xs)"
    snapshot = await discover_sources({"m.py": request["previous"]["source"]}, "P1", "previous-sha")
    assert snapshot.functions[0].possible_task == "collection_ordering"
    await services.db.code_quality_runs.insert_one({"run_id": "phase2", "repository_id": "P1", "function_discovery": snapshot.model_dump()})
    request["previous"]["function_reference"] = {"run_id": "phase2", "function_id": snapshot.functions[0].function_id}
    created = await services.compatibility.create(request, AUTHOR)
    report = (await services.benchmarks.get(created["run_id"]))["behavioral_compatibility"]
    assert report["previous"]["phase2_context"]["possible_task"] == "collection_ordering"
    assert report["status"] == "CONTRACT_MISSING" and not report["phase1_eligible"]
    services.runner.run.assert_not_awaited()


def test_relationships_use_revision_identity_and_context_without_certifying_replacement():
    before = {"function_id": "old", "path": "m.py", "qualified_name": "solve", "source_hash": "old-hash", "source_revision": "parent", "task_hypotheses": [{"kind": "graph_reachability"}]}
    after = {**before, "function_id": "new", "source_hash": "new-hash", "source_revision": "head"}
    relationships = provisional_relationships({"functions": [before]}, {"functions": [after]}, "old-run", "new-run")
    assert relationships[0]["status"] == "PROVISIONAL"
    assert relationships[0]["previous"]["source_revision"] == "parent"
    assert relationships[0]["evidence_refs"]
