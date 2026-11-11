"""Fresh PR base/head comparisons in the existing network-disabled worker images."""

import os
import asyncio
from contextlib import suppress

import pytest

from intelligence.algorithms.runner import DockerBenchmarkRunner
from test_pr_algorithm_intelligence import workflow, run, contract
from test_behavioral_compatibility import approved
from test_behavioral_compatibility_docker import GRAPH, REACHABLE, PY_BFS, JS_BFS, PY_PATH, JS_PATH, PY_DFS_PATH, JS_DFS_PATH

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
    reason="Requires approved isolated Linux Docker worker images")]

PY_DFS = """def solve(g, s):
    stack = [s]
    seen = set()
    result = []
    while stack:
        node = stack.pop()
        if node in seen: continue
        seen.add(node)
        result.append(node)
        stack.extend(g.get(node, []))
    return result
"""
JS_DFS = """function solve(g, s) {
 const stack=[s], seen=new Set(), result=[];
 while(stack.length){const u=stack.pop();if(seen.has(u))continue;seen.add(u);result.push(u);stack.push(...(g[u]||[]));}
 return result;
}"""


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
@pytest.mark.parametrize("task", ["reachability", "shortest_path"])
async def test_automatic_bfs_to_dfs_uses_approved_behavior_not_algorithm_name(workflow, language, task):
    extension = {"python": "py", "javascript": "js", "typescript": "ts"}[language]
    path = "module." + extension
    before, after = ((PY_BFS, PY_DFS) if language == "python" else (JS_BFS, JS_DFS)) if task == "reachability" else ((PY_PATH, PY_DFS_PATH) if language == "python" else (JS_PATH, JS_DFS_PATH))
    if language == "typescript":
        before = before.replace("function solve(g, s)", "function solve(g: Record<string,string[]>, s: string): string[]").replace("function solve(g, start, target)", "function solve(g: Record<string,string[]>, start: string, target: string): string[]")
        after = after.replace("function solve(g, s)", "function solve(g: Record<string,string[]>, s: string): string[]").replace("function solve(g, start, target)", "function solve(g: Record<string,string[]>, start: string, target: string): string[]")
    workflow.snapshots.update(base={path: before}, head={path: after})
    expected = REACHABLE if task == "reachability" else ["s", "b", "t"]
    ids = [task]
    await approved(workflow.service.contracts, {"project_id": "P1", "contract": {"kind": "function", "name": task, "version": "1",
        "input_schema": {"type": "array"}, "output_schema": {"type": "array"}, "correctness": "expected", "mutation": "forbidden",
        "comparison": {"mode": "unordered_set" if task == "reachability" else "exact", "version": "1"}},
        "datasets": [{"id": task, "args": [GRAPH, "s"] if task == "reachability" else [GRAPH, "s", "t"], "expected": expected}],
        "required_dataset_ids": ids, "requirements": [{"id": "behavior", "description": "Required " + task, "source_reference": "spec:reviewed-graph", "dataset_ids": ids}],
        "scope_description": "Finite approved graph fixture", "automatic_scope": {"repository": "o/r", "path": path, "qualified_name": "solve"}})
    workflow.benchmarks.runner = DockerBenchmarkRunner()
    result = await run(workflow, [{"filename": path, "status": "modified"}])
    row = next(r for r in result["functions"] if r["current"]["qualified_name"] == "solve")
    child = await workflow.benchmarks.get(row["benchmark_run_id"])
    assert result["status"] == "completed", result.get("error")
    assert child["status"] == "completed", child.get("error")
    assert child["environment"]["isolation"] == "docker" and child["environment"]["network"] == "none"
    if task == "reachability":
        assert row["compatibility"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"
        assert row["finding_status"] == "CONDITIONAL_FINDING"
    else:
        assert row["finding_status"] == "CORRECTNESS_FAILURE" and row["compatibility"] == "INCOMPATIBLE"
        assert not child["phase1_eligibility"]["eligible"]
        assert not any(c["winner"] for c in child["decision"]["dataset_comparisons"])


async def test_optional_memory_instrumentation_failure_preserves_real_pr_timing(workflow):
    # Fault injection stays inside each existing isolated worker, never the host.
    unavailable_reader = "import memray\ndef unavailable_reader(*args, **kwargs):\n    raise RuntimeError('memory instrumentation unavailable')\nmemray.FileReader = unavailable_reader\n"
    workflow.snapshots["base"]["module.py"] = unavailable_reader + workflow.snapshots["base"]["module.py"]
    workflow.snapshots["head"]["module.py"] = unavailable_reader + workflow.snapshots["head"]["module.py"]
    await contract(workflow)
    workflow.benchmarks.runner = DockerBenchmarkRunner()
    result = await run(workflow)
    child = await workflow.benchmarks.get(result["functions"][0]["benchmark_run_id"])
    assert result["status"] == "completed", result.get("error")
    assert child["behavioral_compatibility"]["status"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"
    assert all(c["task_eligibility"] == "ELIGIBLE" for c in child["decision"]["candidates"])
    for candidate in child["results"]:
        for case in candidate["cases"]:
            assert case["timing_status"] == "AVAILABLE" and len(case["timings_seconds"]) == 5
            assert case["memory_status"] == "UNAVAILABLE" and case["memory_bytes"] is None
            assert case["behavioral_validation"]["status"] == "PASS"


@pytest.mark.parametrize("stop", ["timeout", "cancel"])
async def test_real_pr_worker_stop_removes_container_and_releases_lease(workflow, stop):
    workflow.snapshots["base"]["module.py"] = "def solve(xs):\n    while True: pass\n"
    workflow.snapshots["head"]["module.py"] = "def solve(xs):\n    while True: continue\n"
    await contract(workflow)
    runner = DockerBenchmarkRunner(timeout_seconds=3 if stop == "timeout" else 45)
    workflow.benchmarks.runner = runner
    original = runner._command
    names = []
    async def record_command(*args, **kwargs):
        if args[0] == "run":
            names.append(args[args.index("--name") + 1])
        return await original(*args, **kwargs)
    runner._command = record_command
    created = await workflow.service.enqueue("P1", "o/r", workflow.pr, [{"filename": "module.py"}], "PR1", launch=False)
    task = asyncio.create_task(workflow.service.execute(created["run_id"]))
    try:
        if stop == "cancel":
            for _ in range(100):
                if names:
                    code, output, _ = await original("inspect", "--format", "{{.State.Running}}", names[0])
                    if code == 0 and output.strip() == b"true":
                        break
                await asyncio.sleep(0.1)
            else:
                pytest.fail("The isolated worker never entered its running state")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await asyncio.wait_for(task, 15)
        assert names, "The check must exercise a real worker, not just fail during image inspection"
        for name in names:
            code, _, _ = await original("inspect", name)
            assert code != 0, "Owned worker container survived termination"
        child = await workflow.db.algorithm_benchmark_runs.find_one({})
        assert child["status"] == "failed" and child["active"] is False
        assert (await workflow.service.get(created["run_id"]))["status"] == "failed"
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        for name in names:
            await original("rm", "--force", name)
