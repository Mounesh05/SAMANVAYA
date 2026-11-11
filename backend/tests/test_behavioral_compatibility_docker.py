"""Real behavioral evidence is produced only in the existing isolated workers."""

import os

import pytest

from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from domain.services.behavioral_compatibility_service import BehavioralCompatibilityService
from domain.services.function_contract_service import FunctionContractService
from intelligence.algorithms.runner import DockerBenchmarkRunner

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
    reason="Requires rebuilt pinned Docker workers; developer source never runs on host")]

GRAPH = {"s": ["a", "b"], "a": ["c"], "c": ["d"], "d": ["t"], "b": ["t"], "t": []}
REACHABLE = ["s", "a", "b", "c", "t", "d"]
PY_BFS = """def solve(g, s):
    q = [s]
    seen = {s}
    result = []
    while q:
        u = q.pop(0)
        result.append(u)
        for v in g.get(u, []):
            if v not in seen:
                seen.add(v)
                q.append(v)
    return result
"""
JS_BFS = """function solve(g, s) {
 const q = [s], seen = new Set([s]), result = [];
 while(q.length) { const u = q.shift(); result.push(u);
  for(const v of g[u] || []) if(!seen.has(v)) {seen.add(v); q.push(v);}
 } return result;
} """
PY_PATH = """def solve(g, start, target):
    q = [[start]]
    seen = {start}
    while q:
        path = q.pop(0)
        u = path[-1]
        if u == target: return path
        for v in g.get(u, []):
            if v not in seen:
                seen.add(v)
                q.append(path + [v])
    return []
"""
PY_DFS_PATH = """def solve(g, start, target):
    def explore(u, path):
        if u == target: return path
        for v in g.get(u, []):
            if v not in path:
                result = explore(v, path + [v])
                if result: return result
        return []
    return explore(start, [start])
"""
JS_PATH = """function solve(g, start, target) {
 const q=[[start]],seen=new Set([start]);
 while(q.length){const path=q.shift(),u=path[path.length-1];if(u===target)return path;
 for(const v of g[u]||[])if(!seen.has(v)){seen.add(v);q.push([...path,v]);}}
 return [];
}"""
JS_DFS_PATH = """function solve(g, start, target) {
 function explore(u,path){if(u===target)return path;
 for(const v of g[u]||[])if(!path.includes(v)){const result=explore(v,[...path,v]);if(result.length)return result;}return [];}
 return explore(start,[start]);
}"""


def candidate(language, source, name):
    if language == "typescript":
        source = source.replace("function solve(g, s)", "function solve(g: Record<string,string[]>, s: string): string[]")
        source = source.replace("function solve(g, start, target)", "function solve(g: Record<string,string[]>, start: string, target: string): string[]")
    return {"language": language, "name": name, "source": source, "entrypoint": "solve"}


async def compare(mock_db, languages, sources, datasets, mode="exact", selected=None):
    contracts = FunctionContractService(mock_db.algorithm_function_contracts, mock_db.code_quality_runs)
    required = [d["id"] for d in datasets]
    document = await contracts.propose({"project_id": "P", "contract": {"kind": "function", "name": "approved-scope", "version": "1",
        "input_schema": {"type": "array"}, "output_schema": {"type": "array"}, "mutation": "forbidden",
        "correctness": "expected", "comparison": {"mode": mode, "version": "1"}},
        "datasets": datasets, "required_dataset_ids": required,
        "requirements": [{"id": "behavior", "description": "Required behavior on reviewed examples", "source_reference": "spec:graph-examples", "dataset_ids": required}],
        "scope_description": "Reviewed graph fixtures; no untested-input guarantee"}, {"employee_id": "author", "org_id": "org"})
    document = await contracts.approve(document, {"expected_fingerprint": document["payload_fingerprint"], "source_reference": "review:graph",
        "rationale": "Reviewed scope and expected results", "scope_reviewed": True}, {"employee_id": "reviewer", "role": "LEAD", "org_id": "org"})
    benchmarks = AlgorithmBenchmarkService(mock_db.algorithm_benchmark_runs, DockerBenchmarkRunner())
    service = BehavioralCompatibilityService(benchmarks, contracts, mock_db.code_quality_runs)
    request = {"project_id": "P", "contract_ids": [document["contract_id"]],
        "previous": candidate(languages[0], sources[0], "earlier"), "current": candidate(languages[1], sources[1], "later"), "repetitions": 3}
    if selected is not None:
        request["dataset_ids"] = selected
    created = await service.create(request, {"employee_id": "author", "org_id": "org"})
    await benchmarks.execute(created["run_id"])
    result = await benchmarks.get(created["run_id"])
    assert result["status"] == "completed", result.get("error")
    assert result["behavioral_compatibility"]["evidence_refs"]
    return result


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
@pytest.mark.parametrize("contract_kind", ["reachability", "shortest_path", "traversal_order"])
async def test_bfs_and_dfs_depend_on_approved_behavior_not_names(mock_db, language, contract_kind):
    if contract_kind == "shortest_path":
        sources = (PY_PATH, PY_DFS_PATH) if language == "python" else (JS_PATH, JS_DFS_PATH)
        datasets = [{"id": "long-branch-counterexample", "args": [GRAPH, "s", "t"], "expected": ["s", "b", "t"]}]
    else:
        sources = (PY_BFS, PY_BFS.replace("pop(0)", "pop()")) if language == "python" else (JS_BFS, JS_BFS.replace("shift()", "pop()"))
        datasets = [{"id": "branching-graph", "args": [GRAPH, "s"], "expected": REACHABLE}]
    result = await compare(mock_db, (language, language), sources, datasets, "unordered_set" if contract_kind == "reachability" else "exact")
    expected = "COMPATIBLE_WITHIN_TESTED_CONTRACT" if contract_kind == "reachability" else "INCOMPATIBLE"
    assert result["behavioral_compatibility"]["status"] == expected
    if expected == "INCOMPATIBLE":
        assert not result["phase1_eligibility"]["eligible"]
        assert result["recommendation"]["winner"] is None
        assert all(d["winner"] is None for d in result["decision"]["dataset_comparisons"])


@pytest.mark.parametrize("current", ["javascript", "typescript"])
async def test_python_and_node_implementations_use_identical_contract_inputs(mock_db, current):
    result = await compare(mock_db, ("python", current), (PY_BFS, JS_BFS),
        [{"id": "reachable", "args": [GRAPH, "s"], "expected": REACHABLE}], "unordered_set")
    assert result["behavioral_compatibility"]["status"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"
    fingerprints = {check["input_fingerprint"] for check in result["behavioral_compatibility"]["checks"]}
    assert len(fingerprints) == 1


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
async def test_multiple_approved_shortest_path_outputs_are_supported_without_inventing_an_oracle(mock_db, language):
    graph = {"s": ["a", "b"], "a": ["t"], "b": ["t"], "t": []}
    alternate = PY_DFS_PATH.replace("g.get(u, [])", "reversed(g.get(u, []))") if language == "python" else JS_DFS_PATH.replace("for(const v of g[u]||[])", "for(const v of [...(g[u]||[])].reverse())")
    sources = (PY_PATH, alternate) if language == "python" else (JS_PATH, alternate)
    result = await compare(mock_db, (language, language), sources, [{
        "id": "diamond", "args": [graph, "s", "t"], "expected": ["s", "a", "t"],
        "acceptable_outputs": [["s", "a", "t"], ["s", "b", "t"]]}], "one_of")
    assert result["behavioral_compatibility"]["status"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"


async def test_matching_signatures_do_not_mask_wrong_behavior(mock_db):
    result = await compare(mock_db, ("python", "python"), ("def solve(xs): return xs", "def solve(xs): return []"),
        [{"id": "required-values", "args": [[1, 2]], "expected": [1, 2]}])
    assert result["behavioral_compatibility"]["status"] == "INCOMPATIBLE"


async def test_partial_test_execution_remains_unverified_despite_passing_cases(mock_db):
    result = await compare(mock_db, ("python", "python"), (PY_BFS, PY_BFS.replace("pop(0)", "pop()")),
        [{"id": "trivial", "args": [{"s": []}, "s"], "expected": ["s"]},
         {"id": "branching", "args": [GRAPH, "s"], "expected": REACHABLE}], "exact", selected=["trivial"])
    assert result["behavioral_compatibility"]["status"] == "UNVERIFIED"
    assert not result["decision"]["task_suitability"]["eligible_candidates"]


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
async def test_native_sets_are_normalized_only_by_explicit_unordered_set_contract(mock_db, language):
    source = PY_BFS if language == "python" else JS_BFS
    changed = source.replace("return result", "return seen")
    result = await compare(mock_db, (language, language), (source, changed),
        [{"id": "native-set", "args": [GRAPH, "s"], "expected": REACHABLE}], "unordered_set")
    assert result["behavioral_compatibility"]["status"] == "COMPATIBLE_WITHIN_TESTED_CONTRACT"


async def test_candidate_controlled_validator_function_does_not_override_worker_checks(mock_db):
    misleading = "def validate(*args): return True\ndef solve(xs): return []"
    result = await compare(mock_db, ("python", "python"), ("def solve(xs): return xs", misleading),
        [{"id": "real-oracle", "args": [[1, 2]], "expected": [1, 2]}])
    assert result["behavioral_compatibility"]["status"] == "INCOMPATIBLE"
