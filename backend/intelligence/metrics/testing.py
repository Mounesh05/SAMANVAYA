"""
Testing metrics: coverage, diff coverage, pass rate, flaky tests, bug density.

Pure functions over reports that CI tools already produce; nothing here runs
tests. Standard library only.

Inputs
    coverage    Cobertura XML (coverage.py `coverage xml`, pytest-cov,
                vitest/jest `cobertura` reporter, JaCoCo via converters)
                or LCOV (istanbul / nyc / vitest / jest `lcov` reporter)
    diff        unified diff of a pull request (`git diff -U0 base...head`)
    test runs   JUnit XML (pytest --junitxml, vitest, jest-junit, surefire)

Metrics
    line / branch coverage   covered ÷ coverable, from the coverage report
    diff coverage            covered changed lines ÷ coverable changed lines:
                             only lines the PR added or modified that the
                             coverage tool considers executable (same idea as
                             the diff-cover tool). Files missing from the
                             coverage report are listed, not counted.
    pass rate                passed ÷ (run − skipped); errors count as failures
    flaky tests              a test is FLAKY when it both passed and failed on
                             the same commit (same code, different result: the
                             definition used by Google's test infrastructure).
                             Across commits, the flip rate (status changes
                             between consecutive runs) and a Wilson 95%
                             interval for the failure rate flag SUSPECTED flaky
                             tests without over-trusting a handful of runs.
    bug density              defects per 1,000 code lines (NCLOC), total and
                             open, plus a severity-weighted value
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# ── helpers ───────────────────────────────────────────────────────

def to_ranges(lines: Iterable[int]) -> List[Tuple[int, int]]:
    """[1, 2, 3, 7, 9, 10] -> [(1, 3), (7, 7), (9, 10)]"""
    ranges: List[Tuple[int, int]] = []
    for n in sorted(set(lines)):
        if ranges and n == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], n)
        else:
            ranges.append((n, n))
    return ranges


def _percent(part: int, whole: int) -> Optional[float]:
    return round(100 * part / whole, 2) if whole else None


def normalize_path(path: str, strip_prefixes: Sequence[str] = ()) -> str:
    """Use "/" and drop a leading "./", "a/", "b/" or any given prefix."""
    p = path.replace("\\", "/").strip()
    for prefix in strip_prefixes:
        prefix = prefix.replace("\\", "/").rstrip("/") + "/"
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    while p.startswith("./"):
        p = p[2:]
    return str(PurePosixPath(p)) if p else p


# ── coverage ──────────────────────────────────────────────────────

@dataclass
class FileCoverage:
    path: str
    covered: Set[int] = field(default_factory=set)
    uncovered: Set[int] = field(default_factory=set)
    branches_covered: int = 0
    branches_total: int = 0

    @property
    def coverable(self) -> Set[int]:
        return self.covered | self.uncovered

    @property
    def line_rate(self) -> Optional[float]:
        return _percent(len(self.covered), len(self.coverable))

    @property
    def branch_rate(self) -> Optional[float]:
        return _percent(self.branches_covered, self.branches_total)

    def merge_line(self, number: int, hits: int) -> None:
        if hits > 0:
            self.covered.add(number)
            self.uncovered.discard(number)
        elif number not in self.covered:
            self.uncovered.add(number)


@dataclass
class CoverageReport:
    files: Dict[str, FileCoverage] = field(default_factory=dict)
    source_format: str = ""

    def file(self, path: str) -> FileCoverage:
        if path not in self.files:
            self.files[path] = FileCoverage(path)
        return self.files[path]

    @property
    def lines_covered(self) -> int:
        return sum(len(f.covered) for f in self.files.values())

    @property
    def lines_coverable(self) -> int:
        return sum(len(f.coverable) for f in self.files.values())

    @property
    def line_rate(self) -> Optional[float]:
        return _percent(self.lines_covered, self.lines_coverable)

    @property
    def branch_rate(self) -> Optional[float]:
        covered = sum(f.branches_covered for f in self.files.values())
        total = sum(f.branches_total for f in self.files.values())
        return _percent(covered, total)

    def to_dict(self) -> Dict[str, object]:
        return {
            "format": self.source_format,
            "files": len(self.files),
            "lines_covered": self.lines_covered,
            "lines_coverable": self.lines_coverable,
            "line_rate": self.line_rate,
            "branch_rate": self.branch_rate,
        }


_CONDITION = re.compile(r"\((\d+)\s*/\s*(\d+)\)")


def parse_cobertura(xml_text: str, strip_prefixes: Sequence[str] = ()) -> CoverageReport:
    """Cobertura XML -> CoverageReport. Lines of a file split over several
    <class> elements (common for Java) are merged: covered if any hit."""
    root = ET.fromstring(xml_text)
    report = CoverageReport(source_format="cobertura")
    for cls in root.iter("class"):
        filename = cls.get("filename") or cls.get("name") or ""
        fc = report.file(normalize_path(filename, strip_prefixes))
        for line in cls.iter("line"):
            try:
                number = int(line.get("number", "0"))
                hits = int(float(line.get("hits", "0")))
            except ValueError:
                continue
            if number <= 0:
                continue
            fc.merge_line(number, hits)
            if line.get("branch") == "true":
                match = _CONDITION.search(line.get("condition-coverage", ""))
                if match:
                    fc.branches_covered += int(match.group(1))
                    fc.branches_total += int(match.group(2))
    return report


def parse_lcov(text: str, strip_prefixes: Sequence[str] = ()) -> CoverageReport:
    """LCOV tracefile -> CoverageReport (DA = line hits, BRDA = branches)."""
    report = CoverageReport(source_format="lcov")
    current: Optional[FileCoverage] = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("SF:"):
            current = report.file(normalize_path(line[3:], strip_prefixes))
        elif line == "end_of_record":
            current = None
        elif current is None:
            continue
        elif line.startswith("DA:"):
            parts = line[3:].split(",")
            try:
                current.merge_line(int(parts[0]), int(float(parts[1])))
            except (IndexError, ValueError):
                continue
        elif line.startswith("BRDA:"):
            parts = line[5:].split(",")
            if len(parts) == 4:
                current.branches_total += 1
                if parts[3] not in ("-", "0"):
                    current.branches_covered += 1
    return report


def parse_coverage(text: str, strip_prefixes: Sequence[str] = ()) -> CoverageReport:
    """Detect the format (Cobertura XML or LCOV) and parse it."""
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return parse_cobertura(text, strip_prefixes)
    return parse_lcov(text, strip_prefixes)


# ── diff and diff coverage ────────────────────────────────────────

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(diff_text: str) -> Dict[str, Set[int]]:
    """Added or modified line numbers (in the NEW file) per file.

    Deleted files and binary changes have no new lines and are skipped.
    """
    changed: Dict[str, Set[int]] = {}
    current: Optional[str] = None
    new_line = 0
    in_hunk = False
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            current, in_hunk = None, False
        elif raw.startswith("+++ "):
            target = raw[4:].split("\t")[0].strip()
            current = None if target == "/dev/null" else normalize_path(target[2:] if target.startswith("b/") else target)
            in_hunk = False
        elif raw.startswith("--- ") and not in_hunk:
            continue
        elif raw.startswith("@@"):
            match = _HUNK.match(raw)
            in_hunk = bool(match) and current is not None
            if match:
                new_line = int(match.group(1))
        elif in_hunk and current is not None:
            if raw.startswith("+"):
                changed.setdefault(current, set()).add(new_line)
                new_line += 1
            elif raw.startswith(" ") or raw == "":
                new_line += 1
            # "-" lines and "\ No newline at end of file" do not move the new-file counter
    return changed


@dataclass
class FileDiffCoverage:
    path: str
    changed_lines: int
    coverable: int
    covered: int
    uncovered_ranges: List[Tuple[int, int]]

    @property
    def percent(self) -> Optional[float]:
        return _percent(self.covered, self.coverable)

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "changed_lines": self.changed_lines,
            "coverable": self.coverable,
            "covered": self.covered,
            "percent": self.percent,
            "uncovered_ranges": [list(r) for r in self.uncovered_ranges],
        }


@dataclass
class DiffCoverage:
    files: List[FileDiffCoverage] = field(default_factory=list)
    files_without_coverage: List[str] = field(default_factory=list)

    @property
    def coverable(self) -> int:
        return sum(f.coverable for f in self.files)

    @property
    def covered(self) -> int:
        return sum(f.covered for f in self.files)

    @property
    def percent(self) -> Optional[float]:
        """None when the PR changed no executable lines (nothing to cover)."""
        return _percent(self.covered, self.coverable)

    def to_dict(self) -> Dict[str, object]:
        return {
            "percent": self.percent,
            "covered": self.covered,
            "coverable": self.coverable,
            "files": [f.to_dict() for f in self.files],
            "files_without_coverage": list(self.files_without_coverage),
        }


def diff_coverage(
    changed: Mapping[str, Set[int]],
    coverage: CoverageReport,
    source_suffixes: Optional[Sequence[str]] = None,
) -> DiffCoverage:
    """Coverage of the changed lines only.

    `source_suffixes` (e.g. [".py"]) limits which changed files are expected
    in the coverage report; changed source files missing from it are listed
    in `files_without_coverage` (often new files no test imports).
    """
    result = DiffCoverage()
    for path in sorted(changed):
        lines = changed[path]
        fc = coverage.files.get(path)
        if fc is None:
            if source_suffixes is None or any(path.endswith(s) for s in source_suffixes):
                result.files_without_coverage.append(path)
            continue
        coverable = lines & fc.coverable
        covered = lines & fc.covered
        if not coverable:
            continue  # only comments, blank lines or declarations changed
        result.files.append(FileDiffCoverage(
            path=path,
            changed_lines=len(lines),
            coverable=len(coverable),
            covered=len(covered),
            uncovered_ranges=to_ranges(coverable - covered),
        ))
    return result


# ── test results ──────────────────────────────────────────────────

PASSED, FAILED, SKIPPED = "passed", "failed", "skipped"


@dataclass(frozen=True)
class TestCaseResult:
    __test__ = False  # not a pytest test class

    test_id: str        # "classname::name"
    status: str         # passed | failed | skipped  (errors count as failed)
    duration_seconds: float = 0.0


def parse_junit(xml_text: str) -> List[TestCaseResult]:
    """JUnit XML -> one result per <testcase>."""
    root = ET.fromstring(xml_text)
    results: List[TestCaseResult] = []
    for case in root.iter("testcase"):
        classname = case.get("classname") or case.get("file") or ""
        name = case.get("name") or ""
        test_id = f"{classname}::{name}" if classname else name
        if case.find("failure") is not None or case.find("error") is not None:
            status = FAILED
        elif case.find("skipped") is not None:
            status = SKIPPED
        else:
            status = PASSED
        try:
            duration = float(case.get("time") or 0)
        except ValueError:
            duration = 0.0
        results.append(TestCaseResult(test_id, status, duration))
    return results


@dataclass
class PassRate:
    run: int
    passed: int
    failed: int
    skipped: int

    @property
    def percent(self) -> Optional[float]:
        """passed ÷ (run − skipped)."""
        return _percent(self.passed, self.run - self.skipped)

    def to_dict(self) -> Dict[str, object]:
        return {"run": self.run, "passed": self.passed, "failed": self.failed,
                "skipped": self.skipped, "percent": self.percent}


def pass_rate(results: Iterable[TestCaseResult]) -> PassRate:
    counts = {PASSED: 0, FAILED: 0, SKIPPED: 0}
    total = 0
    for r in results:
        total += 1
        counts[r.status] = counts.get(r.status, 0) + 1
    return PassRate(total, counts[PASSED], counts[FAILED], counts[SKIPPED])


# ── flaky tests ───────────────────────────────────────────────────

def wilson_interval(failures: int, runs: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson score interval for a failure rate (as fractions 0-1).

    Unlike failures / runs, it stays honest with few runs: 1 failure in 2 runs
    gives (0.09, 0.91), "we don't know yet", not "50%".
    """
    if runs <= 0:
        return 0.0, 1.0
    p = failures / runs
    denom = 1 + z * z / runs
    centre = (p + z * z / (2 * runs)) / denom
    half = z * math.sqrt(p * (1 - p) / runs + z * z / (4 * runs * runs)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass(frozen=True)
class TestRunRecord:
    """One execution of one test, in chronological order."""

    __test__ = False

    test_id: str
    commit: str
    status: str          # passed | failed | skipped
    order: float = 0.0   # timestamp or run number; used to sort runs


FLAKY = "flaky"                      # passed and failed on the same commit
SUSPECTED_FLAKY = "suspected_flaky"  # keeps flipping across commits
FAILING = "failing"                  # failed in every recent run
STABLE = "stable"


@dataclass
class TestStability:
    __test__ = False

    test_id: str
    runs: int
    failures: int
    flips: int
    same_commit_flips: int
    last_status: str
    classification: str
    failure_rate_low: float
    failure_rate_high: float

    @property
    def failure_rate(self) -> float:
        return round(100 * self.failures / self.runs, 2) if self.runs else 0.0

    @property
    def flip_rate(self) -> float:
        """Status changes between consecutive runs ÷ (runs − 1)."""
        return round(100 * self.flips / (self.runs - 1), 2) if self.runs > 1 else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "test_id": self.test_id,
            "runs": self.runs,
            "failures": self.failures,
            "failure_rate": self.failure_rate,
            "failure_rate_95": [round(100 * self.failure_rate_low, 2), round(100 * self.failure_rate_high, 2)],
            "flips": self.flips,
            "flip_rate": self.flip_rate,
            "same_commit_flips": self.same_commit_flips,
            "last_status": self.last_status,
            "classification": self.classification,
        }


def classify_tests(
    records: Iterable[TestRunRecord],
    min_runs: int = 5,
    suspect_flip_rate: float = 0.2,
    failing_streak: int = 3,
) -> List[TestStability]:
    """Classify every test from its run history (skipped runs ignored).
    Checked in this order:

    flaky            passed and failed on at least one same commit
    failing          the last `failing_streak` runs all failed: currently
                     broken, which is a regression to fix, not flakiness
    suspected_flaky  >= min_runs runs, at least 2 flips (back AND forth; one
                     pass->fail change is a state change, not flakiness),
                     flip rate >= suspect_flip_rate, and the failure-rate
                     interval excludes both 0% and 100%
    stable           everything else
    """
    history: Dict[str, List[TestRunRecord]] = {}
    for record in records:
        if record.status in (PASSED, FAILED):
            history.setdefault(record.test_id, []).append(record)

    out: List[TestStability] = []
    for test_id in sorted(history):
        runs = sorted(history[test_id], key=lambda r: r.order)
        statuses = [r.status for r in runs]
        failures = statuses.count(FAILED)
        flips = sum(1 for a, b in zip(statuses, statuses[1:]) if a != b)
        by_commit: Dict[str, Set[str]] = {}
        for r in runs:
            by_commit.setdefault(r.commit, set()).add(r.status)
        same_commit = sum(1 for s in by_commit.values() if s == {PASSED, FAILED})
        low, high = wilson_interval(failures, len(runs))

        if same_commit:
            label = FLAKY
        elif len(runs) >= failing_streak and all(s == FAILED for s in statuses[-failing_streak:]):
            label = FAILING
        elif (
            len(runs) >= min_runs
            and flips >= 2
            and flips / (len(runs) - 1) >= suspect_flip_rate
            and low > 0.0
            and high < 1.0
        ):
            label = SUSPECTED_FLAKY
        else:
            label = STABLE
        out.append(TestStability(test_id, len(runs), failures, flips, same_commit,
                                 statuses[-1], label, low, high))
    return out


@dataclass
class FlakinessSummary:
    tests: List[TestStability]

    def _count(self, label: str) -> int:
        return sum(1 for t in self.tests if t.classification == label)

    @property
    def flaky_rate(self) -> float:
        """% of tests (with run history) that are flaky or suspected flaky."""
        if not self.tests:
            return 0.0
        return round(100 * (self._count(FLAKY) + self._count(SUSPECTED_FLAKY)) / len(self.tests), 2)

    def to_dict(self) -> Dict[str, object]:
        return {
            "tests": len(self.tests),
            "flaky": self._count(FLAKY),
            "suspected_flaky": self._count(SUSPECTED_FLAKY),
            "failing": self._count(FAILING),
            "stable": self._count(STABLE),
            "flaky_rate": self.flaky_rate,
            "flagged": [t.to_dict() for t in self.tests if t.classification != STABLE],
        }


def flakiness(records: Iterable[TestRunRecord], **kwargs) -> FlakinessSummary:
    return FlakinessSummary(classify_tests(records, **kwargs))


# ── bug density ───────────────────────────────────────────────────

BUG_SEVERITY_WEIGHTS = {"critical": 10, "high": 5, "medium": 3, "low": 1}
# SAMANVAYA's DefectStatus: OPEN, ASSIGNED, IN_PROGRESS, FIXED, READY_FOR_RETEST,
# CLOSED, REOPENED. READY_FOR_RETEST stays open: the fix is not confirmed yet.
CLOSED_STATUSES = {"closed", "resolved", "fixed", "done", "verified", "rejected", "duplicate", "wont_fix"}


@dataclass
class BugDensity:
    code_lines: int
    total: int
    open: int
    weighted_open: int

    def _per_kloc(self, value: int) -> float:
        return round(value / (self.code_lines / 1000), 2) if self.code_lines else 0.0

    @property
    def density(self) -> float:
        """All defects per 1,000 code lines."""
        return self._per_kloc(self.total)

    @property
    def open_density(self) -> float:
        return self._per_kloc(self.open)

    @property
    def weighted_open_density(self) -> float:
        return self._per_kloc(self.weighted_open)

    def to_dict(self) -> Dict[str, object]:
        return {
            "code_lines": self.code_lines,
            "defects": self.total,
            "open_defects": self.open,
            "density": self.density,
            "open_density": self.open_density,
            "weighted_open_density": self.weighted_open_density,
        }


def bug_density(defects: Iterable[Mapping[str, object]], code_lines: int) -> BugDensity:
    """Defect records (dicts with `status`, `severity`) per 1,000 code lines."""
    total = open_ = weighted = 0
    for d in defects:
        total += 1
        status = str(d.get("status", "open")).lower()
        if status not in CLOSED_STATUSES:
            open_ += 1
            weighted += BUG_SEVERITY_WEIGHTS.get(str(d.get("severity", "medium")).lower(), 3)
    return BugDensity(code_lines=code_lines, total=total, open=open_, weighted_open=weighted)
