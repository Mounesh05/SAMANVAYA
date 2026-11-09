"""
Tests for intelligence.metrics.issues, .debt and .project.
"""

import textwrap
from types import SimpleNamespace

import pytest

from intelligence.metrics.cognitive import analyze_source as cognitive_source
from intelligence.metrics.cyclomatic import analyze_source as cyclomatic_source
from intelligence.metrics.debt import format_duration, rating_for, remediation_minutes, technical_debt
from intelligence.metrics.duplication import detect_duplicates
from intelligence.metrics.issues import (
    Issue,
    complexity_issues,
    duplication_issues,
    issue_density,
    issues_from_findings,
)
from intelligence.metrics.project import analyze_paths, analyze_sources


def deep_function(name: str, depth: int) -> str:
    """A function whose cognitive complexity is 1 + 2 + ... + depth."""
    body = "".join("    " * (i + 1) + f"if a > {i}:\n" for i in range(depth))
    return f"def {name}(a):\n{body}" + "    " * (depth + 1) + "return a\n"


def smell(path="a.py", minutes=None, severity="medium", type_="code_smell"):
    return Issue(rule="r", type=type_, severity=severity, path=path, line=1, message="m",
                 remediation_minutes=minutes)


# ── issue generators ──────────────────────────────────────────────

def test_complexity_issue_only_above_limit_with_sonar_remediation():
    src = deep_function("ok", 5) + "\n" + deep_function("bad", 6)   # 15 and 21
    issues = complexity_issues(cognitive=cognitive_source(src, "m.py"))
    assert len(issues) == 1
    issue = issues[0]
    # "ok" spans lines 1-7, a blank line, then "bad" starts on line 9
    assert issue.rule == "cognitive-complexity" and issue.path == "m.py" and issue.line == 9
    assert "bad has cognitive complexity 21" in issue.message
    assert issue.remediation_minutes == 5 + (21 - 15)
    assert issue.severity == "medium"


def test_very_complex_function_is_high_severity():
    issues = complexity_issues(cognitive=cognitive_source(deep_function("worse", 8), "m.py"))  # 36 > 30
    assert issues[0].severity == "high"


def test_cyclomatic_issues_only_when_requested():
    src = "def f(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(12))
    assert complexity_issues(cyclomatic=None) == []
    issues = complexity_issues(cyclomatic=cyclomatic_source(src, "c.py"))
    assert [i.rule for i in issues] == ["cyclomatic-complexity"]
    assert issues[0].remediation_minutes == 5 + (13 - 10)


def test_duplication_issue_per_copy():
    func = textwrap.dedent('''
        def process(order, inventory):
            total = 0
            for item in order.items:
                if item.sku not in inventory:
                    raise ValueError("missing")
                total += item.price * item.quantity
            return total
    ''')
    report = detect_duplicates({"a.py": func, "b.py": func}, min_tokens=20, min_lines=3)
    issues = duplication_issues(report)
    assert len(issues) == 1
    assert issues[0].path == "b.py" and issues[0].remediation_minutes == 10
    assert "a.py:2-8" in issues[0].message


def test_findings_are_converted():
    severity = SimpleNamespace(value="critical")
    findings = [
        SimpleNamespace(file_path="x.py", line_number=3, rule_id="B105", category="security",
                        severity=severity, source_tool="bandit", message="hardcoded password"),
        {"file_path": "y.py", "line_number": 9, "rule_id": "F841", "category": "maintainability",
         "severity": "low", "source_tool": "ruff", "message": "unused variable"},
        {"file_path": "z.py", "rule_id": "E999", "category": "syntax", "severity": "weird"},
    ]
    issues = issues_from_findings(findings)
    assert [(i.rule, i.type, i.severity) for i in issues] == [
        ("bandit:B105", "vulnerability", "critical"),
        ("ruff:F841", "code_smell", "low"),
        ("external:E999", "bug", "medium"),
    ]


# ── density ───────────────────────────────────────────────────────

def test_issue_density_per_kloc_and_weighted():
    issues = [smell("a.py", severity="critical"), smell("a.py", severity="low"), smell("b.py", severity="medium")]
    report = issue_density(issues, {"a.py": 1500, "b.py": 500, "c.py": 1000})
    assert report.count == 3 and report.code_lines == 3000
    assert report.density == 1.0                     # 3 / 3 KLOC
    assert report.weighted_density == round((10 + 1 + 3) / 3, 2)
    by_path = {f.path: f for f in report.files}
    assert by_path["a.py"].density == round(2 / 1.5, 2)
    assert by_path["c.py"].issues == 0 and by_path["c.py"].density == 0.0
    assert report.by_severity["critical"] == 1 and report.by_type["code_smell"] == 3


def test_density_with_no_code_is_zero():
    assert issue_density([smell()], {}).density == 0.0


# ── technical debt ────────────────────────────────────────────────

@pytest.mark.parametrize(
    "ratio, rating",
    [(0, "A"), (5, "A"), (5.01, "B"), (10, "B"), (20, "C"), (50, "D"), (50.1, "E")],
)
def test_rating_grid(ratio, rating):
    assert rating_for(ratio) == rating


def test_debt_ratio_and_rating():
    # 1,000 lines x 30 min = 30,000 min to write; 2,400 min debt = 8% -> B
    issues = [smell(minutes=1200), smell("b.py", minutes=1200)]
    debt = technical_debt(issues, code_lines=1000)
    assert debt.debt_minutes == 2400
    assert debt.ratio == 8.0 and debt.rating == "B"
    assert debt.minutes_to_rating_a == 2400 - 1500
    assert debt.debt == "5d"                         # 2,400 min / 480 min per day


def test_remediation_falls_back_to_severity():
    assert remediation_minutes(smell(severity="critical")) == 30
    assert remediation_minutes(smell(severity="info")) == 0
    assert remediation_minutes(smell(minutes=7, severity="critical")) == 7


def test_only_code_smells_count_toward_debt_by_default():
    issues = [smell(minutes=60), smell(minutes=60, type_="vulnerability"), smell(minutes=60, type_="bug")]
    assert technical_debt(issues, 100).debt_minutes == 60
    assert technical_debt(issues, 100, include_all_types=True).debt_minutes == 180
    assert technical_debt(issues, 100).by_type == {"code_smell": 60, "bug": 60, "vulnerability": 60}


def test_no_code_no_ratio():
    debt = technical_debt([smell(minutes=30)], code_lines=0)
    assert debt.ratio == 0.0 and debt.rating == "A"


@pytest.mark.parametrize(
    "minutes, text",
    [(0, "0min"), (45, "45min"), (60, "1h"), (75, "1h 15min"), (480, "1d"), (555, "1d 1h 15min")],
)
def test_format_duration(minutes, text):
    assert format_duration(minutes) == text


# ── all six metrics together ──────────────────────────────────────

def test_analyze_sources_combines_all_metrics():
    clean = "def add(a, b):\n    return a + b\n"
    sources = {"clean.py": clean, "deep.py": deep_function("deep", 7), "broken.py": "def f(:\n"}
    summary = analyze_sources(sources, findings=[
        {"file_path": "clean.py", "rule_id": "F401", "category": "maintainability",
         "severity": "low", "source_tool": "ruff", "message": "unused import"},
    ])
    data = summary.to_dict()
    assert data["files_analyzed"] == 2
    assert "broken.py" in data["parse_errors"]
    assert data["cognitive_max"] == 28               # 1 + 2 + ... + 7
    assert summary.issues.count == 2                 # deep complexity + ruff finding
    assert summary.debt.debt_minutes == (5 + 28 - 15) + 5
    assert data["rating"] in {"A", "B", "C", "D", "E"}
    files = {f["path"]: f for f in data["files"]}
    assert files["clean.py"]["cyclomatic_max"] == 1


def test_analyze_paths_from_disk(tmp_path):
    (tmp_path / "a.py").write_text(deep_function("deep", 6), encoding="utf-8")
    summary = analyze_paths([tmp_path / "a.py", tmp_path / "gone.py"], root=tmp_path)
    assert summary.to_dict()["files_analyzed"] == 1
    assert "gone.py" in summary.parse_errors
    assert summary.issues.count == 1
