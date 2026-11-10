"""
Bridge from SAMANVAYA's own code-quality metrics (intelligence/metrics) to
the CodeQualityEvidence package that the QualityEngine, RiskEngine and AI
agents read.

What it does for the analyzed files:
    - fills evidence.metrics with all six metrics
      (cyclomatic, cognitive, duplication, maintainability index,
       issues per 1,000 lines, technical debt + A-E rating)
    - replaces the complexity and duplication numbers produced by the older
      tool-based detectors, so every line-based value uses one NCLOC
      definition (the evidence merger divides duplicated lines by
      complexity.lines_of_code)
    - counts the analyzers' findings (ruff, bandit, secrets...) as issues

Safety: only files that resolve to a location INSIDE the repository are
read. Paths that escape it ("../x.py", absolute paths elsewhere) and missing
files are skipped and listed in metrics.files_rejected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from intelligence.evidence.models import (
    CodeMetricsEvidence,
    CodeQualityEvidence,
    DuplicationEvidence,
)
from intelligence.metrics.cognitive import MODERATE_MAX as COGNITIVE_LIMIT
from intelligence.metrics.cyclomatic import LOW_MAX as CYCLOMATIC_LIMIT, MODERATE_MAX as CYCLOMATIC_CRITICAL
from intelligence.metrics.project import CodeQualitySummary, analyze_paths

SUPPORTED_SUFFIXES = {".py"}
MAX_LISTED_FUNCTIONS = 50


def resolve_inside(files: Iterable[str], repo_path: str) -> Tuple[List[Path], List[str]]:
    """Split files into those inside the repository and rejected ones."""
    root = Path(repo_path).resolve()
    inside: List[Path] = []
    rejected: List[str] = []
    for f in files:
        try:
            candidate = (root / f).resolve()
        except (OSError, RuntimeError, ValueError):
            rejected.append(str(f))
            continue
        if root in candidate.parents and candidate.is_file():
            inside.append(candidate)
        else:
            rejected.append(str(f))
    return inside, rejected


def _unique_findings(evidence: CodeQualityEvidence) -> List[Any]:
    seen = set()
    unique = []
    for finding in list(evidence.static_findings) + list(evidence.security.findings):
        if finding.id not in seen:
            seen.add(finding.id)
            unique.append(finding)
    return unique


def build_code_metrics(
    files: Sequence[str],
    repo_path: str,
    findings: Iterable[Any] = (),
) -> Tuple[Optional[CodeMetricsEvidence], Optional[CodeQualitySummary]]:
    """Run the six metrics on the supported files; (None, None) if there are none."""
    supported = [f for f in files if Path(f).suffix in SUPPORTED_SUFFIXES]
    if not supported:
        return None, None
    inside, rejected = resolve_inside(supported, repo_path)
    if not inside:
        return CodeMetricsEvidence(files_rejected=rejected), None

    summary = analyze_paths(inside, root=Path(repo_path).resolve(), findings=findings)
    rejected += sorted(summary.parse_errors)

    function_lines = sum(f.code_lines for f in summary.functions)
    hard_lines = sum(f.code_lines for f in summary.functions if f.cognitive > COGNITIVE_LIMIT)
    hot = sorted(
        (f for f in summary.functions if f.cognitive > COGNITIVE_LIMIT),
        key=lambda f: f.cognitive,
        reverse=True,
    )
    data = summary.to_dict()
    metrics = CodeMetricsEvidence(
        files_measured=data["files_analyzed"],
        files_rejected=rejected,
        code_lines=data["code_lines"],
        function_count=data["function_count"],
        cyclomatic_average=data["cyclomatic_average"],
        cyclomatic_max=data["cyclomatic_max"],
        cognitive_average=data["cognitive_average"],
        cognitive_max=data["cognitive_max"],
        cognitive_limit=COGNITIVE_LIMIT,
        high_cognitive_functions=[
            {
                "function": f.name,
                "file": f.path,
                "line": f.lineno,
                "cognitive": f.cognitive,
                "cyclomatic": f.cyclomatic,
                "maintainability": f.maintainability,
            }
            for f in hot[:MAX_LISTED_FUNCTIONS]
        ],
        hard_to_read_code_share=round(100 * hard_lines / function_lines, 2) if function_lines else 0.0,
        maintainability_index=data["maintainability"],
        average_function_maintainability=data["average_function_maintainability"],
        duplication_density=data["duplication_density"],
        duplicate_blocks=len(summary.duplication.clones) if summary.duplication else 0,
        issue_count=summary.issues.count if summary.issues else 0,
        issue_density=data["issue_density"],
        weighted_issue_density=data["weighted_issue_density"],
        technical_debt_minutes=summary.debt.debt_minutes if summary.debt else 0,
        technical_debt=data["technical_debt"],
        debt_ratio=data["debt_ratio"],
        maintainability_rating=data["rating"],
    )
    return metrics, summary


def apply_code_metrics(evidence: CodeQualityEvidence, files: Sequence[str], repo_path: str) -> None:
    """Attach the six metrics to `evidence` (mutates it). No-op for unsupported files."""
    metrics, summary = build_code_metrics(files, repo_path, findings=_unique_findings(evidence))
    if metrics is None:
        return
    evidence.metrics = metrics
    if summary is None:
        return

    complexity = evidence.complexity
    complexity.average_complexity = metrics.cyclomatic_average
    complexity.max_complexity = metrics.cyclomatic_max
    complexity.lines_of_code = metrics.code_lines
    complexity.high_complexity_functions = [
        {
            "function": f.name,
            "file": f.path,
            "complexity": f.cyclomatic,
            "severity": "critical" if f.cyclomatic > CYCLOMATIC_CRITICAL else "high",
        }
        for f in sorted(summary.functions, key=lambda f: f.cyclomatic, reverse=True)
        if f.cyclomatic > CYCLOMATIC_LIMIT
    ][:MAX_LISTED_FUNCTIONS]
    if summary.functions:
        complexity.avg_function_length = round(
            sum(f.code_lines for f in summary.functions) / len(summary.functions), 2
        )

    dup = summary.duplication
    evidence.duplication = DuplicationEvidence(
        duplicate_blocks_count=len(dup.clones),
        duplicated_lines_count=dup.duplicated_lines,
        duplication_percentage=dup.density,
        duplicated_files=[
            {"file": f.path, "duplicated_lines": f.duplicated_lines}
            for f in sorted(dup.files, key=lambda f: -f.duplicated_lines)
            if f.duplicated_lines
        ],
    )

    if "samanvaya-metrics" not in evidence.tools_executed:
        evidence.tools_executed.append("samanvaya-metrics")
