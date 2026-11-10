"""Source-only structure reports: no candidate execution or algorithm-name heuristics."""

import ast
import json
import textwrap

import pytest

from intelligence.algorithms import structure
from intelligence.algorithms.structure import analyze_python


def analyze(source, entrypoint="novel_transform"):
    return analyze_python(textwrap.dedent(source).lstrip("\n"), entrypoint)


def rows(report):
    assert report["status"] == "available", report.get("diagnostics")
    return {row["name"]: row for row in report["functions"]}


def test_novel_name_all_functions_and_source_ranges():
    report = analyze("""
        def novel_transform(values):
            for value in values:
                while value:
                    value -= 1
            return values

        async def unrelated(values):
            async for value in values:
                await consume(value)
    """)
    assert set(report) == {"status", "parser", "entrypoint", "functions", "limitations"}
    assert report["parser"] == "python.ast"
    assert report["entrypoint"] == "novel_transform"
    functions = rows(report)
    assert set(functions) == {"novel_transform", "unrelated"}
    first = functions["novel_transform"]
    assert (first["line"], first["end_line"]) == (1, 5)
    assert (first["loops"], first["max_loop_nesting"]) == (2, 2)
    assert functions["unrelated"]["loops"] == 1
    assert functions["unrelated"]["calls"] == ["consume"]
    json.dumps(report, allow_nan=False)


def test_entrypoint_is_not_an_algorithm_filter_or_runtime_lookup():
    functions = rows(analyze("def completely_unknown():\n    return 1", "missing"))
    assert set(functions) == {"completely_unknown"}
    assert analyze("x = 1", "missing")["functions"] == []


def test_comprehensions_include_all_clauses_and_surrounding_loops():
    function = rows(analyze("""
        def novel_transform(groups):
            for group in groups:
                result = [(a, b) for a in group if a for b in a if b]
            return result
    """))["novel_transform"]
    assert function["loops"] == 3
    assert function["max_loop_nesting"] == 3
    assert function["branches"]["comprehension_filters"] == 2
    assert function["allocations"] == [
        {"kind": "list_comprehension", "line": 3},
        {"kind": "tuple_literal", "line": 3},
    ]


@pytest.mark.parametrize("expression, loops, nesting", [
    ("[x for x in [y for y in xs]]", 2, 1),
    ("[[y for y in x] for x in xs]", 2, 2),
    ("[y for x in xs for y in [z for z in x]]", 3, 2),
    ("[x for x in xs if any(y for y in x)]", 2, 2),
    ("{x: [y for y in x] for x in xs}", 2, 2),
    ("(y for x in xs for y in x)", 2, 2),
])
def test_comprehension_evaluation_context(expression, loops, nesting):
    function = rows(analyze(f"def novel_transform(xs):\n    return {expression}"))["novel_transform"]
    assert (function["loops"], function["max_loop_nesting"]) == (loops, nesting)


def test_async_comprehension():
    function = rows(analyze("""
        async def novel_transform(xs):
            return {x async for x in xs if x}
    """))["novel_transform"]
    assert function["loops"] == function["max_loop_nesting"] == 1
    assert function["allocations"] == [{"kind": "set_comprehension", "line": 2}]


def test_nested_functions_lambdas_and_methods_are_separate():
    functions = rows(analyze("""
        def novel_transform(xs):
            def inner(x):
                for y in x:
                    inner(y)
            callback = lambda x: [f(y) for y in x]
            return inner(xs), callback(xs)
        class Example:
            async def method(self):
                return await service.run()
        named = lambda n: named(n - 1) if n else []
        annotated: object = lambda x: x
        sink(lambda z: other(z))
    """))
    outer = functions["novel_transform"]
    assert outer["loops"] == outer["max_loop_nesting"] == 0
    assert outer["allocations"] == [{"kind": "tuple_literal", "line": 6}]
    assert outer["calls"] == ["inner", "callback"]
    assert functions["novel_transform.inner"]["direct_recursive_calls"] == 1
    assert functions["novel_transform.callback"]["loops"] == 1
    assert functions["Example.method"]["calls"] == ["service.run"]
    assert functions["named"]["direct_recursive_calls"] == 1
    assert "annotated" in functions
    anonymous = next(row for name, row in functions.items() if name.startswith("<lambda>@"))
    assert anonymous["calls"] == ["other"]


def test_nested_defaults_and_decorators_belong_to_enclosing_scope():
    functions = rows(analyze("""
        def novel_transform():
            @decorate(factory())
            def inner(x=make(), y: annotation() = None):
                body_call()
            return inner
    """))
    assert set(functions["novel_transform"]["calls"]) == {"decorate", "factory", "make", "annotation"}
    assert functions["novel_transform.inner"]["calls"] == ["body_call"]


def test_calls_are_lexical_and_recursion_is_only_syntactic():
    function = rows(analyze("""
        def novel_transform(n):
            alias = novel_transform
            alias(n)
            novel_transform(n - 1)
            novel_transform(n - 2)
            self.novel_transform(n)
            package.service.run(n)
            package.service.run(n)
            factory()(n)
            table[n](n)
    """))["novel_transform"]
    assert function["direct_recursive_calls"] == 2
    assert function["calls"] == ["alias", "novel_transform", "self.novel_transform", "package.service.run", "factory"]


def test_descriptive_branch_counts_not_cyclomatic_complexity():
    function = rows(analyze("""
        def novel_transform(x):
            try:
                if x and ready(x) and enabled:
                    return 1 if x else 0
                elif x or fallback:
                    match x:
                        case 1:
                            return 1
                        case _ if check(x):
                            return 2
            except ValueError:
                pass
            except TypeError:
                pass
            finally:
                cleanup()
    """))["novel_transform"]
    assert function["branches"] == {
        "if": 2, "ifexp": 1, "match": 1, "match_cases": 2,
        "boolop": 2, "try": 1, "except_handlers": 2, "comprehension_filters": 0,
    }


def test_allocation_sites_not_constructor_or_peak_memory_guesses():
    function = rows(analyze("""
        def novel_transform(xs):
            a = []
            b = {}
            c = {1}
            d = (1, 2)
            e = [x for x in xs]
            f = {x for x in xs}
            g = {x: x for x in xs}
            h = (x for x in xs)
            i = list(xs)
            j = Custom(xs)
            left, right = xs
            [left, right] = xs
    """))["novel_transform"]
    assert [site["kind"] for site in function["allocations"]] == [
        "list_literal", "dict_literal", "set_literal", "tuple_literal",
        "list_comprehension", "set_comprehension", "dict_comprehension", "generator_expression",
    ]
    assert function["calls"] == ["list", "Custom"]


def test_source_is_never_executed_or_imported(tmp_path):
    marker = tmp_path / "must_not_exist"
    source = f"""
import definitely_nonexistent_submitted_module
from pathlib import Path
Path({str(marker)!r}).write_text('executed')
raise RuntimeError('top-level executed')
@explode()
def novel_transform(x=explode()):
    Path({str(marker)!r}).write_text('called')
    return novel_transform()
"""
    report = analyze_python(source, "novel_transform")
    assert report["status"] == "available"
    assert not marker.exists()
    assert rows(report)["novel_transform"]["direct_recursive_calls"] == 1


@pytest.mark.parametrize("source", ["def broken(:", "x = '\x00'", "(" * 500 + "1" + ")" * 500])
def test_syntax_and_parser_depth_failures_are_unavailable(source):
    report = analyze_python(source, "novel_transform")
    assert report["status"] == "unavailable"
    assert report["functions"] == []
    assert report["diagnostics"][0]["kind"] in {"SyntaxError", "RecursionError"}
    assert report["diagnostics"][0]["message"]
    json.dumps(report)


@pytest.mark.parametrize("error", [RecursionError("too deep"), ValueError("invalid AST"),
                                    MemoryError("parser allocation failed"), OverflowError("too large")])
def test_parser_resource_failures_are_useful_unavailable(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(structure.ast, "parse", fail)
    report = analyze_python("pass", "novel_transform")
    assert report["status"] == "unavailable"
    assert report["diagnostics"][0]["kind"] == type(error).__name__
    assert str(error) in report["diagnostics"][0]["message"]


@pytest.mark.parametrize("source", ["#" + "a" * 200_000, "#" + "é" * 100_000,
                                    "#\ud800", b"pass", None])
def test_source_validation_and_utf8_byte_limit(source):
    report = analyze_python(source, "novel_transform")
    assert report["status"] == "unavailable"
    assert report["diagnostics"][0]["message"]


def test_source_exact_byte_boundary_and_ast_node_limit():
    assert analyze_python("#" + "a" * 199_999, "f")["status"] == "available"
    # Each assignment contributes four nodes; source is below the byte limit.
    report = analyze_python("x=0\n" * 12_500, "f")
    assert report["status"] == "unavailable"
    assert "50000 nodes" in report["diagnostics"][0]["message"]


def test_iterative_walk_handles_deep_ast_without_visitor_recursion(monkeypatch):
    # Construct a deep AST, not code execution, to isolate traversal from parser limits.
    expression = ast.Name(id="x", ctx=ast.Load())
    for _ in range(2500):
        expression = ast.UnaryOp(op=ast.Not(), operand=expression)
    function = ast.FunctionDef(name="deep", args=ast.arguments(posonlyargs=[], args=[],
        kwonlyargs=[], kw_defaults=[], defaults=[]), body=[ast.Return(value=expression)],
        decorator_list=[], lineno=1, end_lineno=2)
    tree = ast.Module(body=[function], type_ignores=[])
    monkeypatch.setattr(structure.ast, "parse", lambda *args, **kwargs: tree)
    result = rows(analyze_python("ignored", "deep"))["deep"]
    assert result["loops"] == 0


def test_function_call_allocation_and_serialized_output_bounds():
    many_functions = "\n".join(f"def f{i}(): pass" for i in range(200))
    report = analyze_python(many_functions, "f0")
    assert len(rows(report)) == 128
    assert any("truncated" in item for item in report["limitations"])

    # Distinct non-ASCII labels exercise JSON's default ASCII escaping too.
    calls = "\n".join("    " + "名" * 110 + str(i) + "()" for i in range(550))
    # Keep source under 200,000 bytes while exhausting both output budgets.
    source = "def f():\n" + calls + "\n" + "    x=[]\n" * 1100
    report = analyze_python(source, "f")
    function = rows(report)["f"]
    assert len(function["calls"]) == 512
    assert len(function["allocations"]) == 1024
    assert any("truncated" in item for item in report["limitations"])
    assert len(json.dumps(report).encode("utf-8")) < 1_000_000


def test_long_labels_and_invalid_entrypoint_remain_bounded():
    name = "名" * 1000
    report = analyze_python(f"def {name}():\n    return {name}()", "f")
    function = report["functions"][0]
    assert len(function["name"]) == 120
    assert len(function["calls"][0]) == 120
    assert function["direct_recursive_calls"] == 1
    for entrypoint in (None, "", "a" * 1_000_001):
        report = analyze_python("pass", entrypoint)
        assert report["status"] == "unavailable"
        assert len(json.dumps(report)) < 10_000


def test_limitations_do_not_guess_big_o_or_claim_safety():
    report = analyze("def novel_transform(xs):\n    return sorted(xs)")
    limitations = " ".join(report["limitations"]).lower()
    assert "no proven asymptotic complexity or big-o" in limitations
    for term in ("runtime call graph", "aliases", "dynamic dispatch", "decorators",
                 "peak allocation", "security", "quality"):
        assert term in limitations
    for forbidden in ("complexity", "big_o", "time_complexity", "space_complexity", "security_score"):
        assert forbidden not in report
        assert forbidden not in report["functions"][0]
