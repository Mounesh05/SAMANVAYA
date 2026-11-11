"""Purpose hypotheses must remain traceable, conservative and model-independent."""

import asyncio
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from intelligence.algorithms.discovery.service import discover_sources, discover_repository
from intelligence.algorithms.discovery.rules import PATTERN_RULES, PatternRule, register_rule
from intelligence.evidence.function_purpose import METHOD

PY_BFS = """
def explore(graph, start):
    queue = [start]
    visited = {start}
    while queue:
        node = queue.pop(0)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited
"""
JS_BFS = """
function explore(graph, start) {
    const queue = [start];
    const visited = new Set([start]);
    while (queue.length) {
        const node = queue.shift();
        for (const neighbor of graph[node]) {
            if (!visited.has(neighbor)) {
                visited.add(neighbor);
                queue.push(neighbor);
            }
        }
    }
    return visited;
}
"""


def run(sources, revision="head-sha"):
    return asyncio.run(discover_sources({p: textwrap.dedent(s).lstrip() for p, s in sources.items()}, "project", revision))


def first(source, extension="py"):
    report = run({"src/module." + extension: source})
    assert report.status == "available", report.diagnostics
    return report.functions[0]


@pytest.mark.parametrize("extension,source", [
    ("py", PY_BFS), ("js", JS_BFS),
    ("ts", JS_BFS.replace("graph, start", "graph: Record<string, string[]>, start: string")),
])
def test_bfs_structure_suggests_reachability_never_shortest_paths(extension, source):
    function = first(source, extension)
    patterns = {p.kind for p in function.detected_patterns}
    assert {"fifo_graph_traversal", "visited_set_tracking"} <= patterns
    assert function.possible_task == "graph_reachability"
    assert function.task_status == "INFERRED"
    assert function.verified_contract is None
    assert "shortest" not in function.model_dump_json().lower()
    assert function.source_revision == "head-sha"
    assert len(function.source_hash) == 64
    refs = {e.id for e in function.evidence}
    assert all(e.status == "OBSERVED" for e in function.evidence)
    for conclusion in [*function.detected_patterns, *function.task_hypotheses]:
        assert conclusion.status == "INFERRED"
        assert conclusion.evidence_refs and set(conclusion.evidence_refs) <= refs
        assert conclusion.method == METHOD and conclusion.source_revision == "head-sha"
        assert conclusion.missing_information
    assert "confidence" not in function.model_dump_json()


@pytest.mark.parametrize("extension,source", [("py", PY_BFS.replace("pop(0)", "pop()")),
                                            ("js", JS_BFS.replace("shift()", "pop()")),
                                            ("ts", JS_BFS.replace("shift()", "pop()"))])
def test_iterative_dfs(extension, source):
    function = first(source, extension)
    assert "lifo_graph_exploration" in {p.kind for p in function.detected_patterns}
    assert "fifo_graph_traversal" not in {p.kind for p in function.detected_patterns}
    assert function.possible_task == "graph_reachability"


@pytest.mark.parametrize("extension,source", [("py", PY_BFS), ("js", JS_BFS), ("ts", JS_BFS)])
def test_renaming_and_misleading_comments_do_not_change_purpose(extension, source):
    renamed = source.replace("explore", "guaranteed_shortest_path_sorting")
    renamed = ("# " if extension == "py" else "// ") + "This proves the fastest Dijkstra algorithm\n" + renamed
    before, after = first(source, extension), first(renamed, extension)
    assert before.possible_task == after.possible_task
    assert [p.kind for p in before.detected_patterns] == [p.kind for p in after.detected_patterns]
    assert after.verified_contract is None


@pytest.mark.parametrize("extension,source", [
    ("py", "def shortest_path_bfs(x):\n    # breadth first graph algorithm\n    return (x ^ 7) * 11"),
    ("js", "const bfs = (x) => (x ^ 7) * 11;"),
    ("ts", "const bfs = (x: number): number => (x ^ 7) * 11;"),
])
def test_custom_and_unfamiliar_functions_still_have_metadata(extension, source):
    function = first(source, extension)
    assert function.task_status == "UNKNOWN"
    assert function.possible_task is None and not function.task_hypotheses
    assert function.parameters[0]["name"] == "x"
    assert function.returns and function.evidence
    assert function.uncertainty and function.function_id


@pytest.mark.parametrize("extension,source", [
    ("py", "def unknown(values):\n    return sum(sorted(values))"),
    ("js", "function unknown(values) { return values.filter(x => x > 0).sort(); }"),
    ("ts", "function unknown(values: number[]) { return values.filter(x => x > 0).sort(); }"),
])
def test_multiple_patterns_do_not_force_a_single_task(extension, source):
    function = first(source, extension)
    assert function.task_status == "AMBIGUOUS"
    assert function.possible_task is None
    assert len(function.task_hypotheses) >= 2


@pytest.mark.parametrize("extension,source", [
    ("py", "def recursive(graph, node, seen):\n    seen.add(node)\n    for neighbor in graph[node]:\n        if neighbor not in seen:\n            recursive(graph, neighbor, seen)\n    return seen"),
    ("js", "function recursive(graph, node, seen) { seen.add(node); for (const n of graph[node]) { if (!seen.has(n)) recursive(graph,n,seen); } return seen; }"),
    ("ts", "function recursive(graph: any, node: string, seen: Set<string>) { seen.add(node); for (const n of graph[node]) { if (!seen.has(n)) recursive(graph,n,seen); } return seen; }"),
])
def test_recursive_exploration(extension, source):
    function = first(source, extension)
    assert {"recursion", "recursive_graph_exploration"} <= {p.kind for p in function.detected_patterns}
    assert function.possible_task == "graph_reachability"


@pytest.mark.parametrize("extension,source", [("py", "def incomplete(:"), ("js", "function incomplete( {"), ("ts", "const x: = (")])
def test_incomplete_source_is_explicitly_unavailable(extension, source):
    report = run({"bad." + extension: source})
    assert report.status == "unavailable" and report.diagnostics
    assert report.functions == []


def test_one_invalid_file_does_not_erase_valid_functions():
    report = run({"bad.py": "def (", "good.py": "def custom(x): return x"})
    assert report.status == "partial"
    assert [f.name for f in report.functions] == ["custom"]


def test_decorators_defaults_imports_and_top_level_code_are_not_executed(tmp_path):
    sentinel = tmp_path / "executed.txt"
    function = first(f"""
        from pathlib import Path
        Path({str(sentinel)!r}).touch()
        @dangerous_decorator()
        def custom(x=side_effect()):
            return x
    """)
    assert function.parameters[0]["has_default"]
    assert not sentinel.exists()
    js = f"require('fs').writeFileSync({str(sentinel)!r}, 'executed'); function custom(x) {{ return x; }}"
    assert first(js, "js").name == "custom"
    assert not sentinel.exists()


def test_context_links_callers_and_static_test_expectations_without_verification():
    report = run({"module.py": "def custom(x: int) -> int: return x * 2",
                  "tests/test_module.py": "from module import custom as apply\ndef test_case():\n    assert apply(3) == 6"})
    function = next(f for f in report.functions if f.name == "custom")
    assert function.callers[0]["path"] == "tests/test_module.py"
    assert function.parameters[0]["annotation"] == "int"
    assert function.return_annotation == "int"
    assert function.requirement_evidence_refs
    assert any(e.kind == "test_expectation" for e in function.evidence)
    assert function.verified_contract is None and function.task_status == "UNKNOWN"


def test_javascript_import_context_links_test_expectations():
    report = run({"module.ts": "export function custom(x: number) { return x * 2; }",
                  "tests/check.ts": "import {custom as apply} from '../module'; function check() { expect(apply(3)).toBe(6); }"})
    function = next(f for f in report.functions if f.name == "custom")
    assert function.callers and function.requirement_evidence_refs
    assert function.verified_contract is None


def test_nested_function_patterns_do_not_leak_to_parent():
    function = first("def outer(x):\n    def inner():\n        return sorted(x)\n    return x")
    assert function.name == "outer" and function.task_status == "UNKNOWN"


def test_graph_traversal_requires_related_bindings_and_known_sequence():
    source = PY_BFS.replace("graph[node]", "graph[start]")
    assert "fifo_graph_traversal" not in {p.kind for p in first(source).detected_patterns}
    assert first(source).possible_task is None


def test_returned_collection_must_track_the_explored_elements():
    function = first(PY_BFS.replace("visited.add(neighbor)", "visited.add(start)"))
    assert function.possible_task == "graph_traversal"


def test_known_shadowed_builtins_are_not_sorting_or_aggregation_evidence():
    report = run({"m.py": "def sorted(x): return x\ndef custom(x): return sorted(x)"})
    assert all(f.task_status == "UNKNOWN" for f in report.functions)
    assert first("def custom(xs, sorted): return sorted(xs)").task_status == "UNKNOWN"


def test_priority_operations_and_memoization_are_patterns_not_requirements():
    heap = first("import heapq as h\ndef custom(xs):\n    h.heapify(xs)\n    return h.heappop(xs)")
    assert "priority_queue_operations" in {p.kind for p in heap.detected_patterns}
    assert heap.task_status == "UNKNOWN"
    memo = first("def custom(n, table):\n    if n in table:\n        return table[n]\n    table[n] = custom(n-1, table)\n    return table[n]")
    assert "memoized_recursion" in {p.kind for p in memo.detected_patterns}
    assert memo.verified_contract is None


def test_extensible_rule_registry_does_not_gate_function_extraction():
    rule = PatternRule("custom_return_observation", lambda f: [e for e in f.evidence if e.kind == "return_value"], "Return syntax exists.")
    register_rule(rule)
    try:
        function = first("def novel(x): return x")
        assert "custom_return_observation" in {p.kind for p in function.detected_patterns}
        assert function.task_status == "UNKNOWN"
    finally:
        PATTERN_RULES.pop(rule.name)


def test_content_identity_is_stable_and_revision_absence_explicit():
    a = first("def f(x): return x")
    b = first("def f(x): return x")
    assert a.function_id == b.function_id
    assert a.function_id != first("def f(x): return x + 1").function_id
    function = run({"x.py": "def f(): return 1"}, revision=None).functions[0]
    assert any("revision" in item.lower() for item in function.uncertainty)


def test_parser_unavailability_keeps_python_discovery(monkeypatch):
    from intelligence.algorithms.discovery import extractors
    monkeypatch.setattr(extractors.shutil, "which", lambda _: None)
    report = run({"ok.py": "def f(x): return x", "other.ts": "function other() {}"})
    assert report.status == "partial"
    assert [f.language for f in report.functions] == ["python"]
    assert report.diagnostics


def test_repository_discovery_includes_context_and_excludes_dependencies(tmp_path):
    (tmp_path / "module.py").write_text("def f(x): return x", encoding="utf-8")
    (tmp_path / "caller.py").write_text("from module import f\ndef g(x): return f(x)", encoding="utf-8")
    dependency = tmp_path / "node_modules"
    dependency.mkdir()
    (dependency / "ignored.js").write_text("function ignored() {}", encoding="utf-8")
    report = asyncio.run(discover_repository(tmp_path, "project", "sha", ["module.py"]))
    assert {f.path for f in report.functions} == {"module.py", "caller.py"}
    assert next(f for f in report.functions if f.name == "f").callers


def test_invalid_paths_and_function_limits_are_reported():
    report = run({"../outside.py": "def f(): pass", "many.py": "\n".join(f"def f{i}(): return {i}" for i in range(150))})
    assert report.status == "partial" and len(report.functions) == 128
    assert any(d["kind"] == "function_bound" for d in report.diagnostics)


def test_purpose_discovery_is_independent_of_ollama_and_benchmarking(monkeypatch):
    from domain.services.code_quality_service import CodeQualityService
    from intelligence.evidence.models import CodeQualityEvidence
    from intelligence.algorithms.runner import DockerBenchmarkRunner
    monkeypatch.setattr(DockerBenchmarkRunner, "run", AsyncMock(side_effect=AssertionError("No benchmarks")))
    service = CodeQualityService()
    monkeypatch.setattr(service, "_analyze_quality_pr", AsyncMock(return_value=CodeQualityEvidence(repository_id="project", primary_language="python")))
    report = asyncio.run(service.analyze_pr(["m.py"], {"project_id": "project", "source_files": {"m.py": PY_BFS}}))
    assert report.function_discovery.functions[0].possible_task == "graph_reachability"
    DockerBenchmarkRunner.run.assert_not_awaited()
