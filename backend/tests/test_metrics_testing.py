"""
Tests for intelligence.metrics.testing (coverage, diff coverage, pass rate,
flaky tests, bug density).
"""

import textwrap

import pytest

from intelligence.metrics.testing import (
    FAILED,
    FAILING,
    FLAKY,
    PASSED,
    SKIPPED,
    STABLE,
    SUSPECTED_FLAKY,
    TestRunRecord,
    bug_density,
    classify_tests,
    diff_coverage,
    flakiness,
    normalize_path,
    parse_cobertura,
    parse_coverage,
    parse_junit,
    parse_lcov,
    parse_unified_diff,
    pass_rate,
    to_ranges,
    wilson_interval,
)

COBERTURA = textwrap.dedent("""\
    <?xml version="1.0" ?>
    <coverage version="7.6" line-rate="0.6" branch-rate="0.5">
      <sources><source>/home/runner/work/app</source></sources>
      <packages>
        <package name="pkg">
          <classes>
            <class name="orders.py" filename="pkg/orders.py">
              <lines>
                <line number="1" hits="1"/>
                <line number="2" hits="1"/>
                <line number="3" hits="0"/>
                <line number="4" hits="3" branch="true" condition-coverage="50% (1/2)"/>
                <line number="5" hits="0"/>
              </lines>
            </class>
            <class name="Helper" filename="pkg/orders.py">
              <lines>
                <line number="3" hits="2"/>
              </lines>
            </class>
            <class name="util.py" filename="./pkg\\util.py">
              <lines><line number="10" hits="0"/></lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
""")

LCOV = textwrap.dedent("""\
    TN:
    SF:src/app.js
    FN:1,main
    DA:1,1
    DA:2,0
    DA:3,4
    BRDA:3,0,0,1
    BRDA:3,0,1,-
    LF:3
    LH:2
    end_of_record
    SF:src/empty.js
    DA:7,0
    end_of_record
""")

DIFF = textwrap.dedent("""\
    diff --git a/pkg/orders.py b/pkg/orders.py
    index 1111111..2222222 100644
    --- a/pkg/orders.py
    +++ b/pkg/orders.py
    @@ -2,3 +2,4 @@ def process(order):
         total = 0
    -    old = 1
    +    new = 1
    +    extra = 2
         return total
    @@ -20,0 +22,1 @@
    +# just a comment
    diff --git a/pkg/new_module.py b/pkg/new_module.py
    new file mode 100644
    --- /dev/null
    +++ b/pkg/new_module.py
    @@ -0,0 +1,2 @@
    +def f():
    +    return 1
    \\ No newline at end of file
    diff --git a/pkg/gone.py b/pkg/gone.py
    deleted file mode 100644
    --- a/pkg/gone.py
    +++ /dev/null
    @@ -1,1 +0,0 @@
    -x = 1
    diff --git a/README.md b/README.md
    --- a/README.md
    +++ b/README.md
    @@ -1 +1 @@
    -old
    +new
    diff --git a/img.png b/img.png
    Binary files a/img.png and b/img.png differ
""")

JUNIT = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest" tests="5" failures="1" errors="1" skipped="1">
        <testcase classname="tests.test_orders" name="test_ok" time="0.010"/>
        <testcase classname="tests.test_orders" name="test_bad" time="0.020"><failure message="assert"/></testcase>
        <testcase classname="tests.test_orders" name="test_boom" time="bad"><error message="boom"/></testcase>
        <testcase classname="tests.test_orders" name="test_later"><skipped/></testcase>
        <testcase name="test_no_class" time="1.5"/>
      </testsuite>
    </testsuites>
""")


# ── helpers ───────────────────────────────────────────────────────

def test_to_ranges():
    assert to_ranges([9, 1, 2, 3, 7, 10, 2]) == [(1, 3), (7, 7), (9, 10)]
    assert to_ranges([]) == []


@pytest.mark.parametrize("raw, expected", [
    ("./pkg\\util.py", "pkg/util.py"),
    ("pkg//a.py", "pkg/a.py"),
    ("/home/runner/work/app/pkg/a.py", "pkg/a.py"),
])
def test_normalize_path(raw, expected):
    assert normalize_path(raw, strip_prefixes=["/home/runner/work/app"]) == expected


# ── coverage ──────────────────────────────────────────────────────

def test_cobertura_lines_branches_and_merged_classes():
    report = parse_cobertura(COBERTURA)
    orders = report.files["pkg/orders.py"]
    assert orders.covered == {1, 2, 3, 4}          # line 3 hit by the second <class>
    assert orders.uncovered == {5}
    assert (orders.branches_covered, orders.branches_total) == (1, 2)
    assert orders.line_rate == 80.0 and orders.branch_rate == 50.0
    assert report.files["pkg/util.py"].uncovered == {10}   # "./pkg\\util.py" normalized
    assert report.lines_covered == 4 and report.lines_coverable == 6
    assert report.line_rate == 66.67
    assert report.to_dict()["format"] == "cobertura"


def test_lcov_lines_and_branches():
    report = parse_lcov(LCOV)
    app = report.files["src/app.js"]
    assert app.covered == {1, 3} and app.uncovered == {2}
    assert (app.branches_covered, app.branches_total) == (1, 2)
    assert report.files["src/empty.js"].line_rate == 0.0
    assert report.line_rate == 50.0


def test_parse_coverage_detects_format():
    assert parse_coverage(COBERTURA).source_format == "cobertura"
    assert parse_coverage(LCOV).source_format == "lcov"


def test_empty_report_has_no_rate():
    report = parse_lcov("")
    assert report.line_rate is None and report.branch_rate is None


# ── diff parsing and diff coverage ────────────────────────────────

def test_unified_diff_new_line_numbers():
    changed = parse_unified_diff(DIFF)
    assert changed["pkg/orders.py"] == {3, 4, 22}       # "-" lines do not advance the new file
    assert changed["pkg/new_module.py"] == {1, 2}
    assert changed["README.md"] == {1}
    assert "pkg/gone.py" not in changed and "img.png" not in changed


def test_diff_coverage_counts_only_executable_changed_lines():
    coverage = parse_cobertura(COBERTURA)
    changed = {"pkg/orders.py": {3, 4, 5, 22}, "pkg/new_module.py": {1, 2}, "README.md": {1}, "pkg/util.py": {99}}
    result = diff_coverage(changed, coverage, source_suffixes=[".py"])
    assert [f.path for f in result.files] == ["pkg/orders.py"]   # util.py: changed line not executable
    orders = result.files[0]
    assert (orders.coverable, orders.covered) == (3, 2)          # line 22 is not executable
    assert orders.uncovered_ranges == [(5, 5)]
    assert result.percent == 66.67
    assert result.files_without_coverage == ["pkg/new_module.py"]  # README.md is not a source file
    assert result.to_dict()["files"][0]["uncovered_ranges"] == [[5, 5]]


def test_diff_coverage_none_when_nothing_executable_changed():
    result = diff_coverage({"pkg/orders.py": {22}}, parse_cobertura(COBERTURA))
    assert result.percent is None and result.files == []


def test_diff_coverage_end_to_end_from_diff_text():
    coverage = parse_cobertura(COBERTURA)
    result = diff_coverage(parse_unified_diff(DIFF), coverage, source_suffixes=[".py"])
    assert (result.covered, result.coverable) == (2, 2)          # lines 3 and 4 of orders.py
    assert result.percent == 100.0


# ── JUnit and pass rate ───────────────────────────────────────────

def test_parse_junit_per_test_results():
    results = {r.test_id: r for r in parse_junit(JUNIT)}
    assert results["tests.test_orders::test_ok"].status == PASSED
    assert results["tests.test_orders::test_bad"].status == FAILED
    assert results["tests.test_orders::test_boom"].status == FAILED      # error counts as failure
    assert results["tests.test_orders::test_boom"].duration_seconds == 0.0
    assert results["tests.test_orders::test_later"].status == SKIPPED
    assert results["test_no_class"].duration_seconds == 1.5


def test_pass_rate_excludes_skipped():
    rate = pass_rate(parse_junit(JUNIT))
    assert (rate.run, rate.passed, rate.failed, rate.skipped) == (5, 2, 2, 1)
    assert rate.percent == 50.0
    assert pass_rate([]).percent is None


# ── flaky tests ───────────────────────────────────────────────────

@pytest.mark.parametrize("failures, runs, low, high", [
    (0, 10, 0.0, 0.2775),
    (5, 10, 0.2366, 0.7634),
    (1, 2, 0.0945, 0.9055),
    (10, 10, 0.7225, 1.0),
])
def test_wilson_interval_reference_values(failures, runs, low, high):
    lo, hi = wilson_interval(failures, runs)
    assert lo == pytest.approx(low, abs=1e-4) and hi == pytest.approx(high, abs=1e-4)


def test_wilson_with_no_runs_is_unknown():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def history():
    records = []
    # A: failed then passed on the same commit (a retry) -> flaky
    records += [TestRunRecord("A", "c1", PASSED, 1), TestRunRecord("A", "c2", FAILED, 2), TestRunRecord("A", "c2", PASSED, 3)]
    # B: alternates across 8 different commits -> suspected flaky
    records += [TestRunRecord("B", f"c{i}", PASSED if i % 2 else FAILED, i) for i in range(8)]
    # C: last three runs failed -> failing (a real regression, not flakiness)
    records += [TestRunRecord("C", f"c{i}", s, i) for i, s in enumerate([PASSED, PASSED, FAILED, FAILED, FAILED])]
    # D: always passes, one skipped run ignored -> stable
    records += [TestRunRecord("D", f"c{i}", PASSED, i) for i in range(6)] + [TestRunRecord("D", "c9", SKIPPED, 9)]
    # E: alternates but only 3 runs -> not enough evidence, stable
    records += [TestRunRecord("E", f"c{i}", s, i) for i, s in enumerate([PASSED, FAILED, PASSED])]
    return records


def test_classify_tests():
    by_id = {t.test_id: t for t in classify_tests(history())}
    assert by_id["A"].classification == FLAKY and by_id["A"].same_commit_flips == 1
    assert by_id["B"].classification == SUSPECTED_FLAKY and by_id["B"].flip_rate == 100.0
    assert by_id["C"].classification == FAILING
    assert by_id["D"].classification == STABLE and by_id["D"].runs == 6   # skipped run ignored
    assert by_id["E"].classification == STABLE


def test_one_state_change_is_not_flakiness():
    # P P P P F F: one pass->fail change (flip rate 20%) is a state change, not flakiness,
    # and two failures are below the failing streak of 3
    single = [TestRunRecord("S", f"c{i}", s, i) for i, s in enumerate([PASSED] * 4 + [FAILED] * 2)]
    s = classify_tests(single, failing_streak=3)[0]
    assert s.flips == 1 and s.classification == STABLE   # only 2 failures: not "failing" yet either


def test_runs_are_sorted_by_order_not_input_order():
    shuffled = [TestRunRecord("X", f"c{i}", s, order) for i, (s, order) in
                enumerate([(FAILED, 5), (PASSED, 1), (FAILED, 4), (FAILED, 3), (PASSED, 2)])]
    x = classify_tests(shuffled)[0]
    assert x.last_status == FAILED and x.flips == 1          # P P F F F
    assert x.classification == FAILING


def test_flakiness_summary():
    summary = flakiness(history())
    data = summary.to_dict()
    assert (data["tests"], data["flaky"], data["suspected_flaky"], data["failing"], data["stable"]) == (5, 1, 1, 1, 2)
    assert data["flaky_rate"] == 40.0
    assert {t["test_id"] for t in data["flagged"]} == {"A", "B", "C"}
    assert flakiness([]).flaky_rate == 0.0


# ── bug density ───────────────────────────────────────────────────

def test_bug_density_with_samanvaya_statuses():
    defects = [
        {"status": "OPEN", "severity": "critical"},
        {"status": "REOPENED", "severity": "low"},
        {"status": "READY_FOR_RETEST", "severity": "high"},   # fix not confirmed: still open
        {"status": "FIXED", "severity": "high"},
        {"status": "CLOSED", "severity": "medium"},
    ]
    density = bug_density(defects, code_lines=2500)
    assert (density.total, density.open) == (5, 3)
    assert density.density == 2.0                 # 5 per 2.5 KLOC
    assert density.open_density == 1.2
    assert density.weighted_open_density == round((10 + 1 + 5) / 2.5, 2)
    assert bug_density([], code_lines=0).density == 0.0
