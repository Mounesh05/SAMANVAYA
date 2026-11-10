"""
Compare SAMANVAYA's duplication detection with jscpd and/or SonarQube.

Produce the reference reports first (see evaluation/README.md):
    --jscpd  path to jscpd-report.json      (npx jscpd ... --reporters json)
    --sonar  path to sonar_measures.json    (evaluation/sonarqube/fetch_sonar_measures.py)

SAMANVAYA runs twice on the same files with the same thresholds:
    exact       type-1 clones only, like jscpd and SonarQube (like-for-like)
    normalized  also renamed copies (type 2): SAMANVAYA's default

For each reference tool the report gives:
    - line-level agreement on WHICH lines are duplicated
      (precision, recall, F1, Jaccard; the reference tool is the baseline)
    - per-file agreement on how many lines are duplicated
    - clone-level recall: share of the tool's clone pairs we also report
      (both copies overlap one of our clone pairs)
Duplication percentages are not compared directly: each tool divides by a
different line count. Comparing the duplicated lines themselves avoids that.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePath
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from evaluation.stats import (  # noqa: E402
    OVERLAP_HEADER,
    TABLE_HEADER,
    Agreement,
    LineOverlap,
    LineSet,
    by_file,
    lines_from_ranges,
)
from intelligence.metrics.duplication import (  # noqa: E402
    DEFAULT_MIN_LINES,
    DEFAULT_MIN_TOKENS,
    DuplicationReport,
    analyze_files,
)

DEFAULT_EXCLUDE = ("tests", "evaluation", "metrics", "venv", ".venv", "refvenv", "node_modules")

Range = Tuple[str, int, int]          # (path, start line, end line)
ClonePair = Tuple[Range, Range]


# ── reference reports ─────────────────────────────────────────────

def _relative(path: str, root: Path) -> str:
    """Report paths may be absolute or relative, with / or \\; make them root-relative."""
    p = PurePath(path.replace("\\", "/"))
    try:
        return Path(p).resolve().relative_to(root.resolve()).as_posix() if p.is_absolute() else p.as_posix()
    except ValueError:
        return p.as_posix()


def _line(location: dict, key: str, loc_key: str) -> int:
    if isinstance(location.get(key), int):
        return location[key]
    loc = location.get(loc_key) or {}
    return int(loc.get("line", 0))


def load_jscpd(report_path: Path, root: Path) -> List[ClonePair]:
    """Clone pairs from a jscpd JSON report (duplicates[].firstFile / secondFile)."""
    data = json.loads(report_path.read_text(encoding="utf-8"))
    pairs: List[ClonePair] = []
    for dup in data.get("duplicates", []):
        sides = []
        for side in ("firstFile", "secondFile"):
            f = dup.get(side) or {}
            start = _line(f, "start", "startLoc")
            end = _line(f, "end", "endLoc")
            sides.append((_relative(f.get("name", ""), root), start, max(start, end)))
        pairs.append((sides[0], sides[1]))
    return pairs


def load_sonar(measures_path: Path) -> Tuple[List[ClonePair], Dict[str, int]]:
    """Clone pairs and per-file duplicated-line counts from fetch_sonar_measures.py output."""
    data = json.loads(measures_path.read_text(encoding="utf-8"))
    pairs: List[ClonePair] = []
    counts: Dict[str, int] = {}
    for path, info in data.get("files", {}).items():
        counts[path] = int(float(info.get("measures", {}).get("duplicated_lines", 0)))
    for group in data.get("duplications", []):
        blocks = [(b["path"], int(b["start"]), int(b["end"])) for b in group]
        for other in blocks[1:]:
            pairs.append((blocks[0], other))
    return pairs, counts


# ── comparison ────────────────────────────────────────────────────

def our_pairs(report: DuplicationReport) -> List[ClonePair]:
    return [
        ((c.original.path, c.original.start_line, c.original.end_line),
         (c.copy.path, c.copy.start_line, c.copy.end_line))
        for c in report.clones
    ]


def _overlaps(a: Range, b: Range) -> bool:
    return a[0] == b[0] and a[1] <= b[2] and b[1] <= a[2]


def clone_recall(ours: Sequence[ClonePair], theirs: Sequence[ClonePair]) -> float:
    """Share of their clone pairs matched by one of ours (both sides overlap, in either order)."""
    if not theirs:
        return 100.0
    found = 0
    for t1, t2 in theirs:
        if any((_overlaps(t1, o1) and _overlaps(t2, o2)) or (_overlaps(t1, o2) and _overlaps(t2, o1)) for o1, o2 in ours):
            found += 1
    return 100 * found / len(theirs)


def pair_lines(pairs: Iterable[ClonePair]) -> LineSet:
    return lines_from_ranges(side for pair in pairs for side in pair)


def restrict(lines: LineSet, allowed: Set[str]) -> LineSet:
    return {(p, n) for p, n in lines if p in allowed}


def compare(
    root: Path,
    exclude: Sequence[str],
    jscpd: Optional[Path],
    sonar: Optional[Path],
    min_tokens: int,
    min_lines: int,
) -> dict:
    files = sorted(
        p for p in root.rglob("*.py")
        if not any(part in exclude for part in p.relative_to(root).parts)
    )
    allowed = {p.relative_to(root).as_posix() for p in files}
    exact = analyze_files(files, root=root, min_tokens=min_tokens, min_lines=min_lines, normalize=False)
    normalized = analyze_files(files, root=root, min_tokens=min_tokens, min_lines=min_lines, normalize=True)
    ours = {"exact": (our_pairs(exact), exact), "normalized": (our_pairs(normalized), normalized)}

    references: Dict[str, Tuple[List[ClonePair], Optional[Dict[str, int]]]] = {}
    if jscpd:
        references["jscpd"] = (load_jscpd(jscpd, root), None)
    if sonar:
        references["SonarQube"] = load_sonar(sonar)

    sections = []
    for tool, (their_pairs, their_counts) in references.items():
        their_pairs = [p for p in their_pairs if p[0][0] in allowed and p[1][0] in allowed]
        their_lines = restrict(pair_lines(their_pairs), allowed)
        overlaps, per_file, recalls = [], [], []
        for mode, (pairs, report) in ours.items():
            mine = pair_lines(pairs)
            overlaps.append(LineOverlap(f"SAMANVAYA {mode} vs {tool}", mine, their_lines))
            counts = their_counts if their_counts is not None else by_file(their_lines)
            mine_counts = by_file(mine)
            agreement = Agreement(f"Duplicated lines per file, {mode} vs {tool}")
            for path in sorted(allowed):
                agreement.add(mine_counts.get(path, 0), counts.get(path, 0))
            per_file.append(agreement)
            recalls.append((mode, clone_recall(pairs, their_pairs), len(their_pairs), len(pairs)))
        sections.append({"tool": tool, "overlaps": overlaps, "per_file": per_file, "recalls": recalls})

    return {
        "files": len(files),
        "min_tokens": min_tokens,
        "min_lines": min_lines,
        "ours": {mode: (len(pairs), report.duplicated_lines, report.density) for mode, (pairs, report) in ours.items()},
        "sections": sections,
    }


def write_report(result: dict, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SAMANVAYA duplication vs reference tools",
        "",
        f"Files compared: **{result['files']}**. Thresholds: {result['min_tokens']} tokens, {result['min_lines']} lines.",
        "",
        "| SAMANVAYA mode | Clone pairs | Duplicated lines | Density (NCLOC) |",
        "|---|---|---|---|",
        *[f"| {mode} | {n} | {lines_} | {density}% |" for mode, (n, lines_, density) in result["ours"].items()],
        "",
    ]
    if not result["sections"]:
        lines.append("No reference report given: pass --jscpd and/or --sonar.")
    for section in result["sections"]:
        lines += [
            f"## {section['tool']}",
            "",
            "Which lines are duplicated (the reference tool is the baseline):",
            "",
            OVERLAP_HEADER,
            *[o.row() for o in section["overlaps"]],
            "",
            TABLE_HEADER,
            *[a.row(5) for a in section["per_file"]],
            "",
            *[
                f"- {mode}: we also report **{recall:.1f}%** of {section['tool']}'s {theirs} clone pairs "
                f"(we report {mine} pairs)."
                for mode, recall, theirs, mine in section["recalls"]
            ],
            "- Lines flagged only by SAMANVAYA in normalized mode are renamed copies (type-2 clones), "
            "which exact-match tools do not look for.",
            "",
        ]
    report = out / "duplication_comparison.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=BACKEND)
    parser.add_argument("--out", type=Path, default=BACKEND / "evaluation" / "results")
    parser.add_argument("--jscpd", type=Path, help="jscpd-report.json")
    parser.add_argument("--sonar", type=Path, help="sonar_measures.json")
    parser.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE))
    parser.add_argument("--min-tokens", type=int, default=DEFAULT_MIN_TOKENS)
    parser.add_argument("--min-lines", type=int, default=DEFAULT_MIN_LINES)
    args = parser.parse_args(argv)
    result = compare(args.root.resolve(), args.exclude, args.jscpd, args.sonar, args.min_tokens, args.min_lines)
    report = write_report(result, args.out)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
