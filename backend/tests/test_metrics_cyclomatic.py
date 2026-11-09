"""
Tests for intelligence.metrics.cyclomatic (McCabe cyclomatic complexity).
"""

import sys
import textwrap

import pytest

from intelligence.metrics.cyclomatic import (
    analyze_file,
    analyze_source,
    classify,
)


def cc(source: str, name: str | None = None) -> int:
    """Complexity of the first (or named) function in the snippet."""
    result = analyze_source(textwrap.dedent(source))
    assert result.parse_error is None, result.parse_error
    funcs = {f.name: f for f in result.functions}
    if name is None:
        return result.functions[0].cyclomatic
    return funcs[name].cyclomatic


# ── basic constructs ──────────────────────────────────────────────

def test_straight_line_function_is_one():
    assert cc("""
        def greet(name):
            message = "Hello " + name
            return message
    """) == 1


def test_if_else_is_two():
    assert cc("""
        def check_age(age):
            if age >= 18:
                return "Adult"
            else:
                return "Minor"
    """) == 2


def test_elif_chain_counts_each_branch():
    assert cc("""
        def grade(score):
            if score > 90:
                return "A"
            elif score > 80:
                return "B"
            elif score > 70:
                return "C"
            else:
                return "F"
    """) == 4


def test_boolean_operators_count_extra_operands():
    # if (+1), `a and b and c` (+2), `or d` (+1)
    assert cc("""
        def f(a, b, c, d):
            if a and b and c or d:
                return 1
            return 0
    """) == 5


def test_loops_and_ternary():
    # for (+1), while (+1), ternary (+1)
    assert cc("""
        def f(items):
            total = 0
            for x in items:
                total += x
            while total > 10:
                total -= 1
            return "big" if total > 5 else "small"
    """) == 4


def test_each_except_handler_counts_finally_does_not():
    assert cc("""
        def f():
            try:
                risky()
            except ValueError:
                pass
            except (KeyError, TypeError):
                pass
            finally:
                cleanup()
    """) == 3


def test_comprehension_loop_and_filters():
    # comprehension for (+1) + two ifs (+2)
    assert cc("""
        def evens(xs):
            return [x for x in xs if x > 0 if x % 2 == 0]
    """) == 4


@pytest.mark.skipif(sys.version_info < (3, 10), reason="match needs Python 3.10+")
def test_match_cases_count_except_wildcard():
    assert cc("""
        def f(cmd):
            match cmd:
                case "start":
                    return 1
                case "stop":
                    return 2
                case _:
                    return 0
    """) == 3


def test_async_function_and_async_for():
    assert cc("""
        async def f(stream):
            async for item in stream:
                if item:
                    return item
    """) == 3


def test_worked_example_reset_password_is_seven():
    # The example from the explanation: 6 decision points + 1
    assert cc("""
        def reset_password(email, token):
            if not email:
                return "Email required"
            if "@" not in email:
                return "Invalid email"
            if token is None or token == "":
                return "Token missing"
            for attempt in range(3):
                if send_email(email):
                    return "Sent"
            return "Failed"
    """) == 7


# ── scoping ───────────────────────────────────────────────────────

def test_nested_function_measured_separately():
    src = """
        def outer(x):
            def inner(y):
                if y:
                    return 1
                return 0
            if x:
                return inner(x)
            return None
    """
    assert cc(src, "outer") == 2
    assert cc(src, "outer.inner") == 2


def test_class_methods_get_qualified_names():
    result = analyze_source(textwrap.dedent("""
        class AuthService:
            def login(self, ok):
                if ok:
                    return True
                return False

            def logout(self):
                return None
    """))
    names = [f.name for f in result.functions]
    assert names == ["AuthService.login", "AuthService.logout"]
    assert [f.cyclomatic for f in result.functions] == [2, 1]


def test_lambda_decisions_count_in_enclosing_function():
    assert cc("""
        def f(xs):
            return sorted(xs, key=lambda x: x if x else 0)
    """) == 2


# ── aggregates, bands, errors ─────────────────────────────────────

def test_file_aggregates_and_high_complexity_list():
    branches = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(12))
    src = f"def simple():\n    return 1\n\ndef complex_one(x):\n{branches}\n    return -1\n"
    result = analyze_source(src)
    assert result.function_count == 2
    assert result.maximum == 13
    assert result.total == 14
    assert result.average == 7.0
    assert [f.name for f in result.high_complexity_functions] == ["complex_one"]
    data = result.to_dict()
    assert data["high_complexity_count"] == 1
    assert data["functions"][1]["risk"] == "moderate"


@pytest.mark.parametrize(
    "value, band",
    [(1, "low"), (10, "low"), (11, "moderate"), (20, "moderate"),
     (21, "high"), (50, "high"), (51, "very_high")],
)
def test_risk_bands(value, band):
    assert classify(value) == band


def test_syntax_error_is_reported_not_raised():
    result = analyze_source("def broken(:\n    pass\n", path="bad.py")
    assert result.parse_error is not None
    assert result.functions == []
    assert result.average == 0.0 and result.maximum == 0


def test_empty_module_has_no_functions():
    result = analyze_source("x = 1\n")
    assert result.function_count == 0
    assert result.average == 0.0


def test_analyze_file_reads_from_disk(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("def f(a):\n    return a or 1\n", encoding="utf-8")
    result = analyze_file(f)
    assert result.parse_error is None
    assert result.functions[0].cyclomatic == 2


def test_utf8_bom_is_accepted(tmp_path):
    f = tmp_path / "bom.py"
    f.write_bytes(b"\xef\xbb\xbfdef f(a):\n    if a:\n        return 1\n")
    result = analyze_file(f)
    assert result.parse_error is None
    assert result.functions[0].cyclomatic == 2
    assert analyze_source("\ufeffdef g():\n    return 1\n").parse_error is None


def test_analyze_file_missing_file_is_reported(tmp_path):
    result = analyze_file(tmp_path / "missing.py")
    assert result.parse_error is not None
