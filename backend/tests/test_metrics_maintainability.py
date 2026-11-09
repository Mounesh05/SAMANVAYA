"""
Tests for intelligence.metrics.size and intelligence.metrics.maintainability.
"""

import math
import textwrap

import pytest

from intelligence.metrics.maintainability import (
    Halstead,
    analyze_file,
    analyze_source,
    classify,
    halstead,
    halstead_tokens,
    maintainability_index,
)
from intelligence.metrics.size import measure_file, measure_source

SIZE_SAMPLE = (
    '"""Module docstring."""\n'   # 1 docstring
    "\n"                          # 2 blank
    "import os  # trailing\n"     # 3 code + comment
    "# a comment\n"               # 4 comment
    "def f(x):\n"                 # 5 code
    '    """Function doc\n'       # 6 docstring
    '    more."""\n'              # 7 docstring
    "    return x\n"              # 8 code
)


# ── size ──────────────────────────────────────────────────────────

def test_size_line_categories():
    size = measure_source(SIZE_SAMPLE)
    assert size.parse_error is None
    assert size.loc == 8
    assert size.blank_lines == 1
    assert size.comment_lines == 2        # lines 3 and 4
    assert size.docstring_lines == 3      # lines 1, 6, 7
    assert size.code_lines == 3           # lines 3, 5, 8
    # commented = {1,3,4,6,7} = 5  ->  5 / (3 + 5)
    assert size.comment_density == 62.5


def test_multiline_string_that_is_not_a_docstring_is_code():
    size = measure_source('x = """a\nb\nc"""\n')
    assert size.docstring_lines == 0
    assert size.code_lines == 3


def test_size_errors_and_bom(tmp_path):
    assert measure_source("def f(:\n").parse_error is not None
    assert measure_file(tmp_path / "missing.py").parse_error is not None
    f = tmp_path / "bom.py"
    f.write_bytes(b"\xef\xbb\xbfx = 1\n")
    assert measure_file(f).code_lines == 1


# ── Halstead ──────────────────────────────────────────────────────

def test_halstead_simple_assignment():
    h = halstead(halstead_tokens("x = a + b\n"))
    # operators: = +    operands: x a b
    assert (h.distinct_operators, h.total_operators) == (2, 2)
    assert (h.distinct_operands, h.total_operands) == (3, 3)
    assert h.vocabulary == 5 and h.length == 5
    assert h.volume == pytest.approx(5 * math.log2(5))
    assert h.difficulty == pytest.approx(1.0)        # (2/2) * (3/3)
    assert h.effort == pytest.approx(h.volume)


def test_halstead_brackets_keywords_and_constants():
    h = halstead(halstead_tokens("if x is None:\n    print(x, 'hi')\n"))
    # operators: if is : ( ,        operands: x None print x 'hi'
    assert h.total_operators == 5 and h.distinct_operators == 5
    assert h.total_operands == 5 and h.distinct_operands == 4


def test_halstead_empty():
    h = Halstead()
    assert h.volume == 0 and h.difficulty == 0 and h.effort == 0


# ── MI formula ────────────────────────────────────────────────────

def test_mi_formula_hand_computed():
    # 171 - 5.2 ln(100) - 0.23*5 - 16.2 ln(20) = 97.3722  -> *100/171 = 56.94
    assert maintainability_index(100, 5, 20) == 56.94


def test_mi_is_clamped_to_0_100():
    assert maintainability_index(1e12, 500, 1_000_000) == 0.0
    # 171 - 5.2 ln(1.5) - 0.23 = 168.66 -> 98.63 (only the comment bonus can exceed 100)
    assert maintainability_index(1.5, 1, 1) == 98.63
    assert maintainability_index(1.5, 1, 1, comment_percent=100) == 100.0
    assert maintainability_index(0, 1, 10) == 100.0     # nothing to maintain
    assert maintainability_index(50, 1, 0) == 100.0


def test_comment_bonus_raises_mi():
    without = maintainability_index(500, 10, 50)
    with_comments = maintainability_index(500, 10, 50, comment_percent=30)
    assert with_comments > without


@pytest.mark.parametrize("value, band", [(100, "high"), (20, "high"), (19.9, "moderate"), (10, "moderate"), (9.99, "low"), (0, "low")])
def test_bands(value, band):
    assert classify(value) == band


# ── file and function analysis ────────────────────────────────────

SIMPLE = "def add(a, b):\n    return a + b\n"

COMPLEX = "def tangled(x, y, z):\n" + "".join(
    f"    if x > {i} and y < {i} or z == {i}:\n        x = x * {i} + y - z\n" for i in range(40)
) + "    return x\n"


def test_simple_code_is_more_maintainable_than_complex_code():
    simple = analyze_source(SIMPLE)
    complex_ = analyze_source(COMPLEX)
    assert simple.parse_error is None and complex_.parse_error is None
    assert simple.mi > complex_.mi
    assert simple.rank == "high"


def test_per_function_results():
    result = analyze_source(SIMPLE + "\n" + COMPLEX)
    names = [f.name for f in result.functions]
    assert names == ["add", "tangled"]
    add, tangled = result.functions
    assert add.cyclomatic == 1 and add.code_lines == 2
    assert tangled.cyclomatic == 1 + 40 * 3
    assert tangled.mi < add.mi
    assert result.cyclomatic_total == add.cyclomatic + tangled.cyclomatic
    data = result.to_dict()
    assert data["functions"][0]["rank"] == "high"
    assert set(data["halstead"]) >= {"volume", "difficulty", "effort", "bugs"}


def test_average_function_mi_does_not_punish_file_size():
    many_small = "\n".join(f"def f{i}(a, b):\n    return a + b * {i}\n" for i in range(200))
    result = analyze_source(many_small)
    assert result.average_function_mi > 60          # each function is trivial
    assert result.mi < result.average_function_mi   # file-level MI drops with size
    assert analyze_source("x = 1\n").average_function_mi == analyze_source("x = 1\n").mi


def test_file_mi_matches_formula_inputs():
    result = analyze_source(SIMPLE)
    expected = maintainability_index(result.halstead.volume, result.cyclomatic_total, result.code_lines)
    assert result.mi == expected


def test_include_comments_option():
    documented = textwrap.dedent('''
        def add(a, b):
            """Add two numbers.

            Returns their sum.
            """
            # plain addition
            return a + b
    ''')
    assert analyze_source(documented, include_comments=True).mi > analyze_source(documented).mi


def test_empty_and_broken_files(tmp_path):
    assert analyze_source("").mi == 100.0
    assert analyze_source("def f(:\n").parse_error is not None
    assert analyze_file(tmp_path / "missing.py").parse_error is not None


def test_low_maintainability_list():
    huge = "def huge(a):\n" + "".join(
        f"    if a == {i} or a == {i + 1000} and a != {i + 2000}:\n        a = (a * {i} + {i}) // ({i} + 1) - a % {i + 3}\n"
        for i in range(400)
    ) + "    return a\n"
    result = analyze_source(huge)
    assert [f.name for f in result.low_maintainability_functions] == ["huge"]
    assert result.functions[0].rank == "low"
