"""
Targeted Regression Test Suite for Shared Complexity Analyzer (Task 1.5).
Covers Features 5, 6, 7, 8, 9 with Boundary Value Analysis, Nested Scopes,
Radon CC & MI Schema Reconciliation, and Unavailable Complexity Merging.
"""

import ast
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from intelligence.analyzers.common.complexity import (
    _merge,
    _merge_radon_supplement,
    _run_ast_complexity,
    analyze_complexity,
)
from intelligence.evidence.merger import EvidenceMerger
from intelligence.evidence.models import CodeQualityEvidence, ComplexityEvidence


def sync_run(coro):
    """
    Run a coroutine synchronously by recursively stepping through yielded child coroutines.
    Guarantees deterministic execution across platforms without starting an IOCP event loop.
    """
    try:
        val = None
        while True:
            sub = coro.send(val)
            val = sync_run(sub) if inspect.iscoroutine(sub) else sub
    except StopIteration as e:
        return e.value


class TestMaintainabilityIndexSeparation:
    """Feature 5: Maintainability Index separated from comment ratio."""

    def test_radon_mi_dictionary_sets_maintainability_index(self):
        evidence = ComplexityEvidence()
        radon_mi_output = {"service.py": {"mi": 82.5, "rank": "A"}}
        _merge_radon_supplement(evidence, radon_mi_output)
        assert evidence.maintainability_index == 82.5
        assert evidence.comment_ratio == 0.0

    def test_comment_ratio_not_polluted_by_mi(self):
        evidence = ComplexityEvidence(comment_ratio=0.15)
        radon_mi_output = {"service.py": {"mi": 85.0, "rank": "A"}}
        _merge_radon_supplement(evidence, radon_mi_output)
        assert evidence.comment_ratio == 0.15
        assert evidence.maintainability_index == 85.0

    def test_maintainability_index_direct_key_support(self):
        evidence = ComplexityEvidence()
        supplement = {"maintainability_index": 76.4}
        _merge_radon_supplement(evidence, supplement)
        assert evidence.maintainability_index == 76.4

    def test_mi_averaged_across_multiple_files(self):
        evidence = ComplexityEvidence()
        radon_mi_output = {
            "a.py": {"mi": 80.0, "rank": "A"},
            "b.py": {"mi": 90.0, "rank": "A"},
        }
        _merge_radon_supplement(evidence, radon_mi_output)
        assert evidence.maintainability_index == 85.0

    def test_mi_absent_preserves_none(self):
        evidence = ComplexityEvidence()
        _merge_radon_supplement(evidence, {"other_key": 123})
        assert evidence.maintainability_index is None

    @pytest.mark.parametrize("mi_val", [-10.0, -5.0, 0.0, 100.0, 150.0])
    def test_extreme_boundary_mi_values(self, mi_val):
        evidence = ComplexityEvidence()
        _merge_radon_supplement(evidence, {"mod.py": {"mi": mi_val, "rank": "X"}})
        assert evidence.maintainability_index == mi_val

    def test_invalid_mi_values_ignored(self):
        evidence = ComplexityEvidence()
        _merge_radon_supplement(evidence, {"bad.py": {"mi": "not-a-number", "rank": "X"}})
        assert evidence.maintainability_index is None


class TestRadonSupplementaryOutputSchemaReconciliation:
    """Feature 6: Radon supplementary output schema reconciliation."""

    def test_radon_cc_schema_merges_high_complexity_functions(self):
        evidence = ComplexityEvidence(high_complexity_functions=[{"function": "f1", "complexity": 11}])
        radon_cc_output = {
            "high_complexity_functions": [{"function": "f2", "complexity": 14}],
            "max_complexity": 14,
        }
        _merge_radon_supplement(evidence, radon_cc_output)
        fn_names = {f["function"] for f in evidence.high_complexity_functions}
        assert "f1" in fn_names
        assert "f2" in fn_names

    def test_radon_cc_schema_updates_max_complexity(self):
        evidence = ComplexityEvidence(max_complexity=8)
        radon_cc_output = {"max_complexity": 15, "high_complexity_functions": []}
        _merge_radon_supplement(evidence, radon_cc_output)
        assert evidence.max_complexity == 15

    def test_radon_cc_schema_deduplicates_functions(self):
        evidence = ComplexityEvidence(high_complexity_functions=[{"function": "process", "complexity": 12}])
        radon_cc_output = {
            "high_complexity_functions": [{"function": "process", "complexity": 12}],
            "max_complexity": 12,
        }
        _merge_radon_supplement(evidence, radon_cc_output)
        assert len(evidence.high_complexity_functions) == 1

    def test_radon_cc_schema_deduplicates_by_name_and_file(self):
        evidence = ComplexityEvidence(high_complexity_functions=[
            {"function": "handler", "file": "a.py", "complexity": 12},
        ])
        radon_cc_output = {
            "high_complexity_functions": [
                {"function": "handler", "file": "a.py", "complexity": 12},  # duplicate
                {"function": "handler", "file": "b.py", "complexity": 13},  # different file -> keep
            ],
            "max_complexity": 13,
        }
        _merge_radon_supplement(evidence, radon_cc_output)
        assert len(evidence.high_complexity_functions) == 2
        files = {f["file"] for f in evidence.high_complexity_functions}
        assert files == {"a.py", "b.py"}

    def test_non_dict_result_handled_gracefully(self):
        evidence = ComplexityEvidence(max_complexity=5)
        _merge_radon_supplement(evidence, None)
        _merge_radon_supplement(evidence, "unexpected string")
        _merge_radon_supplement(evidence, [1, 2, 3])
        assert evidence.max_complexity == 5

    def test_empty_dict_result_handled_gracefully(self):
        evidence = ComplexityEvidence(max_complexity=5, comment_ratio=0.1)
        _merge_radon_supplement(evidence, {})
        assert evidence.max_complexity == 5
        assert evidence.comment_ratio == 0.1

    def test_max_complexity_guard_when_current_is_none(self):
        evidence = ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None)
        radon_cc_output = {"max_complexity": 12, "high_complexity_functions": []}
        _merge_radon_supplement(evidence, radon_cc_output)
        assert evidence.max_complexity == 12

    def test_combined_cc_and_mi_supplement(self):
        evidence = ComplexityEvidence()
        combined_output = {
            "max_complexity": 10,
            "high_complexity_functions": [{"function": "heavy", "complexity": 10}],
            "maintainability_index": 78.5,
        }
        _merge_radon_supplement(evidence, combined_output)
        assert evidence.max_complexity == 10
        assert len(evidence.high_complexity_functions) == 1
        assert evidence.maintainability_index == 78.5


class TestPythonASTBranchCounting:
    """Feature 7: Python AST branch counting metric definition (CC = 1 + B)."""

    def test_ternary_ifexp_counts_branch(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "ternary.py"
            py_file.write_text("def choose(cond, a, b):\n    return a if cond else b\n", encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2
            assert res["average_complexity"] == 2.0

    def test_listcomp_with_filter_counts_branch(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "comp.py"
            py_file.write_text("def filter_pos(items):\n    return [x for x in items if x > 0]\n", encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2

    def test_dictcomp_setcomp_genexp_counts_branch(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "comprehensions.py"
            code = (
                "def make_comprehensions(items):\n"
                "    d = {k: v for k, v in items}\n"
                "    s = {x for x in items}\n"
                "    g = (x for x in items)\n"
                "    return d, s, g\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # Base (1) + dictcomp (1) + setcomp (1) + genexp (1) = 4
            assert res["max_complexity"] == 4

    def test_boolop_counts_n_minus_1_branches(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "boolop.py"
            code = "def validate(a, b, c, d):\n    if a and b and c and d:\n        return True\n    return False\n"
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # Base (1) + if (1) + 4-operand and (3) = 5
            assert res["max_complexity"] == 5

    def test_assert_statement_counts_branch(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "assertion.py"
            code = "def check_positive(x):\n    assert x > 0\n    return x\n"
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2

    def test_match_case_statements(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "matching.py"
            code = (
                "def evaluate_status(status):\n"
                "    match status:\n"
                "        case 200:\n"
                "            return 'OK'\n"
                "        case 404:\n"
                "            return 'Not Found'\n"
                "        case 500:\n"
                "            return 'Internal Error'\n"
                "        case _:\n"
                "            return 'Unknown'\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # Base (1) + 4 case branches = 5
            assert res["max_complexity"] == 5

    def test_composite_function_cc(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "composite.py"
            code = (
                "def process(items):\n"
                "    for x in items:\n"
                "        if x > 0:\n"
                "            pass\n"
                "        elif x < -10:\n"
                "            pass\n"
                "    try:\n"
                "        while False:\n"
                "            pass\n"
                "    except ValueError:\n"
                "        pass\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # Base (1) + for (1) + if (1) + elif (1) + while (1) + except (1) = 6
            assert res["max_complexity"] == 6

    def test_empty_python_file_returns_empty_functions(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "empty.py"
            py_file.write_text("", encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            assert res["functions"] == []
            assert res["high_complexity_functions"] == []
            assert res["average_complexity"] in (0.0, None)

    def test_docstring_and_pass_has_cc_1(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "noop.py"
            code = 'def noop():\n    """Docstring only."""\n    pass\n'
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 1
            assert res["average_complexity"] == 1.0


class TestNestedFunctionScoping:
    """Feature 8: Nested function and class scoping."""

    def test_outer_function_does_not_count_inner_def_branches(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "nest.py"
            code = (
                "def outer(x):\n"
                "    if x > 0:\n"
                "        pass\n"
                "    def inner(y, z):\n"
                "        if y > 0 and z > 0:\n"
                "            return True\n"
                "        return False\n"
                "    return inner\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # outer: 1 + if(1) = 2
            # inner: 1 + if(1) + and(1) = 3
            assert res["max_complexity"] == 3
            assert res["average_complexity"] == 2.5

    def test_outer_function_does_not_count_async_inner_branches(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "async_nest.py"
            code = (
                "def make_coro():\n"
                "    async def fetch(url):\n"
                "        if not url:\n"
                "            return None\n"
                "    return fetch\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # make_coro: 1
            # fetch: 1 + if(1) = 2
            assert res["max_complexity"] == 2
            assert res["average_complexity"] == 1.5

    def test_outer_function_does_not_count_inner_class_branches(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "inner_cls.py"
            code = (
                "def factory():\n"
                "    class LocalHandler:\n"
                "        def handle(self, x):\n"
                "            if x:\n"
                "                return 1\n"
                "    return LocalHandler()\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # factory: 1
            # handle: 1 + if(1) = 2
            assert res["max_complexity"] == 2

    def test_multiple_nested_closures_scoped_independently(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "multi_closures.py"
            code = (
                "def builder():\n"
                "    def add_op(a, b):\n"
                "        if a > 0:\n"
                "            return a + b\n"
                "    def sub_op(a, b):\n"
                "        if b > 0:\n"
                "            return a - b\n"
                "    return add_op, sub_op\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # builder: 1, add_op: 2, sub_op: 2 -> avg = 5/3 = 1.67
            assert res["max_complexity"] == 2
            assert round(res["average_complexity"], 2) == 1.67

    def test_average_complexity_computed_over_all_function_scopes(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "two_fns.py"
            code = (
                "def fn_simple():\n"
                "    pass\n"
                "def fn_branch(x):\n"
                "    if x:\n"
                "        pass\n"
            )
            py_file.write_text(code, encoding="utf-8")
            res = _run_ast_complexity([str(py_file)])
            # fn_simple: 1, fn_branch: 2 -> avg = 1.5
            assert res["average_complexity"] == 1.5


class TestUnavailableComplexityRepresentation:
    """Feature 9: Unavailable complexity representation and merger behavior."""

    def test_unmeasured_complexity_representation(self):
        evidence = ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None)
        assert evidence.is_available is False
        assert evidence.average_complexity is None
        assert evidence.max_complexity is None

    def test_analyze_complexity_unavailable_when_no_tool_runs(self):
        with TemporaryDirectory() as tmp_dir:
            js_file = Path(tmp_dir) / "app.js"
            js_file.write_text("console.log('hello');", encoding="utf-8")
            tools_exec, tools_skip = [], []
            with patch("shutil.which", return_value=None):
                evidence = sync_run(analyze_complexity(["app.js"], tmp_dir, tools_exec, tools_skip))
            assert evidence.is_available is False
            assert evidence.average_complexity is None
            assert evidence.max_complexity is None

    def test_analyze_complexity_empty_files_returns_unavailable(self):
        tools_exec, tools_skip = [], []
        evidence = sync_run(analyze_complexity([], "/some/repo", tools_exec, tools_skip))
        assert evidence.is_available is False
        assert evidence.average_complexity is None
        assert evidence.max_complexity is None

    def test_merger_ignores_unmeasured_complexity(self):
        ev_measured = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="python",
            complexity=ComplexityEvidence(
                is_available=True,
                average_complexity=4.0,
                max_complexity=6,
                lines_of_code=100,
            ),
        )
        ev_unmeasured = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="javascript",
            complexity=ComplexityEvidence(
                is_available=False,
                average_complexity=None,
                max_complexity=None,
                lines_of_code=200,
            ),
        )
        merged = EvidenceMerger.merge([ev_measured, ev_unmeasured])
        assert merged.complexity.average_complexity == 4.0
        assert merged.complexity.max_complexity == 6
        assert merged.complexity.is_available is True

    def test_merger_returns_unavailable_when_all_unmeasured(self):
        ev1 = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="javascript",
            complexity=ComplexityEvidence(
                is_available=False,
                average_complexity=None,
                max_complexity=None,
                lines_of_code=100,
            ),
        )
        ev2 = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="typescript",
            complexity=ComplexityEvidence(
                is_available=False,
                average_complexity=None,
                max_complexity=None,
                lines_of_code=100,
            ),
        )
        merged = EvidenceMerger.merge([ev1, ev2])
        assert merged.complexity.is_available is False
        assert merged.complexity.average_complexity is None
        assert merged.complexity.max_complexity is None

    def test_merger_weighted_average_uses_measured_loc(self):
        ev_py = CodeQualityEvidence(
            repository_id="polyglot",
            primary_language="python",
            complexity=ComplexityEvidence(
                is_available=True,
                average_complexity=3.5,
                max_complexity=7,
                lines_of_code=150,
            ),
        )
        ev_js = CodeQualityEvidence(
            repository_id="polyglot",
            primary_language="javascript",
            complexity=ComplexityEvidence(
                is_available=False,
                average_complexity=None,
                max_complexity=None,
                lines_of_code=350,
            ),
        )
        merged = EvidenceMerger.merge([ev_py, ev_js])
        # Weighted average must divide by measured LOC (150), not total LOC (500)
        assert merged.complexity.average_complexity == 3.5
        assert merged.complexity.max_complexity == 7
        assert merged.complexity.lines_of_code == 500

    def test_merger_preserves_total_loc_for_duplication(self):
        ev1 = ComplexityEvidence(is_available=True, average_complexity=2.0, max_complexity=4, lines_of_code=100)
        ev2 = ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None, lines_of_code=400)
        merged = EvidenceMerger._merge_complexity([ev1, ev2])
        assert merged.lines_of_code == 500
        assert merged.average_complexity == 2.0

    def test_merger_averages_maintainability_index(self):
        ev1 = ComplexityEvidence(is_available=True, average_complexity=2.0, maintainability_index=80.0, lines_of_code=100)
        ev2 = ComplexityEvidence(is_available=True, average_complexity=3.0, maintainability_index=90.0, lines_of_code=100)
        ev3 = ComplexityEvidence(is_available=False, average_complexity=None, maintainability_index=None, lines_of_code=50)
        merged = EvidenceMerger._merge_complexity([ev1, ev2, ev3])
        assert merged.maintainability_index == 85.0

    def test_merger_empty_or_none_list(self):
        merged_empty = EvidenceMerger._merge_complexity([])
        assert merged_empty.is_available is False
        assert merged_empty.average_complexity is None

        merged_none = EvidenceMerger._merge_complexity([None, None])
        assert merged_none.is_available is False
        assert merged_none.average_complexity is None
