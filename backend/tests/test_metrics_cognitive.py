"""
Tests for intelligence.metrics.cognitive (SonarSource cognitive complexity).
"""

import sys
import textwrap

import pytest

from intelligence.metrics.cognitive import analyze_file, analyze_source, classify
from intelligence.metrics.cyclomatic import analyze_source as cyclomatic_source


def cog(source: str, name: str | None = None) -> int:
    result = analyze_source(textwrap.dedent(source))
    assert result.parse_error is None, result.parse_error
    if name is None:
        return result.functions[0].cognitive
    return {f.name: f for f in result.functions}[name].cognitive


# ── the core idea: nesting costs more ─────────────────────────────

FLAT = """
    def flat(a, b, c):
        if a:
            x()
        if b:
            y()
        if c:
            z()
"""

NESTED = """
    def nested(a, b, c):
        if a:
            if b:
                if c:
                    z()
"""


def test_flat_ifs_score_three():
    assert cog(FLAT) == 3


def test_nested_ifs_score_six():
    # 1 + 2 + 3
    assert cog(NESTED) == 6


def test_cyclomatic_cannot_tell_flat_from_nested():
    flat = cyclomatic_source(textwrap.dedent(FLAT)).functions[0].cyclomatic
    nested = cyclomatic_source(textwrap.dedent(NESTED)).functions[0].cyclomatic
    assert flat == nested == 4
    assert cog(NESTED) == 2 * cog(FLAT)


def test_worked_example_reset_password_is_six():
    # if +1, for +1, nested if +2, `and` +1, else +1
    assert cog("""
        def reset_password(email, token):
            if not email:
                return "Email required"
            for attempt in range(3):
                if token and send(email):
                    return "Sent"
                else:
                    log("retry")
            return "Failed"
    """) == 6


# ── if / elif / else ──────────────────────────────────────────────

def test_elif_and_else_have_no_nesting_penalty():
    assert cog("""
        def grade(s):
            if s > 90:
                return "A"
            elif s > 80:
                return "B"
            elif s > 70:
                return "C"
            else:
                return "F"
    """) == 4


def test_else_then_if_is_nested_unlike_elif():
    elif_version = cog("""
        def f(a, b):
            if a:
                x()
            elif b:
                y()
    """)
    else_if_version = cog("""
        def f(a, b):
            if a:
                x()
            else:
                if b:
                    y()
    """)
    assert elif_version == 2      # if +1, elif +1
    assert else_if_version == 4   # if +1, else +1, nested if +2


# ── boolean sequences ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "condition, expected",
    [
        ("a and b and c", 2),      # if +1, one sequence +1
        ("a and b or c", 3),       # if +1, two sequences +2
        ("a and (b and c)", 2),    # same operator: still one sequence
        ("not a", 1),              # `not` is free
    ],
)
def test_boolean_operator_sequences(condition, expected):
    assert cog(f"def f(a, b, c):\n    if {condition}:\n        return 1\n") == expected


# ── loops, try, with, match ───────────────────────────────────────

def test_nested_loops_and_if():
    # for +1, while +2, if +3
    assert cog("""
        def f(rows):
            for row in rows:
                while row:
                    if row.ok:
                        row = row.next
    """) == 6


def test_break_and_continue_are_free():
    assert cog("""
        def f(xs):
            for x in xs:
                if x:
                    break
                continue
    """) == 3


def test_for_else_counts_else():
    assert cog("""
        def f(xs):
            for x in xs:
                pass
            else:
                done()
    """) == 2


def test_try_adds_no_nesting_but_except_does():
    # except +1, except +1, if inside except +2
    assert cog("""
        def f():
            try:
                if ready():
                    go()
            except ValueError:
                if retry():
                    go()
            except KeyError:
                pass
            finally:
                cleanup()
    """) == 1 + 1 + 2 + 1


def test_with_adds_no_nesting():
    assert cog("""
        def f(path):
            with open(path) as fh:
                if fh:
                    return 1
    """) == 1


@pytest.mark.skipif(sys.version_info < (3, 10), reason="match needs Python 3.10+")
def test_match_counts_once_and_nests_cases():
    # match +1 (not per case), if inside a case +2
    assert cog("""
        def f(cmd, force):
            match cmd:
                case "start":
                    if force:
                        return 1
                case "stop":
                    return 2
                case _:
                    return 0
    """) == 3


# ── expressions, recursion, nested definitions ────────────────────

def test_ternary_nested_in_if():
    assert cog("""
        def f(a, b):
            if a:
                return 1 if b else 2
            return 0
    """) == 3


def test_comprehension_for_and_filter():
    assert cog("def f(xs):\n    return [x for x in xs if x]\n") == 2


def test_direct_recursion_adds_one():
    assert cog("""
        def fact(n):
            if n <= 1:
                return 1
            return n * fact(n - 1)
    """) == 2


def test_method_recursion_through_self():
    result = analyze_source(textwrap.dedent("""
        class Tree:
            def depth(self, node):
                if node is None:
                    return 0
                return 1 + self.depth(node.left)
    """))
    assert result.functions[0].name == "Tree.depth"
    assert result.functions[0].cognitive == 2


def test_nested_function_is_folded_into_parent_with_extra_nesting():
    result = analyze_source(textwrap.dedent("""
        def outer(xs):
            def inner(x):
                if x:
                    return 1
            return inner
    """))
    assert [f.name for f in result.functions] == ["outer"]
    assert result.functions[0].cognitive == 2  # if at nesting 1


def test_lambda_adds_nesting():
    assert cog("def f(xs):\n    return sorted(xs, key=lambda x: 1 if x else 0)\n") == 2


# ── explainability, aggregates, errors ────────────────────────────

def test_increments_explain_the_score():
    result = analyze_source(textwrap.dedent(NESTED))
    func = result.functions[0]
    assert [(i.line, i.amount, i.reason) for i in func.increments] == [
        (3, 1, "if"),
        (4, 2, "if (nesting 1)"),
        (5, 3, "if (nesting 2)"),
    ]
    assert sum(i.amount for i in func.increments) == func.cognitive
    assert func.to_dict()["increments"][2] == {"line": 5, "amount": 3, "reason": "if (nesting 2)"}


def test_file_aggregates():
    deep = "def deep(a):\n" + "".join(
        "    " * (i + 1) + f"if a > {i}:\n" for i in range(6)
    ) + "    " * 7 + "return a\n"
    src = "def simple():\n    return 1\n\n" + deep
    result = analyze_source(src)
    assert result.function_count == 2
    assert result.maximum == sum(range(1, 7))  # 1+2+...+6 = 21
    assert [f.name for f in result.high_complexity_functions] == ["deep"]
    assert result.to_dict()["functions"][1]["risk"] == "high"


@pytest.mark.parametrize(
    "value, band",
    [(0, "low"), (7, "low"), (8, "moderate"), (15, "moderate"), (16, "high")],
)
def test_bands(value, band):
    assert classify(value) == band


def test_syntax_error_reported(tmp_path):
    assert analyze_source("def f(:\n").parse_error is not None
    assert analyze_file(tmp_path / "missing.py").parse_error is not None


def test_bom_file_is_accepted(tmp_path):
    f = tmp_path / "bom.py"
    f.write_bytes(b"\xef\xbb\xbfdef f(a):\n    if a:\n        return 1\n")
    result = analyze_file(f)
    assert result.parse_error is None
    assert result.functions[0].cognitive == 1
