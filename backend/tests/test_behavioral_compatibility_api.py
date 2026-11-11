"""Authenticated approval and compatibility endpoints reuse existing benchmark storage."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import algorithms
from core.dependencies import get_current_user
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from domain.services.function_contract_service import FunctionContractService
from test_behavioral_compatibility import proposal, body, passing_evidence

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(mock_db, monkeypatch):
    contracts = FunctionContractService(mock_db.algorithm_function_contracts, mock_db.code_quality_runs)
    runner = SimpleNamespace(run=AsyncMock(side_effect=passing_evidence))
    benchmarks = AlgorithmBenchmarkService(mock_db.algorithm_benchmark_runs, runner)
    monkeypatch.setattr(algorithms, "contract_service", contracts)
    monkeypatch.setattr(algorithms, "service", benchmarks)
    monkeypatch.setattr(algorithms, "col", lambda name: mock_db[name])
    monkeypatch.setattr(algorithms.settings, "ALGORITHM_BENCHMARK_ENABLED", True)
    monkeypatch.setattr(algorithms.ProjectRepository, "find_by_id", AsyncMock(side_effect=lambda key: {"id": key, "org_id": "org" if key == "P1" else "foreign"}))
    user = {"employee_id": "author", "org_id": "org", "role": "DEVELOPER", "project_ids": ["P1"]}
    app = FastAPI()
    app.include_router(algorithms.router, prefix="/algorithms")
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(client=client, user=user, contracts=contracts, benchmarks=benchmarks, runner=runner, db=mock_db)


async def publish(api):
    response = await api.client.post("/algorithms/contracts", json=proposal())
    assert response.status_code == 201, response.text
    document = response.json()
    api.user.update(employee_id="reviewer", role="LEAD")
    response = await api.client.post(f"/algorithms/contracts/{document['contract_id']}/approve", json={
        "expected_fingerprint": document["payload_fingerprint"], "source_reference": "review:approved",
        "rationale": "Independently reviewed explicit scope", "scope_reviewed": True})
    assert response.status_code == 200, response.text
    return response.json()


async def test_proposal_is_not_approval_and_self_approval_is_rejected(api):
    response = await api.client.post("/algorithms/contracts", json=proposal())
    document = response.json()
    assert response.status_code == 201 and document["status"] == "PROPOSED"
    api.user["role"] = "LEAD"
    response = await api.client.post(f"/algorithms/contracts/{document['contract_id']}/approve", json={
        "expected_fingerprint": document["payload_fingerprint"], "source_reference": "self", "rationale": "I wrote this", "scope_reviewed": True})
    assert response.status_code == 403
    response = await api.client.post("/algorithms/compatibility/runs", json=body([document["contract_id"]]))
    assert response.status_code == 202
    run = (await api.client.get('/algorithms/runs/' + response.json()['run_id'])).json()
    assert run["behavioral_compatibility"]["status"] == "UNVERIFIED"
    api.runner.run.assert_not_awaited()


async def test_approved_comparison_persists_worker_evidence_and_conservative_decision(api):
    document = await publish(api)
    response = await api.client.post("/algorithms/compatibility/runs", json=body([document["contract_id"]]))
    assert response.status_code == 202, response.text
    run = (await api.client.get('/algorithms/runs/' + response.json()['run_id'])).json()
    assert run["status"] == "completed", run.get("error")
    assert run["behavioral_compatibility"]["status"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"
    assert run["phase1_eligibility"]["eligible"]
    assert run["decision"]["task_suitability"]["global_winner"] is None
    assert run["decision"]["policy_snapshot"]["objective"] == "TRADEOFF_ONLY"
    response = await api.client.get('/algorithms/projects/P1/contracts')
    assert response.status_code == 200 and response.json()["contracts"][0]["approval"]["approved_by"] == "reviewer"


async def test_missing_contract_can_be_reported_with_workers_disabled(api, monkeypatch):
    monkeypatch.setattr(algorithms.settings, "ALGORITHM_BENCHMARK_ENABLED", False)
    response = await api.client.post("/algorithms/compatibility/runs", json=body())
    assert response.status_code == 202
    run = (await api.client.get('/algorithms/runs/' + response.json()['run_id'])).json()
    assert run["behavioral_compatibility"]["status"] == "CONTRACT_MISSING"
    assert run["recommendation"] is None


async def test_contracts_and_runs_do_not_cross_organization_boundaries(api):
    document = await publish(api)
    api.user["org_id"] = "another-org"
    assert (await api.client.get('/algorithms/contracts/' + document['contract_id'])).status_code == 403
    assert (await api.client.post('/algorithms/compatibility/runs', json=body([document['contract_id']]))).status_code == 403


async def test_client_cannot_submit_authority_or_executable_validator(api):
    value = proposal()
    value["status"] = "APPROVED"
    assert (await api.client.post('/algorithms/contracts', json=value)).status_code == 422
    value = proposal()
    value["contract"]["validator"] = "lambda result: True"
    assert (await api.client.post('/algorithms/contracts', json=value)).status_code == 422


async def test_phase2_context_requires_matching_source_hash_and_project(api):
    document = await publish(api)
    await api.db.code_quality_runs.insert_one({"run_id": "discovery", "repository_id": "P1", "function_discovery": {"method": "function-purpose-v1", "status": "available", "functions": [{
        "function_id": "fn", "source_hash": "different-source", "language": "python", "name": "solve"}]}})
    value = body([document['contract_id']])
    value["previous"]["function_reference"] = {"run_id": "discovery", "function_id": "fn"}
    response = await api.client.post('/algorithms/compatibility/runs', json=value)
    assert response.status_code == 202
    run = (await api.client.get('/algorithms/runs/' + response.json()['run_id'])).json()
    assert run['behavioral_compatibility']['status'] == 'UNVERIFIED'
    assert any('snapshot' in message for message in run['behavioral_compatibility']['unverified_behavior'])
    api.runner.run.assert_not_awaited()


async def test_provisional_relationship_endpoint_and_history_are_read_only(api):
    function = {"function_id": "old", "path": "m.py", "qualified_name": "solve", "source_hash": "before", "source_revision": "parent"}
    for run_id, fn in [("before", function), ("after", {**function, "function_id": "new", "source_hash": "after", "source_revision": "head"})]:
        await api.db.code_quality_runs.insert_one({"run_id": run_id, "repository_id": "P1", "function_discovery": {"functions": [fn]}})
    response = await api.client.get('/algorithms/compatibility/relationships', params={"project_id": "P1", "previous_run_id": "before", "current_run_id": "after"})
    assert response.status_code == 200, response.text
    assert response.json()["relationships"][0]["status"] == "PROVISIONAL"
    assert response.json()["execution_performed"] is False
    history = await api.client.get('/algorithms/compatibility/functions/old/history', params={"project_id": "P1"})
    assert history.status_code == 200 and history.json()["historical_only"] is True
    api.runner.run.assert_not_awaited()
