"""Opt-in Phase 4 evidence flows through unchanged isolated benchmark workers."""

import os

import pytest

from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from domain.services.requirement_discovery_service import RequirementDiscoveryService
from intelligence.algorithms.runner import DockerBenchmarkRunner
from test_requirement_discovery import publish, source, declaration
from test_behavioral_compatibility import AUTHOR

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
    reason="Requires running Linux Docker backend and built worker images")]


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
async def test_approved_latency_bound_applies_to_real_worker_results(mock_db, language):
    requirements = RequirementDiscoveryService(mock_db)
    await publish(requirements, source(declaration(value=0)))
    code = ("def solve(a, b): return a + b" if language == "python" else
            "function solve(a: number, b: number): number { return a + b; }" if language == "typescript" else
            "function solve(a, b) { return a + b; }")
    service = AlgorithmBenchmarkService(mock_db.algorithm_benchmark_runs, DockerBenchmarkRunner(), requirements)
    created = await service.create({"project_id": "P1", "language": language,
        "contract": {"kind": "function", "name": "sum", "version": "1", "correctness": "expected", "input_schema": {"type": "array"}, "output_schema": {"type": "number"}},
        "datasets": [{"id": "sum", "args": [2, 3], "expected": 5}],
        "candidates": [{"name": "candidate", "entrypoint": "solve", "source": code}],
        "repetitions": 3, "seed": 42, "objective": "time", "resources": {}}, AUTHOR)
    await service.execute(created["run_id"])
    result = await service.get(created["run_id"])
    assert result["status"] == "completed", result.get("error")
    assert result["results"][0]["cases"][0]["correct"] is True
    assert result["environment"]["isolation"] == "docker" and result["environment"]["network"] == "none"
    assert result["decision"]["candidates"][0]["task_eligibility"] == "INELIGIBLE"
    assert result["decision"]["candidates"][0]["constraint_evaluations"][0]["status"] == "FAIL"
    assert result["recommendation"]["winner"] is None
    assert result["requirements_discovery"]["established"][0]["source_revision"] == "revision-1"
