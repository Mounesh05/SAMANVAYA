"""Static complexity estimation and function classification.

Syntax only: no source is executed, no measurement is taken and every bound
carries its assumptions and unknown reasons. Fixtures are trusted local strings.
"""

import ast
import asyncio
import textwrap

import pytest

from intelligence.algorithms.discovery import complexity
from intelligence.algorithms.discovery.classification import (
    APPLICATION, HELPER, NESTED, TEST, TEST_HELPER, classify,
)
from intelligence.algorithms.discovery.service import discover_sources


def estimate(source, name, facts=(), annotations=None):
    tree = ast.parse(textwrap.dedent(source))
    node = next(node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    return complexity.estimate(node, name, facts=facts, parameter_annotations=annotations or {})


def estimate_discovered(source, name):
    """Run the real discovery pipeline so the structural facts are genuine."""
    text = textwrap.dedent(source)
    report = asyncio.run(discover_sources({"module.py": text}, "fixture-repository", "fixture-revision"))
    function = next(item for item in report.functions if item.name == name)
    assert function.evidence, "structural facts must be produced by discovery"
    node = next(node for node in ast.parse(text).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    return complexity.estimate(node, name, facts=list(function.evidence),
                               parameter_annotations={a.arg: (ast.unparse(a.annotation) if a.annotation else "")
                                                      for a in node.args.args})


# --------------------------------------------------------------------------- #
# Time and space bounds
# --------------------------------------------------------------------------- #

def test_heap_scheduling_bounds_match_the_observed_operations():
    record = estimate(
        """
        import heapq
        def schedule(tasks):
            heap = [(t.priority, t) for t in tasks]
            heapq.heapify(heap)
            ordered = []
            while heap:
                ordered.append(heapq.heappop(heap))
            return ordered
        """,
        "schedule",
    )
    assert record["status"] == "estimated"
    assert record["time_complexity"] == "O(m log m)"
    assert record["space_complexity"] is not None
    assert record["assumptions"] or record["derivation"]


def test_repeated_sorting_bounds_include_the_repeated_sort():
    record = estimate(
        """
        def schedule(tasks):
            remaining = list(tasks)
            ordered = []
            while remaining:
                remaining.sort(key=lambda t: t.due)
                ordered.append(remaining.pop(0))
            return ordered
        """,
        "schedule",
    )
    assert record["time_complexity"] == "O(m m log m)"
    assert record["status"] == "estimated"


def test_breadth_first_traversal_is_bounded_by_vertices_and_edges():
    record = estimate_discovered(
        """
        from collections import deque
        def explore(graph, start):
            queue = deque([start])
            seen = {start}
            while queue:
                node = queue.popleft()
                for neighbor in graph.get(node, []):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append(neighbor)
            return seen
        """,
        "explore",
    )
    assert record["time_complexity"] == "O(V + E)"
    assert record["space_complexity"] == "O(V)"
    assert any("membership guard" in step for step in record["derivation"])
    assert record["confidence"] in {"low", "medium", "high"}


def test_unresolvable_worklist_reports_unknown_instead_of_a_bound():
    record = estimate(
        """
        def explore(graph, start):
            state = {}
            frontier = [start]
            while frontier:
                node = frontier.pop()
                state[node] = 1
                frontier.extend(graph[node])
            return state
        """,
        "explore",
    )
    assert record["time_complexity"] is None
    assert record["unknown_reasons"]
    assert record["status"] in {"partial", "unknown"}


def test_a_bound_never_claims_a_language_that_is_not_analysed():
    record = complexity.estimate(None, "run", facts=[], language="typescript")
    assert record["time_complexity"] is None and record["space_complexity"] is None
    assert record["status"] == "unknown" and record["unknown_reasons"]
    assert all("no bound is claimed" in reason for reason in record["unknown_reasons"])


def test_every_estimate_declares_its_dimensions_and_limitations():
    record = estimate("def count(xs):\n    total = 0\n    for x in xs:\n        total += x\n    return total\n", "count")
    assert record["dimensions"], "symbolic dimensions must be declared"
    assert record["dimension_bindings"], "each letter must be bound to a source symbol"
    assert record["limitations"] and all(isinstance(item, str) for item in record["limitations"])
    assert record["method"] == "static-ast-complexity-v1"


def test_membership_and_sorting_costs_use_documented_typical_bounds():
    record = estimate(
        """
        def ordered_unique(values):
            seen = set()
            kept = [v for v in values if v not in seen and not seen.add(v)]
            return sorted(kept)
        """,
        "ordered_unique",
    )
    assert record["time_complexity"] is not None
    assert any("membership" in assumption for assumption in record["assumptions"])


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path,qualified,name,expected", [
    ("backend/app/advanced_algorithms.py", "schedule", "schedule", APPLICATION),
    ("backend/tests/test_advanced_algorithms.py", "test_schedule", "test_schedule", TEST),
    ("backend/tests/test_advanced_algorithms.py", "sample_tasks", "sample_tasks", TEST_HELPER),
    ("backend/app/advanced_algorithms.py", "test_coverage", "test_coverage", TEST),
    ("src/lib/parser.ts", "parse", "parse", APPLICATION),
    ("src/lib/parser.test.ts", "parses input", "parses input", TEST_HELPER),
    ("src/lib/parser.test.ts", "it_parses_input", "it_parses_input", TEST),
    ("app/advanced_algorithms.py", "schedule.<lambda>@12:9", "<lambda>", NESTED),
    ("app/models.py", "Container.render", "render", NESTED),
])
def test_classification_follows_path_and_identifier_shape_only(path, qualified, name, expected):
    assert classify(path, qualified, name)["category"] == expected


def test_lambda_classification_attributes_the_enclosing_definition():
    record = classify("app/algorithms.py", "schedule_with_heap.<lambda>@40:16", "<lambda>")
    assert record["category"] == NESTED
    assert record["attribution"] == "schedule_with_heap"


def test_a_constant_plain_function_is_a_helper_rather_than_an_algorithm():
    record = classify("app/algorithms.py", "sample", "sample",
                      patterns=[], complexity={"status": "estimated", "time_complexity": "O(1)"})
    assert record["category"] == HELPER
    assert any("constant" in reason for reason in record["reasons"])


def test_observed_structure_is_never_called_a_helper():
    record = classify("app/algorithms.py", "explore", "explore",
                      patterns=["fifo_graph_traversal"],
                      complexity={"status": "estimated", "time_complexity": "O(V + E)"})
    assert record["category"] == APPLICATION


def test_classification_always_declares_its_limitations():
    record = classify("app/algorithms.py", "solve", "solve")
    assert record["limitations"] and record["method"] == "static-function-classification-v1"
    assert record["attribution"] is None and record["is_test"] is False


def test_no_repository_function_or_framework_name_is_matched():
    # Only structure may drive the decision: a plausible application function in a
    # non-test path with a non-test name must never be labelled a test.
    for name in ("latest_report", "contest_entry", "attestation", "special_case"):
        assert classify("app/reporting.py", name, name)["category"] == APPLICATION
