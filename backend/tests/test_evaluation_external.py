"""
Tests for the external-tool comparison scripts in backend/evaluation, using
sample reports in jscpd's and SonarQube's documented formats.
"""

import json
import math
import textwrap

import pytest

from evaluation.compare_duplication import clone_recall, compare as compare_dup, load_jscpd, write_report as write_dup
from evaluation.compare_sonarqube import compare as compare_sonar, write_report as write_sonar
from evaluation.sonarqube.fetch_sonar_measures import effort_minutes, fetch, rating_letter
from evaluation.stats import Agreement, LineOverlap, pearson, spearman

FUNC = textwrap.dedent('''
    def process_order(order, inventory):
        total = 0
        for item in order.items:
            if item.sku not in inventory:
                raise ValueError("missing sku")
            stock = inventory[item.sku]
            if stock.quantity < item.quantity:
                raise ValueError("insufficient stock")
            stock.quantity -= item.quantity
            line_total = item.price * item.quantity
            if item.discount:
                line_total -= line_total * item.discount / 100
            total += line_total
        order.total = round(total, 2)
        order.status = "processed"
        return order.total
''')  # lines 2-17
RENAMED = (FUNC.replace("process_order", "handle").replace("inventory", "stock_map")
           .replace("item", "line").replace("total", "amount"))


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "backend"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text(FUNC, encoding="utf-8")
    (root / "pkg" / "b.py").write_text(FUNC, encoding="utf-8")
    (root / "pkg" / "c.py").write_text(RENAMED, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text(FUNC, encoding="utf-8")  # excluded
    return root


# ── stats ─────────────────────────────────────────────────────────

def test_correlations():
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [10, 20, 20, 40]) == pytest.approx(pearson([1, 2, 3, 4], [1, 2.5, 2.5, 4]))
    assert math.isnan(pearson([1], [1]))


def test_agreement_and_line_overlap():
    a = Agreement("x")
    for ours, theirs in [(1, 1), (2, 3), (5, 5)]:
        a.add(ours, theirs)
    assert round(a.exact(), 1) == 66.7 and a.within(1) == 100.0 and a.mae() == pytest.approx(1 / 3)
    overlap = LineOverlap("o", {("f", 1), ("f", 2), ("f", 3)}, {("f", 2), ("f", 3), ("f", 4), ("f", 5)})
    assert overlap.both == 2
    assert overlap.precision == pytest.approx(200 / 3) and overlap.recall == 50.0
    assert overlap.jaccard == 40.0


# ── jscpd ─────────────────────────────────────────────────────────

def test_load_jscpd_handles_absolute_paths_and_loc_objects(repo, tmp_path):
    report = tmp_path / "jscpd-report.json"
    report.write_text(json.dumps({"duplicates": [
        {"firstFile": {"name": str(repo / "pkg" / "a.py"), "start": 2, "end": 17},
         "secondFile": {"name": "pkg\\b.py", "startLoc": {"line": 2}, "endLoc": {"line": 17}}},
    ]}), encoding="utf-8")
    assert load_jscpd(report, repo) == [(("pkg/a.py", 2, 17), ("pkg/b.py", 2, 17))]


def test_clone_recall_matches_pairs_in_either_order():
    ours = [(("a", 1, 10), ("b", 1, 10))]
    assert clone_recall(ours, [(("b", 3, 8), ("a", 2, 9))]) == 100.0
    assert clone_recall(ours, [(("a", 1, 10), ("c", 1, 10))]) == 0.0
    assert clone_recall(ours, []) == 100.0


def test_duplication_comparison_against_jscpd(repo, tmp_path):
    report = tmp_path / "jscpd-report.json"
    report.write_text(json.dumps({"duplicates": [
        {"firstFile": {"name": "pkg/a.py", "start": 2, "end": 17}, "secondFile": {"name": "pkg/b.py", "start": 2, "end": 17}},
        {"firstFile": {"name": "pkg/a.py", "start": 2, "end": 17}, "secondFile": {"name": "tests/test_x.py", "start": 2, "end": 17}},
    ]}), encoding="utf-8")
    result = compare_dup(repo, ("tests",), jscpd=report, sonar=None, min_tokens=100, min_lines=10)
    section = result["sections"][0]
    exact, normalized = section["overlaps"]
    assert exact.precision == 100.0 and exact.recall == 100.0          # same exact copy found
    assert normalized.recall == 100.0 and normalized.precision < 100.0  # plus the renamed copy in c.py
    assert {mode: recall for mode, recall, _, _ in section["recalls"]} == {"exact": 100.0, "normalized": 100.0}
    assert section["recalls"][0][2] == 1        # the pair touching tests/ is excluded
    text = write_dup(result, tmp_path / "out").read_text(encoding="utf-8")
    assert "## jscpd" in text and "renamed copies" in text


# ── SonarQube fetch ───────────────────────────────────────────────

@pytest.mark.parametrize("text, minutes", [("5min", 5), ("1h 5min", 65), ("2d", 960), ("1d 2h", 600), (None, 0), ("", 0)])
def test_effort_minutes(text, minutes):
    assert effort_minutes(text) == minutes


def test_rating_letter():
    assert [rating_letter(v) for v in ("1.0", "3.0", 5, "x", None)] == ["A", "C", "E", None, None]


def fake_sonar(project="p"):
    files = [
        {"key": f"{project}:pkg/a.py", "path": "pkg/a.py",
         "measures": [{"metric": "ncloc", "value": "16"}, {"metric": "duplicated_lines", "value": "16"}]},
        {"key": f"{project}:pkg/b.py", "path": "pkg/b.py",
         "measures": [{"metric": "ncloc", "value": "16"}, {"metric": "duplicated_lines", "value": "16"}]},
        {"key": f"{project}:pkg/c.py", "path": "pkg/c.py",
         "measures": [{"metric": "ncloc", "value": "16"}, {"metric": "duplicated_lines", "value": "0"}]},
    ]
    dup = {"duplications": [{"blocks": [{"from": 2, "size": 16, "_ref": "1"}, {"from": 2, "size": 16, "_ref": "2"}]}],
           "files": {"1": {"key": f"{project}:pkg/a.py"}, "2": {"key": f"{project}:pkg/b.py"}}}
    issues = [
        {"rule": "common-py:DuplicatedBlocks", "component": f"{project}:pkg/b.py", "line": 2, "effort": "10min", "type": "CODE_SMELL"},
        {"rule": "python:S1192", "component": f"{project}:pkg/a.py", "line": 5, "effort": "1h", "type": "CODE_SMELL"},
    ]
    calls = []

    def get(path, params):
        calls.append((path, dict(params)))
        if path == "/api/measures/component":
            return {"component": {"measures": [
                {"metric": "ncloc", "value": "48"}, {"metric": "sqale_index", "value": "70"},
                {"metric": "sqale_debt_ratio", "value": "4.9"}, {"metric": "sqale_rating", "value": "1.0"},
                {"metric": "duplicated_lines", "value": "32"}, {"metric": "code_smells", "value": "2"},
            ]}}
        if path == "/api/measures/component_tree":   # honours page size, like the real API
            page, size = params["p"], params["ps"]
            return {"components": files[(page - 1) * size: page * size],
                    "paging": {"pageIndex": page, "pageSize": size, "total": len(files)}}
        if path == "/api/duplications/show":
            return dup
        if path == "/api/issues/search":
            return {"issues": issues, "paging": {"total": 2}}
        raise AssertionError(path)

    return get, calls


def test_fetch_normalizes_sonarqube_api(monkeypatch):
    import evaluation.sonarqube.fetch_sonar_measures as fetcher
    monkeypatch.setattr(fetcher, "PAGE_SIZE", 2)
    get, calls = fake_sonar()
    data = fetch(get, "p")
    assert set(data["files"]) == {"pkg/a.py", "pkg/b.py", "pkg/c.py"}
    assert data["project"]["measures"]["sqale_rating_letter"] == "A"
    # the same group is shown for a.py and b.py; it must be stored once
    assert data["duplications"] == [[{"path": "pkg/a.py", "start": 2, "end": 17}, {"path": "pkg/b.py", "start": 2, "end": 17}]]
    assert [(i["rule"], i["path"], i["effort_minutes"]) for i in data["issues"]] == [
        ("common-py:DuplicatedBlocks", "pkg/b.py", 10), ("python:S1192", "pkg/a.py", 60)]
    assert sum(1 for path, _ in calls if path == "/api/duplications/show") == 2   # c.py has no duplicates
    assert "token" not in json.dumps(data).lower()


# ── SonarQube comparison ──────────────────────────────────────────

def test_sonarqube_comparison(repo, tmp_path):
    get, _ = fake_sonar()
    sonar = fetch(get, "p")
    result = compare_sonar(repo, ("tests",), sonar)
    assert result["files_common"] == 3 and result["only_ours"] == [] and result["only_sonar"] == []
    project = {name: (ours, theirs) for name, ours, theirs in result["project"]}
    assert project["Duplicated-block issues"] == (2, 1)            # we also flag the renamed copy
    assert project["Debt, shared rules (min)"] == (20, 10)         # 10 min per duplicated block in both tools
    assert project["Maintainability rating"][1] == "A"
    per_file = {a.name: a for a in result["per_file"]}
    assert per_file["Code lines (NCLOC) per file"].exact() == 100.0  # 16 code lines in every file
    text = write_sonar(result, tmp_path / "out").read_text(encoding="utf-8")
    assert "# SAMANVAYA vs SonarQube" in text and "Shared-rule debt" in text
