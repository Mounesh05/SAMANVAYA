"""Opt-in execution checks. Submitted source executes only in isolated Docker."""

import os

import pytest

from domain.schemas.algorithm_benchmark import BenchmarkRequest
from intelligence.algorithms.decision import evaluate_decision
from intelligence.algorithms.runner import DockerBenchmarkRunner

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(
    os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
    reason="Requires isolated Docker Linux host and rebuilt pinned independent-v1 workers")]


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
async def test_new_policy_real_worker_protocol_and_expected_output(language):
    source = ("def solve(a, b): return a + b" if language == "python" else
              "function solve(a, b) { return a + b; }")
    request = BenchmarkRequest.model_validate({
        "project_id": "test", "language": language, "repetitions": 3,
        "candidates": [{"name": "one", "entrypoint": "solve", "source": source}],
        "contract": {"kind": "function", "name": "fixture-add", "version": "1",
                     "input_schema": {"type": "array"}, "output_schema": {"type": "number"}, "correctness": "expected"},
        "datasets": [{"id": "tested", "args": [2, 3], "expected": 5}],
        "decision_policy": {"id": "docker-smoke", "version": "1", "objective": "MINIMIZE_TIME"},
    }).model_dump()
    evidence = await DockerBenchmarkRunner().run(request)
    case = evidence["results"][0]["cases"][0]
    assert case["correct"] is True and case["measurement_version"] == "independent-v1"
    assert case["timing_status"] == "AVAILABLE"
    decision = evaluate_decision(request, evidence, request["decision_policy"])
    assert decision["candidates"][0]["task_eligibility"] == "ELIGIBLE"
    assert decision["dataset_comparisons"][0]["winner"] is None


async def test_real_python_memory_invocation_correctness_failure_is_contract_wide():
    request = BenchmarkRequest.model_validate({
        "project_id": "test", "language": "python", "repetitions": 3,
        "candidates": [{"name": "stateful", "entrypoint": "solve", "source":
            "calls = 0\ndef solve(a):\n    global calls\n    calls += 1\n    return a if calls != 6 else -1"}],
        "contract": {"kind": "function", "name": "identity", "version": "1",
                     "input_schema": {"type": "array"}, "output_schema": {}, "correctness": "expected"},
        "datasets": [{"id": "first", "args": [3], "expected": 3}, {"id": "second", "args": [4], "expected": 4}],
        "decision_policy": {"id": "docker-memory", "version": "1"},
    }).model_dump()
    evidence = await DockerBenchmarkRunner().run(request)
    assert evidence["results"][0]["cases"][0]["correct"] is False
    decision = evaluate_decision(request, evidence, request["decision_policy"])
    assert all(d["eligibility"] == "INELIGIBLE" for d in decision["candidates"][0]["datasets"])
