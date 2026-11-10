"""Service/API revisions and worker instrumentation without submitted-code execution."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import algorithms
from benchmark_worker import python_worker
from core.dependencies import get_current_user
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService, raw_evidence
from intelligence.algorithms.runner import DockerBenchmarkRunner
from test_deterministic_decision import fixture, constraint
from test_function_workers import node_data

pytestmark = pytest.mark.anyio


@pytest.fixture
async def context(mock_db, monkeypatch):
    request, evidence, policy = fixture()
    request["decision_policy"] = policy
    runner = DockerBenchmarkRunner()
    runner.run = AsyncMock(return_value=evidence)
    service = AlgorithmBenchmarkService(mock_db.decisions, runner)
    monkeypatch.setattr(algorithms, "service", service)
    monkeypatch.setattr(algorithms.settings, "ALGORITHM_BENCHMARK_ENABLED", True)
    monkeypatch.setattr(algorithms.ProjectRepository, "find_by_id", AsyncMock(return_value={"id": "P1", "org_id": "O1"}))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(side_effect=AssertionError("No worker execution")))
    user = {"employee_id": "E1", "role": "DEVELOPER", "org_id": "O1", "project_ids": ["P1"]}
    app = FastAPI()
    app.include_router(algorithms.router, prefix="/algorithms")
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(request=request, evidence=evidence, policy=policy, runner=runner, service=service,
                              user=user, client=client, monkeypatch=monkeypatch)


async def complete(ctx):
    created = await ctx.service.create(ctx.request, ctx.user)
    await ctx.service.execute(created["run_id"])
    document = await ctx.service.get(created["run_id"])
    assert document["status"] == "completed", document.get("error")
    return document


async def test_policy_run_persists_initial_revision_and_server_provenance(context):
    doc = await complete(context)
    assert doc["decision"]["revision_number"] == 1
    assert doc["decision_revisions"] == [doc["decision"]]
    assert doc["decision"]["provenance"]["established_by"] == "E1"
    assert doc["decision"]["provenance"]["organization_id"] == "O1"
    assert doc["immutable_evidence_fingerprint"] == doc["decision"]["identities"]["evidence"]
    history = (await context.service.history("P1"))[0]
    assert "source" not in history["request"]["candidates"][0]
    assert history["decision"] == doc["decision"]


async def test_reevaluation_preserves_evidence_original_decision_and_legacy_recommendation(context):
    doc = await complete(context)
    before = copy.deepcopy(doc)
    context.runner.run.reset_mock()
    policy = {**context.policy, "id": "strict", "constraints": [constraint(threshold=0.1)]}
    response = await context.client.post(f"/algorithms/runs/{doc['run_id']}/reevaluate", json={"decision_policy": policy})
    assert response.status_code == 200, response.text
    revision = response.json()
    assert revision["revision_number"] == 2
    assert revision["task_suitability"]["status"] == "NO_ELIGIBLE_IMPLEMENTATION"
    after = await context.service.get(doc["run_id"])
    assert after["recommendation"] == before["recommendation"]
    assert raw_evidence(after) == raw_evidence(before)
    assert after["request"] == before["request"]
    assert after["decision_revisions"][0] == before["decision"]
    assert after["decision"] == revision
    context.runner.run.assert_not_awaited()


async def test_concurrent_revisions_are_atomic_and_ordered(context):
    doc = await complete(context)
    revisions = await asyncio.gather(*(context.service.reevaluate(doc["run_id"], {**context.policy, "id": f"p-{i}"}, context.user) for i in range(8)))
    after = await context.service.get(doc["run_id"])
    assert sorted(r["revision_number"] for r in revisions) == list(range(2, 10))
    assert len(after["decision_revisions"]) == 9
    assert len({r["revision_id"] for r in after["decision_revisions"]}) == 9
    assert after["decision"]["revision_number"] == 9
    assert raw_evidence(after) == raw_evidence(doc)


async def test_legacy_completed_run_can_receive_first_explicit_revision_without_reexecution(context):
    context.request.pop("decision_policy")
    doc = await complete(context)
    assert "decision" not in doc
    context.runner.run.reset_mock()
    revision = await context.service.reevaluate(doc["run_id"], context.policy, context.user)
    assert revision["revision_number"] == 1
    assert (await context.service.get(doc["run_id"]))["recommendation"] == doc["recommendation"]
    context.runner.run.assert_not_awaited()


async def test_tampered_preserved_evidence_rejected(context):
    doc = await complete(context)
    await context.service.collection.update_one({"run_id": doc["run_id"]}, {"$set": {"results.0.cases.0.memory_bytes": 999}})
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        await context.service.reevaluate(doc["run_id"], context.policy, context.user)


async def test_changed_functional_context_rejected_without_changing_revisions(context):
    doc = await complete(context)
    await context.service.collection.update_one({"run_id": doc["run_id"]}, {"$set": {"request.datasets.0.expected": 999}})
    with pytest.raises(ValueError, match="execution context fingerprint mismatch"):
        await context.service.reevaluate(doc["run_id"], context.policy, context.user)
    after = await context.service.get(doc["run_id"])
    assert after["decision_revisions"] == doc["decision_revisions"]


@pytest.mark.parametrize("role,org,projects,status", [("HR", "O1", ["P1"], 403), ("DEVELOPER", "O2", ["P1"], 403),
    ("DEVELOPER", "O1", [], 403), ("DEVELOPER", "O1", ["P1"], 200)])
async def test_reevaluation_uses_existing_project_authorization(context, role, org, projects, status):
    doc = await complete(context)
    context.user.update(role=role, org_id=org, project_ids=projects)
    response = await context.client.post(f"/algorithms/runs/{doc['run_id']}/reevaluate", json={"decision_policy": context.policy})
    assert response.status_code == status, response.text


@pytest.mark.parametrize("payload", [{"approved": True}, {"provenance": {"established_by": "CEO"}}, {"constraints": [constraint(approved=True)]}])
async def test_api_rejects_forged_authority_before_execution(context, payload):
    response = await context.client.post("/algorithms/runs", json={**context.request,
        "decision_policy": {**context.policy, **payload}})
    assert response.status_code == 422
    context.runner.run.assert_not_awaited()


async def test_reevaluation_rejects_pending_run_and_unknown_run(context):
    created = await context.service.create(context.request, context.user)
    for run_id, status in ((created["run_id"], 409), ("missing", 404)):
        response = await context.client.post(f"/algorithms/runs/{run_id}/reevaluate", json={"decision_policy": context.policy})
        assert response.status_code == status


async def test_new_explanation_never_selects_legacy_winner_or_model_invented_facts(context, monkeypatch):
    doc = await complete(context)
    await context.service.reevaluate(doc["run_id"], {**context.policy, "constraints": [constraint(threshold=0.1)]}, context.user)
    doc = await context.service.get(doc["run_id"])
    original_client = httpx.AsyncClient
    seen = []
    async def handler(request):
        seen.append(json.loads(request.content)["prompt"])
        return httpx.Response(200, json={"response": json.dumps({"statement_ids": ["current", "dataset-0", "constraint-0-0"]})})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler)))
    answer = await context.service.explain(doc)
    assert answer["status"] == "generated"
    assert "NO_ELIGIBLE_IMPLEMENTATION" in answer["explanation"]
    assert "Recommendation: a" not in seen[0]
    async def broken(request):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(broken)))
    answer = await context.service.explain(doc)
    assert answer["status"] == "unavailable"
    assert "NO_ELIGIBLE_IMPLEMENTATION" in answer["explanation"]
    assert doc["decision"] == (await context.service.get(doc["run_id"]))["decision"]


async def test_worker_only_receives_server_selected_protocol_not_policy(context):
    runner = DockerBenchmarkRunner()
    async def command(*args, data=None):
        if args[0] == "run":
            payload = json.loads(data)
            assert payload["measurement_protocol"] == "independent-v1"
            assert "decision_policy" not in payload
            result = {"environment": {}, "tools": {}, "result": context.evidence["results"][0]}
            return 0, json.dumps(result).encode(), b""
        return 0, b"", b""
    context.monkeypatch.setattr(runner, "_command", command)
    await runner._candidate(context.request, context.request["candidates"][0])


async def test_python_worker_instrumentation_failures_and_memory_phase_correctness(monkeypatch):
    # Trusted fixed harness callback, never compile/exec candidate source on host.
    request, _, _ = fixture()
    counter = iter(range(100))
    clock = SimpleNamespace(perf_counter=lambda: next(counter))
    # Instrumentation is mocked completely; do not depend on Windows /tmp or
    # the shell sandbox's OS temp-directory permissions.
    with monkeypatch.context() as instrument:
        instrument.setattr(python_worker.tempfile, "TemporaryDirectory", lambda **kw: SimpleNamespace(name="unused", cleanup=lambda: None))
        result = {"cases": []}
        python_worker.benchmark_independent_cases(request, lambda a, b: a + b, result, None, clock)
        assert result["cases"][0]["correct"] is True
        assert result["cases"][0]["timing_status"] == "AVAILABLE"
        assert result["cases"][0]["memory_status"] == "UNAVAILABLE"
        class Tracker:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): pass
            def __exit__(self, *args): pass
        memory = SimpleNamespace(Tracker=Tracker, FileReader=lambda _: SimpleNamespace(
            get_high_watermark_allocation_records=lambda: [SimpleNamespace(size=12)]))
        result = {"cases": []}
        python_worker.benchmark_independent_cases(request, lambda a, b: a + b, result, memory, None)
        assert result["cases"][0]["correct"] is True
        assert result["cases"][0]["timing_status"] == "UNAVAILABLE"
        assert result["cases"][0]["memory_bytes"] == 12
        calls = 0
        def fixed_harness_callback(a, b):
            nonlocal calls
            calls += 1
            return a + b if calls != 6 else -1
        result = {"cases": []}
        python_worker.benchmark_independent_cases(request, fixed_harness_callback, result, memory, clock)
        assert result["cases"][0]["correct"] is False
        assert result["cases"][0]["validation_status"] == "failed"
        assert "expected JSON" in result["cases"][0]["error"]
        assert result["cases"][0]["timing_status"] == "AVAILABLE"


@pytest.mark.parametrize("mode", ["no-clock", "no-memory", "zero-clock", "memory-correctness"])
async def test_node_independent_instrumentation_with_trusted_fixed_callbacks(mode):
    request, _, _ = fixture("javascript")
    result = node_data("""
const data = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
let tick = 0, call = 0;
const clock = () => { if (data.mode === 'no-clock') throw new Error('clock absent'); return data.mode === 'zero-clock' ? 0 : ++tick; };
const memory = () => { if (data.mode === 'no-memory') throw new Error('memory absent'); return ++tick; };
const result = {cases: []};
w.benchmarkIndependentCases(data.request, (a,b) => { ++call; return data.mode === 'memory-correctness' && call === 6 ? -1 : a+b; }, result, clock, memory);
console.log(JSON.stringify(result));
""", {"request": request, "mode": mode})
    c = result["cases"][0]
    assert c["correct"] is (mode != "memory-correctness")
    if mode == "no-clock":
        assert c["timing_status"] == "UNAVAILABLE" and c["memory_status"] == "AVAILABLE"
    elif mode == "no-memory":
        assert c["timing_status"] == "AVAILABLE" and c["memory_status"] == "UNAVAILABLE"
    elif mode == "zero-clock":
        assert c["timing_status"] == "INVALID" and c["timings_seconds"] == [0, 0, 0]
    else:
        assert c["error"] and c["validation_status"] == "failed"


async def test_python_memory_region_excludes_cloning_validation_and_cleanup_failures(monkeypatch):
    request, _, _ = fixture()
    tracking = False
    class Tracker:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self):
            nonlocal tracking
            tracking = True
        def __exit__(self, *args):
            nonlocal tracking
            tracking = False
    def cleanup():
        raise PermissionError("Mocked optional cleanup failure")
    original_clone = copy.deepcopy
    original_check = python_worker.check_function_result
    def checked_clone(value):
        assert not tracking, "Input copying must be outside memory measurement"
        return original_clone(value)
    def checked_validation(*args):
        assert not tracking, "Validation must be outside memory measurement"
        return original_check(*args)
    monkeypatch.setattr(python_worker.copy, "deepcopy", checked_clone)
    monkeypatch.setattr(python_worker, "check_function_result", checked_validation)
    monkeypatch.setattr(python_worker.tempfile, "TemporaryDirectory", lambda **kw: SimpleNamespace(name="unused", cleanup=cleanup))
    memray = SimpleNamespace(Tracker=Tracker, FileReader=lambda _: SimpleNamespace(
        get_high_watermark_allocation_records=lambda: [SimpleNamespace(size=12)]))
    counter = iter(range(100))
    result = {"cases": []}
    python_worker.benchmark_independent_cases(request, lambda a, b: a + b, result, memray,
                                            SimpleNamespace(perf_counter=lambda: next(counter)))
    assert all(c["correct"] is True and c["memory_bytes"] == 12 for c in result["cases"])
    assert all(c["timing_status"] == "AVAILABLE" for c in result["cases"])
