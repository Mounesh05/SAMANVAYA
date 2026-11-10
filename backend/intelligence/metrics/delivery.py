"""
DORA software delivery metrics.

Definitions follow DORA's guide (dora.dev/guides/dora-metrics-four-keys):
    deployment frequency   "the number of deployments over a given period"
                           (production, successful deployments)
    change lead time       "time it takes for a change to go from committed to
                           version control to deployed in production"; measured
                           per commit, at the first successful production
                           deployment that contains it
    change fail rate       "ratio of deployments that require immediate
                           intervention following a deployment": a deployment
                           that caused an incident, or that was rolled back
    failed deployment      "time it takes to recover from a deployment that
    recovery time          fails and requires immediate intervention". Since
                           2023 only failures caused by a change count, not
                           external causes (dora.dev/insights/dora-metrics-history),
                           so only incidents linked to a deployment or marked
                           cause="change" are used. All incidents are reported
                           separately (classic time to restore).
    deployment rework rate added in 2024: share of deployments that are
                           unplanned fixes (rollbacks and hotfixes)

Performance levels: the 2023 Accelerate State of DevOps report clusters, used
as upper bounds (the clusters are statistical groups, not official cut-offs;
the 2024 report published different values):

    level   deploy frequency     lead time          fail rate  recovery
    elite   on demand (daily+)   < 1 day            <= 5%      < 1 hour
    high    day - week           1 day - 1 week     <= 10%     < 1 day
    medium  week - month         1 week - 1 month   <= 15%     1 day - 1 week
    low     slower               slower             > 15%      slower

Failed deployment ATTEMPTS (a deployment that never reached success) are not
change failures in DORA's sense; they are reported as deployment_failure_rate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from .pull_requests import Distribution, parse_time

SUCCESS = "success"
FAILED_STATES = {"failure", "error"}
DORA_SOURCE = "2023 Accelerate State of DevOps report (DORA) performance clusters"

# upper bounds per level, in the metric's unit
_FREQUENCY_PER_WEEK = ((7.0, "elite"), (1.0, "high"), (12 / 52, "medium"))   # higher is better
_LEAD_TIME_HOURS = ((24, "elite"), (24 * 7, "high"), (24 * 30, "medium"))  # lower is better
_FAIL_RATE_PERCENT = ((5, "elite"), (10, "high"), (15, "medium"))
_RECOVERY_HOURS = ((1, "elite"), (24, "high"), (24 * 7, "medium"))
LEVEL_ORDER = ["low", "medium", "high", "elite"]


def _level_lower_is_better(value: Optional[float], bounds, inclusive: bool) -> Optional[str]:
    if value is None:
        return None
    for limit, level in bounds:
        if value < limit or (inclusive and value == limit):
            return level
    return "low"


def frequency_level(per_week: Optional[float]) -> Optional[str]:
    if per_week is None:
        return None
    for limit, level in _FREQUENCY_PER_WEEK:
        if per_week >= limit:
            return level
    return "low"


def lead_time_level(median_hours: Optional[float]) -> Optional[str]:
    return _level_lower_is_better(median_hours, _LEAD_TIME_HOURS, inclusive=False)


def fail_rate_level(percent: Optional[float]) -> Optional[str]:
    return _level_lower_is_better(percent, _FAIL_RATE_PERCENT, inclusive=True)


def recovery_level(median_hours: Optional[float]) -> Optional[str]:
    return _level_lower_is_better(median_hours, _RECOVERY_HOURS, inclusive=False)


def _finished(d: Mapping[str, Any]) -> Optional[datetime]:
    return parse_time(d.get("finished_at")) or parse_time(d.get("created_at"))


def successful(deployments: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    out = [d for d in deployments if d.get("status") == SUCCESS and _finished(d)]
    return sorted(out, key=_finished)


def _in_window(moment: Optional[datetime], start: date, end: date) -> bool:
    return moment is not None and start <= moment.date() <= end


# ── the four (five) metrics ───────────────────────────────────────

@dataclass(frozen=True)
class DeploymentFrequency:
    deployments: int
    days: int
    deploy_days: int

    @property
    def per_week(self) -> float:
        return round(7 * self.deployments / self.days, 2) if self.days else 0.0

    @property
    def deploy_day_share(self) -> float:
        """% of days with at least one production deployment."""
        return round(100 * self.deploy_days / self.days, 2) if self.days else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"deployments": self.deployments, "days": self.days, "per_day": round(self.deployments / self.days, 3)
                if self.days else 0.0, "per_week": self.per_week, "deploy_day_share": self.deploy_day_share,
                "level": frequency_level(self.per_week) if self.deployments else "low"}


def deployment_frequency(deployments: Iterable[Mapping[str, Any]], start: date, end: date) -> DeploymentFrequency:
    done = [d for d in successful(deployments) if _in_window(_finished(d), start, end)]
    days = max(0, (end - start).days + 1)
    return DeploymentFrequency(len(done), days, len({_finished(d).date() for d in done}))


def lead_times_hours(deployments: Iterable[Mapping[str, Any]], start: date, end: date) -> List[float]:
    """Per commit: committed -> first successful deployment containing it (deployed in the window)."""
    seen: Set[str] = set()
    out: List[float] = []
    for d in successful(deployments):
        deployed = _finished(d)
        for commit in d.get("commits") or []:
            sha = commit.get("sha")
            committed = parse_time(commit.get("committed_at"))
            if not sha or sha in seen or committed is None:
                continue
            seen.add(sha)
            if _in_window(deployed, start, end) and deployed >= committed:
                out.append(round((deployed - committed).total_seconds() / 3600, 2))
    return out


def failed_changes(deployments: Iterable[Mapping[str, Any]], incidents: Iterable[Mapping[str, Any]]) -> Set[str]:
    """Deployment ids that required immediate intervention: caused an incident or were rolled back."""
    failed = {str(i["caused_by_deployment_id"]) for i in incidents if i.get("caused_by_deployment_id")}
    failed |= {str(d["rolled_back_deployment_id"]) for d in deployments if d.get("rolled_back_deployment_id")}
    return failed


def change_fail_rate(deployments: Sequence[Mapping[str, Any]], incidents: Sequence[Mapping[str, Any]],
                     start: date, end: date) -> Optional[float]:
    done = [d for d in successful(deployments) if _in_window(_finished(d), start, end)]
    if not done:
        return None
    failed = failed_changes(deployments, incidents)
    return round(100 * sum(1 for d in done if str(d.get("id")) in failed) / len(done), 2)


def deployment_failure_rate(deployments: Iterable[Mapping[str, Any]], start: date, end: date) -> Optional[float]:
    """Failed deployment ATTEMPTS / finished attempts (not a DORA metric)."""
    finished = [d for d in deployments if (d.get("status") == SUCCESS or d.get("status") in FAILED_STATES)
                and _in_window(_finished(d), start, end)]
    if not finished:
        return None
    return round(100 * sum(1 for d in finished if d.get("status") in FAILED_STATES) / len(finished), 2)


def recovery_hours(incidents: Iterable[Mapping[str, Any]], start: date, end: date,
                   change_only: bool = True) -> List[float]:
    """Resolved incidents started in the window: started -> resolved."""
    out = []
    for i in incidents:
        if change_only and not (i.get("caused_by_deployment_id") or i.get("cause") == "change"):
            continue
        began, resolved = parse_time(i.get("started_at")), parse_time(i.get("resolved_at"))
        if began and resolved and resolved >= began and _in_window(began, start, end):
            out.append(round((resolved - began).total_seconds() / 3600, 2))
    return out


def rework_rate(deployments: Sequence[Mapping[str, Any]], start: date, end: date,
                incidents: Iterable[Mapping[str, Any]] = ()) -> Optional[float]:
    """Unplanned fixes / successful deployments: rollbacks, hotfixes, and
    deployments an incident names as its fix (fixed_by_deployment_id)."""
    done = [d for d in successful(deployments) if _in_window(_finished(d), start, end)]
    if not done:
        return None
    fixes = {str(i["fixed_by_deployment_id"]) for i in incidents if i.get("fixed_by_deployment_id")}
    rework = sum(1 for d in done if d.get("is_rollback") or d.get("is_hotfix") or str(d.get("id")) in fixes)
    return round(100 * rework / len(done), 2)


# ── report ────────────────────────────────────────────────────────

def _week(moment: datetime) -> str:
    monday = moment.date() - timedelta(days=moment.weekday())
    return monday.isoformat()


def weekly_trend(deployments: Sequence[Mapping[str, Any]], incidents: Sequence[Mapping[str, Any]],
                 start: date, end: date) -> List[Dict[str, Any]]:
    done = [d for d in successful(deployments) if _in_window(_finished(d), start, end)]
    failed = failed_changes(deployments, incidents)
    weeks: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"deployments": 0, "failed": 0, "lead": []})
    seen: Set[str] = set()
    for d in successful(deployments):
        deployed = _finished(d)
        for commit in d.get("commits") or []:
            committed = parse_time(commit.get("committed_at"))
            sha = commit.get("sha")
            if sha and sha not in seen and committed:
                seen.add(sha)
                if _in_window(deployed, start, end) and deployed >= committed:
                    weeks[_week(deployed)]["lead"].append((deployed - committed).total_seconds() / 3600)
    for d in done:
        w = weeks[_week(_finished(d))]
        w["deployments"] += 1
        w["failed"] += str(d.get("id")) in failed
    rows = []
    for week in sorted(weeks):
        w = weeks[week]
        rows.append({
            "week": week,
            "deployments": w["deployments"],
            "change_fail_rate": round(100 * w["failed"] / w["deployments"], 2) if w["deployments"] else None,
            "lead_time_median_hours": Distribution.of(w["lead"]).median,
        })
    return rows


def dora_report(deployments: Sequence[Mapping[str, Any]], incidents: Sequence[Mapping[str, Any]],
                start: date, end: date) -> Dict[str, Any]:
    deployments, incidents = list(deployments), list(incidents)
    frequency = deployment_frequency(deployments, start, end)
    lead = Distribution.of(lead_times_hours(deployments, start, end))
    cfr = change_fail_rate(deployments, incidents, start, end)
    recovery = Distribution.of(recovery_hours(incidents, start, end, change_only=True))
    restore_all = Distribution.of(recovery_hours(incidents, start, end, change_only=False))
    levels = {
        "deployment_frequency": frequency.to_dict()["level"],
        "change_lead_time": lead_time_level(lead.median),
        "change_fail_rate": fail_rate_level(cfr),
        "failed_deployment_recovery_time": recovery_level(recovery.median),
    }
    known = [lvl for lvl in levels.values() if lvl]
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "deployment_frequency": frequency.to_dict(),
        "change_lead_time_hours": {**lead.to_dict(), "level": levels["change_lead_time"]},
        "change_fail_rate": {"percent": cfr, "level": levels["change_fail_rate"],
                             "failed_changes": sorted(failed_changes(deployments, incidents))},
        "failed_deployment_recovery_hours": {**recovery.to_dict(), "level": levels["failed_deployment_recovery_time"]},
        "time_to_restore_all_incidents_hours": restore_all.to_dict(),
        "deployment_rework_rate": rework_rate(deployments, start, end, incidents),
        "deployment_failure_rate": deployment_failure_rate(deployments, start, end),
        "levels": levels,
        # DORA defines no overall level; the weakest of the measured ones is the honest summary
        "lowest_level": min(known, key=LEVEL_ORDER.index) if known else None,
        "levels_source": DORA_SOURCE,
        "weekly": weekly_trend(deployments, incidents, start, end),
    }
