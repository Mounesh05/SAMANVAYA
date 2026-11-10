"""
Backtest: Monte Carlo sprint forecast vs the usual average-velocity forecast.

There is no real sprint history in this environment, so teams are SIMULATED
(stated in the report). For each simulated team:

    - working-day throughput ~ Poisson(rate x daily noise), noise ~ Gamma
      (over-dispersed, like real teams: some days 0, some days many); weekends 0
    - 30 days of history, then a forecast with 10 calendar days left
    - the real future is simulated from the same process ("stable") or from a
      process whose rate changed by up to +/-30% ("drift")

Remaining work is sized in two ways (both reported):
    planned from history   observed past throughput x 10 days x U(0.7, 1.3):
                           how teams actually plan sprints
    from true capacity     the team's TRUE rate x 10 days x U(0.7, 1.3): leaks
                           information no forecast can have, so it also shows
                           regression to the mean (a team with an unlucky
                           history is given work matched to its real pace)

Forecasts compared:
    average     remaining / mean daily throughput: one date, yes/no answer
    MC plain    bootstrap of past days
    MC 2-level  each run first redraws a plausible history (SAMANVAYA's default)

Scores:
    Brier       mean (probability - outcome)^2 for "done on time"; lower is
                better, 0.25 = always answering 50%
    P85 hit     share finishing within the forecast's 85% value (target 85%);
                for the average forecast, within its single date
    accuracy    correct yes/no calls (Monte Carlo: probability >= 50%)

    python evaluation/backtest_forecast.py [--teams 300] [--seed 2026] [--runs 2000]
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from intelligence.metrics.flow import average_velocity_forecast, monte_carlo_forecast  # noqa: E402

HISTORY_DAYS = 30
DAYS_LEFT = 10


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's method (small lambda)."""
    if lam <= 0:
        return 0
    threshold, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def simulate_days(rng: random.Random, rate: float, days: int, first_weekday: int) -> List[int]:
    out = []
    for d in range(days):
        if (first_weekday + d) % 7 >= 5:  # Saturday, Sunday
            out.append(0)
        else:
            out.append(poisson(rng, rate * rng.gammavariate(2.0, 0.5)))  # mean multiplier 1.0
    return out


def days_to_finish(rng: random.Random, rate: float, remaining: int, first_weekday: int, cap: int = 365) -> int:
    done = days = 0
    while done < remaining and days < cap:
        done += simulate_days(rng, rate, 1, first_weekday + days)[0]
        days += 1
    return days


@dataclass
class Case:
    actual_days: int
    avg_probability: float
    avg_days: int
    plain_probability: float
    plain_p85: int
    two_probability: float
    two_p85: int

    @property
    def on_time(self) -> bool:
        return self.actual_days <= DAYS_LEFT


def run_scenario(teams: int, seed: int, drift: float, runs: int, sizing: str) -> List[Case]:
    rng = random.Random(seed)
    cases: List[Case] = []
    while len(cases) < teams:
        rate = rng.uniform(0.5, 3.0)
        weekday = rng.randrange(7)
        history = simulate_days(rng, rate, HISTORY_DAYS, weekday)
        if not any(history):
            continue
        future_weekday = (weekday + HISTORY_DAYS) % 7
        per_day = sum(history) / len(history) if sizing == "history" else rate * 5 / 7
        remaining = max(1, round(per_day * DAYS_LEFT * rng.uniform(0.7, 1.3)))
        actual = days_to_finish(rng, rate * (1 + rng.uniform(-drift, drift)), remaining, future_weekday)
        mc_seed = rng.randrange(1 << 30)
        plain = monte_carlo_forecast(remaining, history, DAYS_LEFT, runs=runs, seed=mc_seed, two_level=False)
        two = monte_carlo_forecast(remaining, history, DAYS_LEFT, runs=runs, seed=mc_seed, two_level=True)
        avg = average_velocity_forecast(remaining, history, DAYS_LEFT)
        if None in (plain.probability_on_time, two.probability_on_time, avg.days_p50):
            continue
        cases.append(Case(actual, avg.probability_on_time / 100, avg.days_p50,
                          plain.probability_on_time / 100, plain.days_p85,
                          two.probability_on_time / 100, two.days_p85))
    return cases


def brier(probabilities: Sequence[float], outcomes: Sequence[bool]) -> float:
    return sum((p - (1.0 if o else 0.0)) ** 2 for p, o in zip(probabilities, outcomes)) / len(outcomes)


def score(cases: List[Case]) -> Dict[str, float]:
    outcomes = [c.on_time for c in cases]
    n = len(cases)
    return {
        "teams": n,
        "on_time": 100 * sum(outcomes) / n,
        "brier_avg": brier([c.avg_probability for c in cases], outcomes),
        "brier_plain": brier([c.plain_probability for c in cases], outcomes),
        "brier_two": brier([c.two_probability for c in cases], outcomes),
        "hit_avg": 100 * sum(c.actual_days <= c.avg_days for c in cases) / n,
        "hit_plain": 100 * sum(c.actual_days <= c.plain_p85 for c in cases) / n,
        "hit_two": 100 * sum(c.actual_days <= c.two_p85 for c in cases) / n,
        "acc_avg": 100 * sum((c.avg_probability >= 0.5) == c.on_time for c in cases) / n,
        "acc_two": 100 * sum((c.two_probability >= 0.5) == c.on_time for c in cases) / n,
    }


def calibration_bins(cases: List[Case], bins: int = 5) -> List[Dict[str, float]]:
    rows = []
    for b in range(bins):
        low, high = b / bins, (b + 1) / bins
        group = [c for c in cases if low <= c.two_probability < high or (b == bins - 1 and c.two_probability == 1.0)]
        if group:
            rows.append({"range": f"{int(low * 100)}-{int(high * 100)}%", "teams": len(group),
                         "predicted": 100 * sum(c.two_probability for c in group) / len(group),
                         "observed": 100 * sum(c.on_time for c in group) / len(group)})
    return rows


SCENARIOS = (
    ("planned from history", "stable", "history", 0.0, 0),
    ("planned from history", "drift ±30%", "history", 0.3, 1),
    ("from true capacity", "stable", "true", 0.0, 2),
    ("from true capacity", "drift ±30%", "true", 0.3, 3),
)


def write_report(results: List[Dict], out: Path, teams: int, seed: int, runs: int) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Sprint forecast backtest: Monte Carlo vs average velocity",
        "",
        f"> **Simulated teams, not real project data** ({teams} per scenario, seed {seed}, {runs} Monte Carlo "
        "runs per forecast). Rerun on real history once SAMANVAYA has completed sprints.",
        "",
        f"Each team: {HISTORY_DAYS} days of history, forecast made with {DAYS_LEFT} days left.",
        "",
        "| Work sized | Scenario | Teams | On time | Brier average | Brier MC plain | Brier MC 2-level "
        "| Date hit average | P85 hit MC plain | P85 hit MC 2-level | Accuracy average | Accuracy MC 2-level |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r["score"]
        lines.append(
            f"| {r['sizing']} | {r['scenario']} | {s['teams']} | {s['on_time']:.1f}% | {s['brier_avg']:.3f} "
            f"| {s['brier_plain']:.3f} | **{s['brier_two']:.3f}** | {s['hit_avg']:.1f}% | {s['hit_plain']:.1f}% "
            f"| **{s['hit_two']:.1f}%** | {s['acc_avg']:.1f}% | {s['acc_two']:.1f}% |"
        )
    lines += [
        "",
        "- **Brier**: lower is better; 0.25 is what always answering 50% would score.",
        "- **Hit rates**: how often the team finished within the forecast's 85% date (target 85%). The average "
        "forecast gives one date with no stated confidence; its hit rate shows how often that date held.",
        "- **Planned from history** is how teams plan sprints and is the main result. **From true capacity** sizes "
        "work with information no forecast can have (the team's real pace), so every history-based forecast is "
        "pulled off by regression to the mean there; it is kept to show that limit.",
        "- **Stable** follows Monte Carlo's own assumption (the future looks like the past), so it favours Monte "
        "Carlo; **drift** changes the team's pace by up to ±30% after the forecast.",
        "",
    ]
    for r in results:
        lines += [f"Calibration, MC 2-level, {r['sizing']}, {r['scenario']} (small groups are noisy):", "",
                  "| Predicted range | Teams | Mean predicted | Observed on time |", "|---|---|---|---|"]
        lines += [f"| {b['range']} | {b['teams']} | {b['predicted']:.1f}% | {b['observed']:.1f}% |" for b in r["bins"]]
        lines.append("")
    report = out / "forecast_backtest.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--teams", type=int, default=300)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--out", type=Path, default=BACKEND / "evaluation" / "results")
    args = parser.parse_args(argv)
    results = []
    for sizing_label, scenario, sizing, drift, offset in SCENARIOS:
        cases = run_scenario(args.teams, args.seed + offset, drift, args.runs, sizing)
        results.append({"sizing": sizing_label, "scenario": scenario, "score": score(cases),
                        "bins": calibration_bins(cases)})
    report = write_report(results, args.out, args.teams, args.seed, args.runs)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
