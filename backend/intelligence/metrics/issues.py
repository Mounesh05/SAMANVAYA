"""
Issues and issue density (issues per 1,000 lines of code).

An issue is one problem at one place in the code. Sources:
    - our own metrics:
        cognitive complexity above 15 per function   (SonarQube's default rule)
        cyclomatic complexity above 10 per function  (optional, off by default:
                                                      SonarQube's default Python
                                                      profile flags cognitive only,
                                                      and flagging both would
                                                      count one problem twice)
        each duplicated block
    - SAMANVAYA's existing analyzers (ruff, bandit, eslint, ...):
        their `Finding` objects, converted with `issues_from_findings`

Issue types follow SonarQube: code_smell, bug, vulnerability.
Severities follow SAMANVAYA's SeverityEnum: critical, high, medium, low, info.

    density          = issues / (code_lines / 1000)
    weighted density = sum(severity weight) / (code_lines / 1000)
                       weights: critical 10, high 5, medium 3, low 1, info 0
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .cognitive import FileCognitive, MODERATE_MAX as COGNITIVE_LIMIT
from .cyclomatic import FileComplexity, LOW_MAX as CYCLOMATIC_LIMIT
from .duplication import DuplicationReport

SEVERITIES = ("critical", "high", "medium", "low", "info")
SEVERITY_WEIGHTS: Dict[str, int] = {"critical": 10, "high": 5, "medium": 3, "low": 1, "info": 0}
ISSUE_TYPES = ("code_smell", "bug", "vulnerability")

# Remediation models for our own rules (minutes), SonarQube-style:
COMPLEXITY_BASE_MINUTES = 5       # fixed cost to start refactoring a function
COMPLEXITY_MINUTES_PER_POINT = 1  # plus one minute per point above the limit
DUPLICATED_BLOCK_MINUTES = 10     # extract one copy into a shared function


@dataclass(frozen=True)
class Issue:
    rule: str
    type: str          # code_smell | bug | vulnerability
    severity: str      # critical | high | medium | low | info
    path: str
    line: Optional[int]
    message: str
    source: str = "samanvaya"
    remediation_minutes: Optional[int] = None  # None: the debt model decides by severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "type": self.type,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "source": self.source,
            "remediation_minutes": self.remediation_minutes,
        }


# ── issue generators ──────────────────────────────────────────────

def _complexity_severity(score: int, limit: int) -> str:
    return "high" if score > 2 * limit else "medium"


def complexity_issues(
    cognitive: Optional[FileCognitive] = None,
    cyclomatic: Optional[FileComplexity] = None,
    cognitive_limit: int = COGNITIVE_LIMIT,
    cyclomatic_limit: int = CYCLOMATIC_LIMIT,
) -> List[Issue]:
    """One issue per function above the complexity limit."""
    issues: List[Issue] = []
    if cognitive is not None:
        for f in cognitive.functions:
            if f.cognitive > cognitive_limit:
                excess = f.cognitive - cognitive_limit
                issues.append(Issue(
                    rule="cognitive-complexity",
                    type="code_smell",
                    severity=_complexity_severity(f.cognitive, cognitive_limit),
                    path=cognitive.path,
                    line=f.lineno,
                    message=f"{f.name} has cognitive complexity {f.cognitive} (limit {cognitive_limit})",
                    remediation_minutes=COMPLEXITY_BASE_MINUTES + excess * COMPLEXITY_MINUTES_PER_POINT,
                ))
    if cyclomatic is not None:
        for f in cyclomatic.functions:
            if f.cyclomatic > cyclomatic_limit:
                excess = f.cyclomatic - cyclomatic_limit
                issues.append(Issue(
                    rule="cyclomatic-complexity",
                    type="code_smell",
                    severity=_complexity_severity(f.cyclomatic, cyclomatic_limit),
                    path=cyclomatic.path,
                    line=f.lineno,
                    message=f"{f.name} has cyclomatic complexity {f.cyclomatic} (limit {cyclomatic_limit})",
                    remediation_minutes=COMPLEXITY_BASE_MINUTES + excess * COMPLEXITY_MINUTES_PER_POINT,
                ))
    return issues


def duplication_issues(report: DuplicationReport) -> List[Issue]:
    """One issue per duplicated block (reported on the copy)."""
    return [
        Issue(
            rule="duplicated-block",
            type="code_smell",
            severity="medium",
            path=clone.copy.path,
            line=clone.copy.start_line,
            message=(
                f"Lines {clone.copy.start_line}-{clone.copy.end_line} duplicate "
                f"{clone.original.path}:{clone.original.start_line}-{clone.original.end_line} "
                f"({clone.tokens} tokens)"
            ),
            remediation_minutes=DUPLICATED_BLOCK_MINUTES,
        )
        for clone in report.clones
    ]


_CATEGORY_TO_TYPE = {"security": "vulnerability", "syntax": "bug", "type": "bug"}


def issues_from_findings(findings: Iterable[Any]) -> List[Issue]:
    """Convert SAMANVAYA analyzer `Finding` objects (or similar dicts) into issues."""
    issues: List[Issue] = []
    for finding in findings:
        get = finding.get if isinstance(finding, Mapping) else lambda k, d=None: getattr(finding, k, d)
        severity = get("severity", "medium")
        severity = getattr(severity, "value", severity)
        severity = str(severity).lower() if str(severity).lower() in SEVERITIES else "medium"
        tool = get("source_tool", "external")
        issues.append(Issue(
            rule=f"{tool}:{get('rule_id', 'unknown')}",
            type=_CATEGORY_TO_TYPE.get(str(get("category", "")).lower(), "code_smell"),
            severity=severity,
            path=str(get("file_path", "")).replace("\\", "/"),
            line=get("line_number"),
            message=str(get("message", "")),
            source=str(tool),
        ))
    return issues


# ── density ───────────────────────────────────────────────────────

def _per_kloc(value: float, code_lines: int) -> float:
    return round(value / (code_lines / 1000), 2) if code_lines else 0.0


@dataclass
class FileIssueDensity:
    path: str
    code_lines: int
    issues: int
    weighted: int

    @property
    def density(self) -> float:
        return _per_kloc(self.issues, self.code_lines)

    @property
    def weighted_density(self) -> float:
        return _per_kloc(self.weighted, self.code_lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "code_lines": self.code_lines,
            "issues": self.issues,
            "density": self.density,
            "weighted_density": self.weighted_density,
        }


@dataclass
class IssueDensityReport:
    issues: List[Issue] = field(default_factory=list)
    code_lines: int = 0
    files: List[FileIssueDensity] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.issues)

    @property
    def weighted(self) -> int:
        return sum(SEVERITY_WEIGHTS.get(i.severity, 0) for i in self.issues)

    @property
    def density(self) -> float:
        """Issues per 1,000 lines of code."""
        return _per_kloc(self.count, self.code_lines)

    @property
    def weighted_density(self) -> float:
        """Severity-weighted issues per 1,000 lines of code."""
        return _per_kloc(self.weighted, self.code_lines)

    @property
    def by_type(self) -> Dict[str, int]:
        counts = Counter(i.type for i in self.issues)
        return {t: counts.get(t, 0) for t in ISSUE_TYPES}

    @property
    def by_severity(self) -> Dict[str, int]:
        counts = Counter(i.severity for i in self.issues)
        return {s: counts.get(s, 0) for s in SEVERITIES}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "code_lines": self.code_lines,
            "density": self.density,
            "weighted_density": self.weighted_density,
            "by_type": self.by_type,
            "by_severity": self.by_severity,
            "files": [f.to_dict() for f in self.files],
            "issues": [i.to_dict() for i in self.issues],
        }


def issue_density(issues: Iterable[Issue], code_lines_by_file: Mapping[str, int]) -> IssueDensityReport:
    """Issues per 1,000 lines, overall and per file.

    `code_lines_by_file` maps each analysed file to its code lines (NCLOC);
    its total is the denominator, so files with no issues still count.
    """
    issue_list = list(issues)
    per_file: Dict[str, List[Issue]] = {}
    for issue in issue_list:
        per_file.setdefault(issue.path, []).append(issue)
    files = [
        FileIssueDensity(
            path=path,
            code_lines=lines,
            issues=len(per_file.get(path, [])),
            weighted=sum(SEVERITY_WEIGHTS.get(i.severity, 0) for i in per_file.get(path, [])),
        )
        for path, lines in sorted(code_lines_by_file.items())
    ]
    return IssueDensityReport(issues=issue_list, code_lines=sum(code_lines_by_file.values()), files=files)
