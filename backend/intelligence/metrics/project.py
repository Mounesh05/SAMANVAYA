"""
Run all six code-quality metrics over a set of Python files.

    1. cyclomatic complexity       4. maintainability index
    2. cognitive complexity        5. issues per 1,000 lines
    3. duplication                 6. technical debt + A-E rating

Returns one CodeQualitySummary with project totals and per-file results,
ready for the QualityEngine, the AI agents or a comparison with SonarQube.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .cognitive import analyze_source as cognitive_source
from .cyclomatic import analyze_source as cyclomatic_source
from .debt import TechnicalDebt, technical_debt
from .duplication import DEFAULT_MIN_LINES, DEFAULT_MIN_TOKENS, DuplicationReport, detect_duplicates
from .issues import (
    Issue,
    IssueDensityReport,
    complexity_issues,
    duplication_issues,
    issue_density,
    issues_from_findings,
)
from .maintainability import analyze_source as maintainability_source


@dataclass
class FileQuality:
    path: str
    code_lines: int
    cyclomatic_average: float
    cyclomatic_max: int
    cognitive_average: float
    cognitive_max: int
    maintainability: float
    average_function_maintainability: float
    duplication_density: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class CodeQualitySummary:
    files: List[FileQuality] = field(default_factory=list)
    duplication: Optional[DuplicationReport] = None
    issues: Optional[IssueDensityReport] = None
    debt: Optional[TechnicalDebt] = None
    parse_errors: Dict[str, str] = field(default_factory=dict)

    def _mean(self, attr: str) -> float:
        weighted = [(getattr(f, attr), f.code_lines) for f in self.files if f.code_lines]
        total = sum(lines for _, lines in weighted)
        return round(sum(v * lines for v, lines in weighted) / total, 2) if total else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_analyzed": len(self.files),
            "code_lines": sum(f.code_lines for f in self.files),
            "cyclomatic_max": max((f.cyclomatic_max for f in self.files), default=0),
            "cognitive_max": max((f.cognitive_max for f in self.files), default=0),
            "maintainability": self._mean("maintainability"),
            "average_function_maintainability": self._mean("average_function_maintainability"),
            "duplication_density": self.duplication.density if self.duplication else 0.0,
            "issue_density": self.issues.density if self.issues else 0.0,
            "weighted_issue_density": self.issues.weighted_density if self.issues else 0.0,
            "technical_debt": self.debt.debt if self.debt else "0min",
            "debt_ratio": self.debt.ratio if self.debt else 0.0,
            "rating": self.debt.rating if self.debt else "A",
            "files": [f.to_dict() for f in self.files],
            "parse_errors": dict(self.parse_errors),
        }


def analyze_sources(
    sources: Dict[str, str],
    findings: Iterable[Any] = (),
    include_cyclomatic_issues: bool = False,
    min_tokens: int = DEFAULT_MIN_TOKENS,
    min_lines: int = DEFAULT_MIN_LINES,
) -> CodeQualitySummary:
    """All six metrics for path -> source code (plus optional analyzer findings)."""
    summary = CodeQualitySummary()
    issues: List[Issue] = []
    code_lines: Dict[str, int] = {}

    for path in sorted(sources):
        source = sources[path]
        mi = maintainability_source(source, path)
        if mi.parse_error:
            summary.parse_errors[path] = mi.parse_error
            continue
        cyc = cyclomatic_source(source, path)
        cog = cognitive_source(source, path)
        issues += complexity_issues(cognitive=cog, cyclomatic=cyc if include_cyclomatic_issues else None)
        code_lines[path] = mi.code_lines
        summary.files.append(FileQuality(
            path=path,
            code_lines=mi.code_lines,
            cyclomatic_average=cyc.average,
            cyclomatic_max=cyc.maximum,
            cognitive_average=cog.average,
            cognitive_max=cog.maximum,
            maintainability=mi.mi,
            average_function_maintainability=mi.average_function_mi,
        ))

    parsed = {p: sources[p] for p in code_lines}
    summary.duplication = detect_duplicates(parsed, min_tokens=min_tokens, min_lines=min_lines)
    dup_by_file = {f.path: f.density for f in summary.duplication.files}
    for f in summary.files:
        f.duplication_density = dup_by_file.get(f.path, 0.0)
    issues += duplication_issues(summary.duplication)
    issues += issues_from_findings(findings)

    summary.issues = issue_density(issues, code_lines)
    summary.debt = technical_debt(issues, sum(code_lines.values()))
    return summary


def analyze_paths(
    paths: Iterable[str | Path],
    root: str | Path | None = None,
    findings: Iterable[Any] = (),
    **kwargs: Any,
) -> CodeQualitySummary:
    """All six metrics for Python files on disk (paths relative to `root`)."""
    sources: Dict[str, str] = {}
    unreadable: Dict[str, str] = {}
    root_path = Path(root) if root is not None else None
    for path in paths:
        p = Path(path)
        key = str(p.relative_to(root_path)) if root_path is not None else str(p)
        try:
            sources[key] = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            unreadable[key] = f"{type(exc).__name__}: {exc}"
    summary = analyze_sources(sources, findings=findings, **kwargs)
    summary.parse_errors.update(unreadable)
    return summary
