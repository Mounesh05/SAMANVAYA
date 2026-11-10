"""
Sprint and flow metrics: velocity, completion, scope creep, cycle time,
blocked time, throughput, Little's Law, burndown, Monte Carlo forecast.

Inputs are plain records (dicts), so the functions work on database documents
and on test data alike:
    item        {id, status, points | story_points, created_at, sprint_id}
                Items without an estimate count as 1 point, the same rule
                SprintService.calculate_sprint_health already uses.
    transition  {item_id, from_status, to_status, created_at}   (WorkflowService)
    sprint      {id, start_date, end_date, status, started_at,
                 committed_points, committed_item_ids, completed_points}
    scope change {sprint_id, item_id, action: added | removed, points, at}

Definitions
    cycle time   first move into an active status (in_progress / review /
                 blocked) -> final move into done. Reopened work counts until
                 it is done again.
    lead time    created -> done.
    blocked time total time spent in "blocked", per item.
    velocity     points completed in a finished sprint; rolling mean of the
                 last 3; say/do ratio = completed / committed.
    scope creep  points added after the sprint started / points committed at
                 the start (removed points reported separately).
    Little's Law average WIP = throughput x average cycle time (Little, 1961).
                 The ratio of the two sides checks that the flow data is
                 consistent (about 1.0 for a stable process).
    Monte Carlo  replays sampled days of past throughput many times
                 (bootstrap): P(remaining work done by the end date) and the
                 50% / 85% "done within N days" values. Forecasts in ITEMS,
                 not points (throughput-based forecasting, Vacanti 2015).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .pull_requests import Distribution, parse_time

DONE = "done"
ACTIVE_STATUSES = {"in_progress", "review", "blocked"}
BLOCKED = "blocked"


def item_points(item: Mapping[str, Any]) -> float:
    """Estimate of a work item; unestimated items count as 1."""
    for key in ("points", "story_points"):
        value = item.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return 1.0


def _transitions_by_item(transitions: Iterable[Mapping[str, Any]]) -> Dict[str, List[Tuple[datetime, str, str]]]:
    out: Dict[str, List[Tuple[datetime, str, str]]] = {}
    for t in transitions:
        at = parse_time(t.get("created_at") or t.get("at"))
        if at is None:
            continue
        out.setdefault(str(t["item_id"]), []).append((at, str(t.get("from_status", "")), str(t.get("to_status", ""))))
    for events in out.values():
        events.sort(key=lambda e: e[0])
    return out


# ── per-item flow ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ItemFlow:
    item_id: str
    started_at: Optional[datetime]
    done_at: Optional[datetime]
    cycle_hours: Optional[float]
    lead_hours: Optional[float]
    blocked_hours: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "done_at": self.done_at.isoformat() if self.done_at else None,
            "cycle_hours": self.cycle_hours, "lead_hours": self.lead_hours, "blocked_hours": self.blocked_hours,
        }


def item_flow(item: Mapping[str, Any], events: Sequence[Tuple[datetime, str, str]],
              now: Optional[datetime] = None) -> ItemFlow:
    now = now or datetime.now(timezone.utc)
    started = next((at for at, _, to in events if to in ACTIVE_STATUSES), None)
    final_status = events[-1][2] if events else str(item.get("status", ""))
    done = None
    if final_status == DONE:
        done = next((at for at, _, to in reversed(events) if to == DONE), None)
    blocked = 0.0
    entered: Optional[datetime] = None
    for at, _, to in events:
        if to == BLOCKED and entered is None:
            entered = at
        elif to != BLOCKED and entered is not None:
            blocked += (at - entered).total_seconds()
            entered = None
    if entered is not None:
        blocked += ((done or now) - entered).total_seconds()
    created = parse_time(item.get("created_at"))

    def hours(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
        return round((b - a).total_seconds() / 3600, 2) if a and b and b >= a else None

    return ItemFlow(str(item.get("id")), started, done, hours(started, done), hours(created, done), round(blocked / 3600, 2))


def flow_for_items(items: Iterable[Mapping[str, Any]], transitions: Iterable[Mapping[str, Any]],
                   now: Optional[datetime] = None) -> List[ItemFlow]:
    by_item = _transitions_by_item(transitions)
    return [item_flow(item, by_item.get(str(item.get("id")), []), now) for item in items]


# ── throughput, WIP, Little's Law ─────────────────────────────────

def daily_throughput(done_times: Iterable[datetime], start: date, end: date) -> List[int]:
    """Items finished per calendar day from start to end inclusive (zeros included)."""
    days = (end - start).days + 1
    if days <= 0:
        return []
    counts = [0] * days
    for t in done_times:
        index = (t.date() - start).days
        if 0 <= index < days:
            counts[index] += 1
    return counts


def average_wip(flows: Iterable[ItemFlow], start: date, end: date) -> float:
    """Mean number of items in an active status at the end of each day."""
    flows = [f for f in flows if f.started_at]
    days = (end - start).days + 1
    if days <= 0:
        return 0.0
    total = 0
    for offset in range(days):
        moment = datetime.combine(start + timedelta(days=offset), datetime.max.time(), tzinfo=timezone.utc)
        total += sum(1 for f in flows if f.started_at <= moment and (f.done_at is None or f.done_at > moment))
    return round(total / days, 2)


@dataclass(frozen=True)
class LittlesLaw:
    average_wip: float
    throughput_per_day: float
    average_cycle_days: Optional[float]

    @property
    def expected_wip(self) -> Optional[float]:
        if self.average_cycle_days is None:
            return None
        return round(self.throughput_per_day * self.average_cycle_days, 2)

    @property
    def ratio(self) -> Optional[float]:
        """Observed WIP / (throughput x cycle time); about 1.0 when consistent."""
        expected = self.expected_wip
        return round(self.average_wip / expected, 2) if expected else None

    def to_dict(self) -> Dict[str, Any]:
        return {"average_wip": self.average_wip, "throughput_per_day": self.throughput_per_day,
                "average_cycle_days": self.average_cycle_days, "expected_wip": self.expected_wip, "ratio": self.ratio}


def littles_law(flows: Sequence[ItemFlow], start: date, end: date) -> LittlesLaw:
    finished = [f for f in flows if f.done_at and start <= f.done_at.date() <= end]
    days = max(1, (end - start).days + 1)
    cycles = [f.cycle_hours / 24 for f in finished if f.cycle_hours is not None]
    return LittlesLaw(
        average_wip=average_wip(flows, start, end),
        throughput_per_day=round(len(finished) / days, 3),
        average_cycle_days=round(sum(cycles) / len(cycles), 2) if cycles else None,
    )


# ── sprints ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class SprintCompletion:
    items: int
    done_items: int
    points: float
    done_points: float

    @property
    def by_points(self) -> Optional[float]:
        return round(100 * self.done_points / self.points, 2) if self.points else None

    @property
    def by_items(self) -> Optional[float]:
        return round(100 * self.done_items / self.items, 2) if self.items else None

    def to_dict(self) -> Dict[str, Any]:
        return {"items": self.items, "done_items": self.done_items, "points": self.points,
                "done_points": self.done_points, "by_points": self.by_points, "by_items": self.by_items}


def sprint_completion(items: Iterable[Mapping[str, Any]]) -> SprintCompletion:
    items = list(items)
    done = [i for i in items if i.get("status") == DONE]
    return SprintCompletion(len(items), len(done), sum(map(item_points, items)), sum(map(item_points, done)))


@dataclass(frozen=True)
class ScopeCreep:
    committed_points: Optional[float]
    added_points: float
    removed_points: float

    @property
    def creep_percent(self) -> Optional[float]:
        return round(100 * self.added_points / self.committed_points, 2) if self.committed_points else None

    @property
    def net_change(self) -> float:
        return self.added_points - self.removed_points

    def to_dict(self) -> Dict[str, Any]:
        return {"committed_points": self.committed_points, "added_points": self.added_points,
                "removed_points": self.removed_points, "net_change": self.net_change,
                "creep_percent": self.creep_percent}


def scope_creep(sprint: Mapping[str, Any], changes: Iterable[Mapping[str, Any]]) -> ScopeCreep:
    """Only changes made after the sprint started count; None committed means
    the sprint was never started through SAMANVAYA (no snapshot exists)."""
    started = parse_time(sprint.get("started_at"))
    committed = sprint.get("committed_points")
    added = removed = 0.0
    if started is not None:
        for change in changes:
            at = parse_time(change.get("at"))
            if change.get("sprint_id") != sprint.get("id") or at is None or at <= started:
                continue
            points = float(change.get("points") or 0)
            if change.get("action") == "added":
                added += points
            elif change.get("action") == "removed":
                removed += points
    return ScopeCreep(float(committed) if committed is not None else None, added, removed)


@dataclass(frozen=True)
class Velocity:
    completed: List[float]
    committed: List[Optional[float]]

    @property
    def last(self) -> Optional[float]:
        return self.completed[-1] if self.completed else None

    @property
    def rolling_mean(self) -> Optional[float]:
        recent = self.completed[-3:]
        return round(sum(recent) / len(recent), 2) if recent else None

    @property
    def say_do_ratios(self) -> List[Optional[float]]:
        return [round(done / plan, 2) if plan else None for done, plan in zip(self.completed, self.committed)]

    def to_dict(self) -> Dict[str, Any]:
        return {"completed_points": self.completed, "last": self.last, "rolling_mean_3": self.rolling_mean,
                "say_do_ratios": self.say_do_ratios}


def velocity(completed_sprints: Iterable[Mapping[str, Any]]) -> Velocity:
    """From completed sprints, oldest first."""
    ordered = sorted(completed_sprints, key=lambda s: str(s.get("end_date") or ""))
    return Velocity(
        completed=[float(s.get("completed_points") or 0) for s in ordered],
        committed=[float(s["committed_points"]) if s.get("committed_points") is not None else None for s in ordered],
    )


def burndown(sprint: Mapping[str, Any], items: Iterable[Mapping[str, Any]], flows: Iterable[ItemFlow],
             changes: Iterable[Mapping[str, Any]] = (), today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Ideal vs actual remaining points for each day of the sprint (up to today)."""
    start = (parse_time(sprint.get("started_at")) or parse_time(sprint.get("start_date")))
    end = parse_time(sprint.get("end_date"))
    if start is None or end is None or end < start:
        return []
    items = list(items)
    points = {str(i.get("id")): item_points(i) for i in items}
    done_at = {f.item_id: f.done_at for f in flows if f.done_at}
    committed = float(sprint.get("committed_points") or sum(points.values()))
    later = [(parse_time(c.get("at")), c) for c in changes if c.get("sprint_id") == sprint.get("id")]
    days = (end.date() - start.date()).days
    last_day = min(end.date(), today or datetime.now(timezone.utc).date())
    rows = []
    for offset in range(days + 1):
        day = start.date() + timedelta(days=offset)
        if day > last_day:
            break
        moment = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc)
        scope = committed + sum(
            (float(c.get("points") or 0) if c.get("action") == "added" else -float(c.get("points") or 0))
            for at, c in later if at and start < at <= moment
        )
        burned = sum(points.get(item_id, 0) for item_id, at in done_at.items() if at <= moment)
        ideal = committed * (1 - offset / days) if days else 0.0
        rows.append({"date": day.isoformat(), "ideal_remaining": round(ideal, 2),
                     "actual_remaining": round(max(scope - burned, 0.0), 2), "scope": round(scope, 2)})
    return rows


# ── forecasting ───────────────────────────────────────────────────

@dataclass(frozen=True)
class Forecast:
    remaining_items: int
    days_left: int
    runs: int
    probability_on_time: Optional[float]    # 0-100
    days_p50: Optional[int]
    days_p85: Optional[int]
    method: str = "monte_carlo"

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def monte_carlo_forecast(remaining_items: int, daily_samples: Sequence[int], days_left: int,
                         runs: int = 10_000, seed: Optional[int] = None, max_days: int = 365,
                         two_level: bool = True) -> Forecast:
    """Bootstrap past daily throughput to forecast when the remaining items are done.

    `daily_samples` are calendar days (weekend zeros included) and `days_left`
    counts calendar days after today, so both use the same unit.

    two_level (default): each run first redraws a plausible history from the
    real one (same length, with replacement) and then samples days from that.
    A plain bootstrap treats a few weeks of history as the team's true pace and
    is overconfident; the extra level carries the uncertainty about the pace
    into the forecast (see evaluation/backtest_forecast.py for the effect).
    """
    if remaining_items <= 0:
        return Forecast(0, days_left, runs, 100.0, 0, 0)
    if not daily_samples or not any(daily_samples):
        return Forecast(remaining_items, days_left, runs, None, None, None)
    rng = random.Random(seed)
    on_time = 0
    durations: List[int] = []
    n = len(daily_samples)
    for _ in range(runs):
        history = [rng.choice(daily_samples) for _ in range(n)] if two_level else daily_samples
        if not any(history):
            durations.append(max_days)    # this plausible history never finishes anything
            continue
        done = days = 0
        while done < remaining_items and days < max_days:
            done += rng.choice(history)   # one sampled past day = one future day
            days += 1
        if done >= remaining_items and days <= days_left:
            on_time += 1
        durations.append(days if done >= remaining_items else max_days)
    durations.sort()

    def quantile(q: float) -> int:
        return durations[min(len(durations) - 1, math.ceil(q * len(durations)) - 1)]

    return Forecast(remaining_items, days_left, runs, round(100 * on_time / runs, 2), quantile(0.5), quantile(0.85))


def average_velocity_forecast(remaining_items: int, daily_samples: Sequence[int], days_left: int) -> Forecast:
    """The common baseline: remaining / average daily throughput. A yes/no answer
    (100% or 0%) with a single date, no uncertainty."""
    if remaining_items <= 0:
        return Forecast(0, days_left, 1, 100.0, 0, 0, method="average")
    mean = sum(daily_samples) / len(daily_samples) if daily_samples else 0
    if mean <= 0:
        return Forecast(remaining_items, days_left, 1, None, None, None, method="average")
    days = math.ceil(remaining_items / mean)
    return Forecast(remaining_items, days_left, 1, 100.0 if days <= days_left else 0.0, days, days, method="average")


# ── summary for one sprint ────────────────────────────────────────

def sprint_flow_report(
    sprint: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    transitions: Iterable[Mapping[str, Any]],
    changes: Iterable[Mapping[str, Any]] = (),
    completed_sprints: Iterable[Mapping[str, Any]] = (),
    history_flows: Optional[Sequence[ItemFlow]] = None,
    now: Optional[datetime] = None,
    history_days: int = 30,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Everything for one sprint. `history_flows` (items the team finished
    recently, any sprint) feeds the forecast; defaults to this sprint's items."""
    now = now or datetime.now(timezone.utc)
    flows = flow_for_items(items, transitions, now)
    changes = list(changes)
    history = list(history_flows) if history_flows is not None else flows
    window_start = (now - timedelta(days=history_days - 1)).date()
    samples = daily_throughput([f.done_at for f in history if f.done_at], window_start, now.date())
    end = parse_time(sprint.get("end_date"))
    days_left = max(0, (end.date() - now.date()).days) if end else 0
    remaining = sum(1 for i in items if i.get("status") != DONE)
    start = parse_time(sprint.get("started_at")) or parse_time(sprint.get("start_date"))
    return {
        "sprint_id": sprint.get("id"),
        "completion": sprint_completion(items).to_dict(),
        "scope_creep": scope_creep(sprint, changes).to_dict(),
        "velocity": velocity(completed_sprints).to_dict(),
        "cycle_hours": Distribution.of(f.cycle_hours for f in flows).to_dict(),
        "lead_hours": Distribution.of(f.lead_hours for f in flows).to_dict(),
        "blocked_hours_total": round(sum(f.blocked_hours for f in flows), 2),
        "currently_blocked": sum(1 for i in items if i.get("status") == BLOCKED),
        "littles_law": littles_law(flows, start.date(), now.date()).to_dict() if start else None,
        "burndown": burndown(sprint, items, flows, changes, now.date()),
        "forecast": monte_carlo_forecast(remaining, samples, days_left, seed=seed).to_dict(),
        "forecast_average_velocity": average_velocity_forecast(remaining, samples, days_left).to_dict(),
    }
