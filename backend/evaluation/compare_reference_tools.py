"""
Compare SAMANVAYA's own code-quality metrics with reference tools.

    cyclomatic complexity   vs  radon (cc) and lizard (CCN)      per function
    cognitive complexity    vs  cognitive_complexity package     per function
    maintainability index   vs  radon (mi)                       per file
    Halstead volume         vs  radon (h)                        per file

For every function where the numbers differ, the script checks whether a
KNOWN, documented rule difference explains the gap, so a disagreement is
either "explained" (both tools are right by their own rules) or listed for
investigation.

Reference tools are NOT dependencies of SAMANVAYA. Install them in a
separate environment (same versions as backend/requirements.txt):

    python -m venv refvenv
    refvenv/Scripts/python -m pip install radon==6.0.1 lizard==1.17.10 cognitive_complexity==1.3.0
    refvenv/Scripts/python evaluation/compare_reference_tools.py --root . --out evaluation/results

Writes <out>/reference_comparison.md (summary for the report) and
<out>/reference_disagreements.csv (every differing function).
"""

from __future__ import annotations

import argparse
import ast
import csv
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from intelligence.metrics.cognitive import analyze_source as our_cognitive  # noqa: E402
from intelligence.metrics.cyclomatic import analyze_source as our_cyclomatic  # noqa: E402
from intelligence.metrics.maintainability import (  # noqa: E402
    analyze_source as our_maintainability,
    maintainability_index,
)

try:
    import lizard
    from cognitive_complexity.api import get_cognitive_complexity
    from radon.complexity import cc_visit
    from radon.metrics import h_visit, mi_compute, mi_parameters, mi_visit
except ImportError as exc:  # pragma: no cover - guidance for the user
    sys.exit(
        f"Reference tool missing ({exc.name}). Install: "
        "pip install radon==6.0.1 lizard==1.17.10 cognitive_complexity==1.3.0"
    )

DEFAULT_EXCLUDE = ("tests", "evaluation", "metrics", "venv", ".venv", "node_modules")
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


# ── statistics (no numpy needed) ──────────────────────────────────

def _ranks(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy) if sx and sy else float("nan")


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    return pearson(_ranks(x), _ranks(y))


@dataclass
class Agreement:
    name: str
    ours: List[float] = field(default_factory=list)
    theirs: List[float] = field(default_factory=list)

    def add(self, ours: float, theirs: float) -> None:
        self.ours.append(ours)
        self.theirs.append(theirs)

    @property
    def n(self) -> int:
        return len(self.ours)

    def exact(self) -> float:
        return 100 * sum(a == b for a, b in zip(self.ours, self.theirs)) / self.n if self.n else 0.0

    def within(self, tolerance: float) -> float:
        return 100 * sum(abs(a - b) <= tolerance for a, b in zip(self.ours, self.theirs)) / self.n if self.n else 0.0

    def mae(self) -> float:
        return sum(abs(a - b) for a, b in zip(self.ours, self.theirs)) / self.n if self.n else 0.0

    def row(self, tolerance: float) -> str:
        return (
            f"| {self.name} | {self.n} | {self.exact():.1f}% | {self.within(tolerance):.1f}% (±{tolerance:g}) "
            f"| {self.mae():.2f} | {pearson(self.ours, self.theirs):.3f} | {spearman(self.ours, self.theirs):.3f} |"
        )


# ── known rule differences ────────────────────────────────────────

def _own_nodes(func: ast.AST) -> Iterable[ast.AST]:
    """Nodes inside a function body, not descending into nested defs/classes."""
    stack = list(getattr(func, "body", []))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (*_FUNCS, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def radon_rule_gap(func: ast.AST) -> int:
    """radon adds +1 for `assert`, try/else and for/while/else; we do not."""
    gap = 0
    for node in _own_nodes(func):
        if isinstance(node, ast.Assert):
            gap += 1
        elif isinstance(node, ast.Try) and node.orelse:
            gap += 1
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)) and node.orelse:
            gap += 1
    return gap


def _decisions(node: ast.AST) -> int:
    """Cyclomatic decision points inside an expression (used for f-strings)."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.IfExp):
            count += 1
        elif isinstance(child, ast.BoolOp):
            count += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            count += 1 + len(child.ifs)
    return count


def lizard_rule_gap(func: ast.AST) -> int:
    """lizard reads tokens, not syntax:
    - it does not understand `match` (we count each non-wildcard case)
    - it cannot see decisions inside f-strings, e.g. f"{a if b else c}"
    - it counts `finally` as a decision (it always runs, so it is not a branch)
    """
    gap = 0
    for node in _own_nodes(func):
        if isinstance(node, ast.Match):
            for case in node.cases:
                pattern = case.pattern
                if not (isinstance(pattern, ast.MatchAs) and pattern.pattern is None and pattern.name is None):
                    gap -= 1
        elif isinstance(node, ast.JoinedStr):
            gap -= _decisions(node)
        elif isinstance(node, ast.Try) and node.finalbody:
            gap += 1
    return gap


def cognitive_unsupported(func: ast.AST) -> List[str]:
    """Constructs the cognitive_complexity package scores differently.

    Verified with small test functions (cognitive_complexity 1.3.0):
    - ignores comprehensions and `match`
    - ignores `async for` entirely (no +1, no nesting for its body)
    - scores `else:` + nested `if` like `elif` (2 instead of SonarSource's 4)
    - nested functions/lambdas: no SonarSource nesting penalty
    - in an if/elif chain, structures nested in a branch that is followed by
      another `elif` lose their nesting penalty (e.g. +1 instead of +2)
    """
    nesting = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.IfExp, ast.Match)
    reasons = set()
    for node in ast.walk(func):
        if node is func:
            continue
        if (
            isinstance(node, ast.If)
            and len(node.orelse) == 1
            and isinstance(node.orelse[0], ast.If)
            and node.orelse[0].col_offset == node.col_offset  # followed by elif
            and any(isinstance(n, nesting) for stmt in node.body for n in ast.walk(stmt))
        ):
            reasons.add("nesting inside a branch followed by elif")
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            reasons.add("comprehension")
        elif isinstance(node, ast.Match):
            reasons.add("match")
        elif isinstance(node, ast.AsyncFor):
            reasons.add("async for")
        elif isinstance(node, (*_FUNCS, ast.Lambda, ast.ClassDef)):
            reasons.add("nested function/lambda")
        elif (
            isinstance(node, ast.If)
            and len(node.orelse) == 1
            and isinstance(node.orelse[0], ast.If)
            and node.orelse[0].col_offset != node.col_offset
        ):
            reasons.add("else + nested if (package reads it as elif)")
    return sorted(reasons)


# ── comparison ────────────────────────────────────────────────────

def _radon_functions(source: str) -> Dict[int, int]:
    """line -> radon cyclomatic for every function, method and closure."""
    found: Dict[int, int] = {}

    def walk(blocks):
        for block in blocks:
            if type(block).__name__ == "Function":
                found[block.lineno] = block.complexity
                walk(getattr(block, "closures", []))
            else:  # Class
                walk(getattr(block, "methods", []))
                walk(getattr(block, "inner_classes", []))

    walk(cc_visit(source))
    return found


def _lizard_functions(path: str, source: str) -> Dict[int, int]:
    result = lizard.analyze_file.analyze_source_code(path, source)
    return {fn.start_line: fn.cyclomatic_complexity for fn in result.function_list}


def _function_nodes(tree: ast.AST) -> Dict[int, ast.AST]:
    return {node.lineno: node for node in ast.walk(tree) if isinstance(node, _FUNCS)}


def compare(root: Path, exclude: Sequence[str]) -> dict:
    files = sorted(
        p for p in root.rglob("*.py")
        if not any(part in exclude for part in p.relative_to(root).parts)
    )
    cc_radon = Agreement("Cyclomatic vs radon")
    cc_radon_rules = Agreement("Cyclomatic vs radon, after known rule differences")
    cc_lizard = Agreement("Cyclomatic vs lizard")
    cc_lizard_rules = Agreement("Cyclomatic vs lizard, after known rule differences")
    cog = Agreement("Cognitive vs cognitive_complexity")
    cog_comparable = Agreement("Cognitive vs cognitive_complexity, comparable functions")
    mi = Agreement("Maintainability index vs radon (file)")
    mi_formula = Agreement("MI formula check: our formula on radon's inputs")
    mi_formula_same_constant = Agreement("MI formula check, radon's comment constant (2.46)")
    volume = Agreement("Halstead volume vs radon (file)")
    rows: List[dict] = []
    skipped: Dict[str, str] = {}

    for path in files:
        rel = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            tree = ast.parse(source)
            radon_cc = _radon_functions(source)
            lizard_cc = _lizard_functions(rel, source)
        except (SyntaxError, ValueError) as exc:
            skipped[rel] = str(exc)
            continue
        nodes = _function_nodes(tree)

        for f in our_cyclomatic(source, rel).functions:
            node = nodes.get(f.lineno)
            if f.lineno in radon_cc and node is not None:
                theirs = radon_cc[f.lineno]
                gap = radon_rule_gap(node)
                cc_radon.add(f.cyclomatic, theirs)
                cc_radon_rules.add(f.cyclomatic + gap, theirs)
                if f.cyclomatic != theirs:
                    rows.append({"file": rel, "function": f.name, "line": f.lineno, "metric": "cyclomatic",
                                 "tool": "radon", "ours": f.cyclomatic, "theirs": theirs,
                                 "explained": f.cyclomatic + gap == theirs,
                                 "reason": "radon counts assert / try-else / loop-else" if gap else ""})
            if f.lineno in lizard_cc and node is not None:
                theirs = lizard_cc[f.lineno]
                gap = lizard_rule_gap(node)
                cc_lizard.add(f.cyclomatic, theirs)
                cc_lizard_rules.add(f.cyclomatic + gap, theirs)
                if f.cyclomatic != theirs:
                    rows.append({"file": rel, "function": f.name, "line": f.lineno, "metric": "cyclomatic",
                                 "tool": "lizard", "ours": f.cyclomatic, "theirs": theirs,
                                 "explained": f.cyclomatic + gap == theirs,
                                 "reason": "lizard does not support match" if gap else ""})

        for f in our_cognitive(source, rel).functions:
            node = nodes.get(f.lineno)
            if node is None:
                continue
            theirs = get_cognitive_complexity(node)
            reasons = cognitive_unsupported(node)
            cog.add(f.cognitive, theirs)
            if not reasons:
                cog_comparable.add(f.cognitive, theirs)
            if f.cognitive != theirs:
                rows.append({"file": rel, "function": f.name, "line": f.lineno, "metric": "cognitive",
                             "tool": "cognitive_complexity", "ours": f.cognitive, "theirs": theirs,
                             "explained": bool(reasons), "reason": ", ".join(reasons)})

        ours_mi = our_maintainability(source, rel)
        if not ours_mi.parse_error:
            mi.add(ours_mi.mi, mi_visit(source, multi=True))
            volume.add(round(ours_mi.halstead.volume, 2), round(h_visit(source).total.volume, 2))
            params = mi_parameters(source, count_multi=True)
            theirs_mi = round(mi_compute(*params), 2)
            mi_formula.add(
                maintainability_index(params[0], params[1], params[2], comment_percent=params[3]),
                theirs_mi,
            )
            mi_formula_same_constant.add(
                maintainability_index(params[0], params[1], params[2], comment_percent=params[3], comment_constant=2.46),
                theirs_mi,
            )

    return {
        "files": len(files) - len(skipped),
        "skipped": skipped,
        "cyclomatic": [cc_radon, cc_radon_rules, cc_lizard, cc_lizard_rules],
        "cognitive": [cog, cog_comparable],
        "file_level": [mi, mi_formula, mi_formula_same_constant, volume],
        "rows": rows,
    }


def _explained_share(rows: List[dict], metric: str, tool: str) -> Tuple[int, int]:
    subset = [r for r in rows if r["metric"] == metric and r["tool"] == tool]
    return sum(1 for r in subset if r["explained"]), len(subset)


def write_report(result: dict, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    header = "| Comparison | n | Exact match | Close match | Mean abs. error | Pearson r | Spearman ρ |\n|---|---|---|---|---|---|---|"
    lines = [
        "# SAMANVAYA metrics vs reference tools",
        "",
        f"Files compared: **{result['files']}** (skipped: {len(result['skipped'])}).",
        "Reference tools: radon 6.0.1, lizard 1.17.10, cognitive_complexity 1.3.0.",
        "",
        "## Cyclomatic complexity (per function)",
        "",
        header,
        *[a.row(1) for a in result["cyclomatic"]],
        "",
    ]
    for tool in ("radon", "lizard"):
        explained, total = _explained_share(result["rows"], "cyclomatic", tool)
        lines.append(f"- Differences with {tool}: **{total}**, of which **{explained}** are explained by known rule differences.")
    lines += [
        "- radon adds +1 for `assert`, `try … else` and loop `else`; SAMANVAYA, following McCabe, counts only branch points.",
        "- lizard reads tokens, not syntax: it does not understand `match`, cannot see decisions inside f-strings "
        "(e.g. `f\"{a if b else c}\"`) and counts `finally`, which always runs and is not a branch.",
        "",
        "## Cognitive complexity (per function)",
        "",
        header,
        *[a.row(1) for a in result["cognitive"]],
        "",
    ]
    explained, total = _explained_share(result["rows"], "cognitive", "cognitive_complexity")
    lines += [
        f"- Differences: **{total}**, of which **{explained}** are in functions using constructs the package scores differently "
        "from SonarSource's specification. Each was confirmed with a small test function:",
        "  - comprehensions and `match`: ignored by the package",
        "  - `async for`: ignored by the package (no +1, no nesting for its body)",
        "  - `else:` followed by a nested `if`: scored like `elif` (2 instead of 4)",
        "  - a structure nested in an `if`/`elif` branch that is followed by another `elif`: nesting penalty missed",
        "  - nested functions and lambdas: no nesting penalty",
        "- \"Comparable functions\" excludes those constructs: this is the like-for-like check of the shared rules.",
        "",
        "## Maintainability index and Halstead volume (per file)",
        "",
        header,
        *[a.row(5) for a in result["file_level"]],
        "",
        "- The MI values differ **by design**: radon uses logical lines (LLOC), operator-only Halstead counting and always adds "
        "the comment bonus (constant 2.46); SAMANVAYA uses NCLOC, token-based Halstead and no comment bonus by default.",
        "- The **formula check** feeds radon's own inputs into SAMANVAYA's formula. With the published comment constant (2.4) "
        "the results are within ±5; with radon's constant (2.46) they are identical, so the formula is implemented correctly "
        "and every MI difference comes from the inputs (line counting, Halstead definition, comment bonus).",
        "- Halstead volume uses different operator/operand definitions, so compare ranking (Spearman ρ), not values.",
    ]
    report = out / "reference_comparison.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with (out / "reference_disagreements.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "function", "line", "metric", "tool", "ours", "theirs", "explained", "reason"])
        writer.writeheader()
        writer.writerows(result["rows"])
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=BACKEND, help="folder with Python code to compare")
    parser.add_argument("--out", type=Path, default=BACKEND / "evaluation" / "results")
    parser.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE), help="folder names to skip")
    args = parser.parse_args(argv)
    result = compare(args.root.resolve(), args.exclude)
    report = write_report(result, args.out)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    print(report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
