"""v4 CQ-13 / CQ-14: base-versus-head comparison in the isolated worker.

Observed with fixture A-DIFF01 through the candidate worker: both revisions are
"partial" only because the static worker always skips pytest, coverage and
online dependency advisories, so every comparison was withheld and CQ-13 could
never produce new / existing / resolved findings. Separately, two "available"
sides with different tool sets were still classified, which can mark findings
"resolved" only because a tool did not run on head.
"""

from domain.services.pr_quality_comparison import (classify_findings, comparable_delta, comparable_sides,
                                                   rename_map)
from intelligence.evidence.models import Finding, SeverityEnum

WORKER_SKIPS = ["dependency-advisories-offline", "pytest", "coverage"]


def side(**changes):
    record = {"quality_score": 97, "quality_analysis_status": "partial", "policy_digest": "policy-1",
              "tools_executed": ["ruff", "mypy", "bandit", "lizard", "radon"], "tools_skipped": list(WORKER_SKIPS),
              "quality_dimensions": {"static_security": 95, "testing": None}}
    record.update(changes)
    return record


def finding(path, message, line):
    return Finding(file_path=path, line_number=line, rule_id="RUFF-F401", category="syntax",
                   severity=SeverityEnum.HIGH, source_tool="ruff", message=message)


def test_worker_snapshots_with_the_same_environment_skips_are_comparable():
    assert comparable_sides(side(), side()) is None
    assert comparable_delta(side(), side(quality_score=99)) == {
        "delta": 2, "delta_withheld_reason": None, "policy_digest": "policy-1"}


def test_a_failed_tool_on_either_side_withholds_the_comparison():
    failed = side(tools_skipped=WORKER_SKIPS + ["bandit-source-errors"])
    assert comparable_sides(side(), failed) == "partial_evidence"
    assert comparable_delta(failed, failed)["delta"] is None


def test_different_tools_withhold_the_comparison_even_when_both_are_available():
    base = side(quality_analysis_status="available", tools_skipped=[])
    head = side(quality_analysis_status="available", tools_skipped=[], tools_executed=["ruff", "bandit", "lizard", "radon"])
    assert comparable_sides(base, head) == "tools_differ"
    assert comparable_sides(side(), side(tools_skipped=WORKER_SKIPS[:2])) == "tools_differ"


def test_truncated_or_unscored_sides_are_not_comparable():
    assert comparable_sides(side(), side(), truncated=True) == "partial_evidence"
    assert comparable_sides(side(quality_score=None), side()) == "score_unavailable"


def test_a_diff01_rename_line_move_new_and_resolved():
    base = [finding("old.py", "`math` imported but unused", 1), finding("removed_issue.py", "`os` imported but unused", 1)]
    head = [finding("new.py", "`math` imported but unused", 2), finding("added_issue.py", "`sys` imported but unused", 1)]
    renames = rename_map([{"filename": "new.py", "previous_filename": "old.py", "status": "renamed"}])
    summary, _ = classify_findings(base, head, renames)
    assert summary["counts"] == {"new": 1, "existing": 1, "resolved": 1}
    assert [x["file_path"] for x in summary["new"]] == ["added_issue.py"]
    assert [x["file_path"] for x in summary["resolved"]] == ["removed_issue.py"]
