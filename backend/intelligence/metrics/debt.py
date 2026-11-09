"""
Technical debt and maintainability rating (SQALE method, Letouzey 2012),
the model SonarQube uses.

    debt        = sum of the remediation time of every code smell (minutes)
    debt ratio  = debt / (code_lines x cost_per_line) x 100
                  cost_per_line = 30 minutes: SonarQube's default estimate of
                  the time it takes to write one line of code
    rating      A <= 5%   B <= 10%   C <= 20%   D <= 50%   E > 50%
                (SonarQube's default maintainability rating grid)

Remediation time of an issue:
    issue.remediation_minutes when the rule sets it (our complexity and
    duplication rules do), otherwise by severity (configurable defaults):
        critical 30, high 20, medium 10, low 5, info 0

Like SonarQube, the debt ratio and rating cover maintainability, so only
code smells count by default; bugs and vulnerabilities are reported
separately (include_all_types=True adds them).

Time units: an 8-hour working day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .issues import ISSUE_TYPES, Issue

COST_PER_LINE_MINUTES = 30
MINUTES_PER_DAY = 8 * 60
DEFAULT_SEVERITY_MINUTES: Dict[str, int] = {"critical": 30, "high": 20, "medium": 10, "low": 5, "info": 0}

# (upper bound of the debt ratio in %, rating)
RATING_GRID = ((5.0, "A"), (10.0, "B"), (20.0, "C"), (50.0, "D"))


def rating_for(ratio_percent: float) -> str:
    for upper, rating in RATING_GRID:
        if ratio_percent <= upper:
            return rating
    return "E"


def remediation_minutes(issue: Issue, severity_minutes: Mapping[str, int] = DEFAULT_SEVERITY_MINUTES) -> int:
    if issue.remediation_minutes is not None:
        return issue.remediation_minutes
    return severity_minutes.get(issue.severity, 0)


def format_duration(minutes: int) -> str:
    """SonarQube-style duration: 2d 3h 15min (8h days)."""
    if minutes <= 0:
        return "0min"
    days, rest = divmod(minutes, MINUTES_PER_DAY)
    hours, mins = divmod(rest, 60)
    parts = [f"{days}d"] if days else []
    parts += [f"{hours}h"] if hours else []
    parts += [f"{mins}min"] if mins else []
    return " ".join(parts)


@dataclass
class TechnicalDebt:
    debt_minutes: int
    code_lines: int
    by_type: Dict[str, int] = field(default_factory=dict)
    by_file: Dict[str, int] = field(default_factory=dict)
    cost_per_line_minutes: int = COST_PER_LINE_MINUTES

    @property
    def development_cost_minutes(self) -> int:
        return self.code_lines * self.cost_per_line_minutes

    @property
    def ratio(self) -> float:
        """Debt as a % of the estimated cost of writing the code."""
        cost = self.development_cost_minutes
        return round(100 * self.debt_minutes / cost, 2) if cost else 0.0

    @property
    def rating(self) -> str:
        return rating_for(self.ratio)

    @property
    def minutes_to_rating_a(self) -> int:
        """Debt to pay off before the code reaches rating A (ratio <= 5%)."""
        allowed = self.development_cost_minutes * RATING_GRID[0][0] / 100
        return max(0, int(round(self.debt_minutes - allowed)))

    @property
    def debt(self) -> str:
        return format_duration(self.debt_minutes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "debt_minutes": self.debt_minutes,
            "debt": self.debt,
            "code_lines": self.code_lines,
            "ratio": self.ratio,
            "rating": self.rating,
            "minutes_to_rating_a": self.minutes_to_rating_a,
            "by_type": dict(self.by_type),
            "by_file": dict(self.by_file),
        }


def technical_debt(
    issues: Iterable[Issue],
    code_lines: int,
    severity_minutes: Mapping[str, int] = DEFAULT_SEVERITY_MINUTES,
    include_all_types: bool = False,
    cost_per_line_minutes: int = COST_PER_LINE_MINUTES,
) -> TechnicalDebt:
    """Total remediation time, debt ratio and A-E rating."""
    by_type = {t: 0 for t in ISSUE_TYPES}
    by_file: Dict[str, int] = {}
    total = 0
    for issue in issues:
        minutes = remediation_minutes(issue, severity_minutes)
        by_type[issue.type] = by_type.get(issue.type, 0) + minutes
        if include_all_types or issue.type == "code_smell":
            total += minutes
            by_file[issue.path] = by_file.get(issue.path, 0) + minutes
    return TechnicalDebt(
        debt_minutes=total,
        code_lines=code_lines,
        by_type=by_type,
        by_file=dict(sorted(by_file.items(), key=lambda kv: -kv[1])),
        cost_per_line_minutes=cost_per_line_minutes,
    )
