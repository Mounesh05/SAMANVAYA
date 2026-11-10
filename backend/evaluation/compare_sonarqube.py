"""
Compare SAMANVAYA's code-quality summary with SonarQube's measures.

Input: sonar_measures.json from evaluation/sonarqube/fetch_sonar_measures.py.

    per file   code lines, cyclomatic, cognitive, duplicated lines, debt
    project    the same totals plus debt ratio, rating and code smells

Technical debt is compared twice:
    all rules      SonarQube applies hundreds of rules; SAMANVAYA's debt comes
                   from complexity and duplication (plus any analyzer findings
                   fed in), so SonarQube's total is expected to be higher
    shared rules   only the two rules both apply with the same thresholds:
                   cognitive complexity > 15 (SonarQube python:S3776) and
                   duplicated blocks; this is the like-for-like comparison
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from evaluation.stats import TABLE_HEADER, Agreement  # noqa: E402
from intelligence.metrics.project import CodeQualitySummary, analyze_paths  # noqa: E402

DEFAULT_EXCLUDE = ("tests", "evaluation", "metrics", "venv", ".venv", "refvenv", "node_modules")
SHARED_RULES = {
    "cognitive": ("S3776",),                 # python:S3776 Cognitive Complexity of functions should not be too high
    "duplication": ("DuplicatedBlocks",),    # common-py:DuplicatedBlocks
}
OUR_RULES = {"cognitive": "cognitive-complexity", "duplication": "duplicated-block"}


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _shared(rule: Optional[str], kind: str) -> bool:
    return bool(rule) and any(marker in rule for marker in SHARED_RULES[kind])


def compare(root: Path, exclude: Sequence[str], sonar: Dict[str, Any]) -> Dict[str, Any]:
    files = sorted(
        p for p in root.rglob("*.py")
        if not any(part in exclude for part in p.relative_to(root).parts)
    )
    summary: CodeQualitySummary = analyze_paths(files, root=root)
    ours_files = {f.path: f for f in summary.files}
    ours_dup = {f.path: f.duplicated_lines for f in summary.duplication.files}
    sonar_files = sonar.get("files", {})
    common = sorted(set(ours_files) & set(sonar_files))

    rows = {
        "code lines (NCLOC)": Agreement("Code lines (NCLOC) per file"),
        "cyclomatic": Agreement("Cyclomatic complexity per file"),
        "cognitive": Agreement("Cognitive complexity per file"),
        "duplicated lines": Agreement("Duplicated lines per file"),
        "debt shared": Agreement("Debt (minutes) per file, shared rules"),
    }
    sonar_issues = sonar.get("issues", [])
    shared_sonar_debt: Dict[str, int] = {}
    for issue in sonar_issues:
        if _shared(issue.get("rule"), "cognitive") or _shared(issue.get("rule"), "duplication"):
            shared_sonar_debt[issue["path"]] = shared_sonar_debt.get(issue["path"], 0) + int(issue.get("effort_minutes", 0))
    ours_shared_debt: Dict[str, int] = {}
    for issue in summary.issues.issues:
        if issue.rule in OUR_RULES.values():
            ours_shared_debt[issue.path] = ours_shared_debt.get(issue.path, 0) + int(issue.remediation_minutes or 0)

    for path in common:
        theirs = sonar_files[path]["measures"]
        mine = ours_files[path]
        rows["code lines (NCLOC)"].add(mine.code_lines, _num(theirs.get("ncloc")))
        rows["cyclomatic"].add(mine.cyclomatic_total, _num(theirs.get("complexity")))
        rows["cognitive"].add(mine.cognitive_total, _num(theirs.get("cognitive_complexity")))
        rows["duplicated lines"].add(ours_dup.get(path, 0), _num(theirs.get("duplicated_lines")))
        rows["debt shared"].add(ours_shared_debt.get(path, 0), shared_sonar_debt.get(path, 0))

    def count(kind: str, issues: List[Any], ours: bool) -> int:
        if ours:
            return sum(1 for i in issues if i.rule == OUR_RULES[kind])
        return sum(1 for i in issues if _shared(i.get("rule"), kind))

    project = sonar.get("project", {}).get("measures", {})
    ours_data = summary.to_dict()
    project_rows = [
        ("Files", len(ours_files), len(sonar_files)),
        ("Code lines (NCLOC)", ours_data["code_lines"], _num(project.get("ncloc"))),
        ("Cyclomatic complexity (total)", sum(f.cyclomatic_total for f in summary.files), _num(project.get("complexity"))),
        ("Cognitive complexity (total)", sum(f.cognitive_total for f in summary.files), _num(project.get("cognitive_complexity"))),
        ("Duplicated lines", summary.duplication.duplicated_lines, _num(project.get("duplicated_lines"))),
        ("Duplication density %", ours_data["duplication_density"], _num(project.get("duplicated_lines_density"))),
        ("Functions over cognitive 15", count("cognitive", summary.issues.issues, True), count("cognitive", sonar_issues, False)),
        ("Duplicated-block issues", count("duplication", summary.issues.issues, True), count("duplication", sonar_issues, False)),
        ("Debt, shared rules (min)", sum(ours_shared_debt.values()), sum(shared_sonar_debt.values())),
        ("Debt, all rules (min)", summary.debt.debt_minutes, _num(project.get("sqale_index"))),
        ("Debt ratio %", ours_data["debt_ratio"], _num(project.get("sqale_debt_ratio"))),
        ("Maintainability rating", ours_data["rating"], project.get("sqale_rating_letter") or "?"),
        ("Code smells", summary.issues.by_type.get("code_smell", 0), _num(project.get("code_smells"))),
    ]
    return {
        "files_ours": len(ours_files),
        "files_sonar": len(sonar_files),
        "files_common": len(common),
        "only_ours": sorted(set(ours_files) - set(sonar_files)),
        "only_sonar": sorted(set(sonar_files) - set(ours_files)),
        "per_file": list(rows.values()),
        "project": project_rows,
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def write_report(result: Dict[str, Any], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SAMANVAYA vs SonarQube",
        "",
        f"Files: SAMANVAYA {result['files_ours']}, SonarQube {result['files_sonar']}, compared {result['files_common']}.",
    ]
    if result["only_ours"] or result["only_sonar"]:
        lines.append(
            f"Not in both: {len(result['only_ours'])} only in SAMANVAYA, {len(result['only_sonar'])} only in SonarQube "
            "(check that both used the same exclusions)."
        )
    lines += [
        "",
        "## Project totals",
        "",
        "| Measure | SAMANVAYA | SonarQube |",
        "|---|---|---|",
        *[f"| {name} | {_fmt(ours)} | {_fmt(theirs)} |" for name, ours, theirs in result["project"]],
        "",
        "## Per file",
        "",
        TABLE_HEADER,
        *[a.row(5) for a in result["per_file"]],
        "",
        "- **Shared-rule debt** is the like-for-like check: both tools charge 5 min + 1 min per point over 15 for "
        "cognitive complexity, and a fixed cost per duplicated block.",
        "- **All-rule debt** is expected to differ: SonarQube applies hundreds of rules, SAMANVAYA only those it implements "
        "plus the analyzer findings it is given.",
        "- SonarQube counts cyclomatic complexity per file including some constructs SAMANVAYA does not (see "
        "reference_comparison.md for the documented rule differences).",
    ]
    report = out / "sonarqube_comparison.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=BACKEND)
    parser.add_argument("--sonar", type=Path, default=BACKEND / "evaluation" / "results" / "sonar_measures.json")
    parser.add_argument("--out", type=Path, default=BACKEND / "evaluation" / "results")
    parser.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE))
    args = parser.parse_args(argv)
    sonar = json.loads(args.sonar.read_text(encoding="utf-8"))
    report = write_report(compare(args.root.resolve(), args.exclude, sonar), args.out)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
