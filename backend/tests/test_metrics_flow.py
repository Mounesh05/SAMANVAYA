"""
Tests for intelligence.metrics.pull_requests and intelligence.metrics.flow.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from intelligence.metrics.flow import (
    average_velocity_forecast,
    burndown,
    daily_throughput,
    flow_for_items,
    item_points,
    littles_law,
    monte_carlo_forecast,
    scope_creep,
    sprint_completion,
    sprint_flow_report,
    velocity,
)
from intelligence.metrics.pull_requests import (
    Distribution,
    hours_between,
    is_bot,
    is_generated,
    percentile,
    pr_metrics,
    pr_size,
    review_rounds,
    review_status,
    size_bucket,
    summarize_prs,
)

UTC = timezone.utc


def t(day, hour=0):
    """November 2026, day `day`, hour `hour` (UTC). 2026-11-07/08 are a weekend."""
    return datetime(2026, 11, day, hour, tzinfo=UTC).isoformat()


def review(login, state, at, user_type="User"):
    return {"user": {"login": login, "type": user_type}, "state": state, "submitted_at": at}


# ── pull requests: helpers ────────────────────────────────────────

def test_hours_between_and_weekends():
    assert hours_between(t(2, 9), t(2, 17)) == 8.0
    assert hours_between(t(6, 12), t(9, 12)) == 72.0                       # Fri noon -> Mon noon
    assert hours_between(t(6, 12), t(9, 12), exclude_weekends=True) == 24.0  # Sat + Sun removed
    assert hours_between(t(3), None) is None and hours_between(t(5), t(4)) is None
    assert hours_between("2026-11-02T09:00:00Z", "2026-11-02T10:30:00Z") == 1.5


@pytest.mark.parametrize("path, generated", [
    ("package-lock.json", True), ("frontend/yarn.lock", True), ("static/app.min.js", True),
    ("dist/bundle.js", True), ("api/user_pb2.py", True), ("src/app.js", False), ("backend/main.py", False),
])
def test_generated_files(path, generated):
    assert is_generated(path) is generated


def test_bots():
    assert is_bot("dependabot[bot]") and is_bot("renovate") and is_bot("someone", "Bot")
    assert not is_bot("alice", "User")


@pytest.mark.parametrize("lines, bucket", [(0, "XS"), (9, "XS"), (10, "S"), (399, "M"), (400, "L"), (1000, "XL")])
def test_size_buckets(lines, bucket):
    assert size_bucket(lines) == bucket


def test_pr_size_excludes_generated_files():
    size = pr_size([
        {"filename": "src/app.py", "additions": 120, "deletions": 30},
        {"filename": "tests/test_app.py", "additions": 40, "deletions": 0},
        {"filename": "package-lock.json", "additions": 900, "deletions": 400},
    ])
    assert (size.lines_added, size.lines_deleted, size.files, size.generated_lines_excluded) == (160, 30, 2, 1300)
    assert size.lines_changed == 190 and size.bucket == "M"


# ── pull requests: reviews ────────────────────────────────────────

def test_review_status_uses_latest_decision_per_reviewer():
    reviews = [
        review("bob", "CHANGES_REQUESTED", t(2, 10)),
        review("carol", "APPROVED", t(2, 11)),
        review("bob", "APPROVED", t(3, 9)),           # bob changed his mind
    ]
    assert review_status(reviews, author="alice") == "approved"
    assert review_rounds(reviews, author="alice") == 1


def test_outstanding_changes_request_wins_and_dismissal_cancels():
    assert review_status([review("bob", "APPROVED", t(2)), review("carol", "CHANGES_REQUESTED", t(3))]) == "changes_requested"
    assert review_status([review("carol", "CHANGES_REQUESTED", t(2)), review("carol", "DISMISSED", t(3)),
                          review("bob", "APPROVED", t(4))]) == "approved"


def test_bots_author_and_pending_reviews_are_ignored():
    reviews = [review("dependabot[bot]", "APPROVED", t(2)), review("alice", "APPROVED", t(2)),
               review("bob", "PENDING", t(2))]
    assert review_status(reviews, author="alice") == "pending"
    assert review_status([review("bob", "COMMENTED", t(2))], author="alice") == "in_review"


def test_pr_metrics_from_stored_document():
    pr = {"pr_number": 7, "status": "merged", "author_login": "alice", "created_at": t(2, 9),
          "merged_at": t(4, 9), "lines_added": 300, "lines_deleted": 50, "files_changed_count": 6,
          "reviews": [
              {"reviewer": "ci-helper", "is_bot": True, "state": "APPROVED", "submitted_at": t(2, 9)},
              {"reviewer": "bob", "is_bot": False, "state": "CHANGES_REQUESTED", "submitted_at": t(2, 15)},
              {"reviewer": "bob", "is_bot": False, "state": "APPROVED", "submitted_at": t(3, 15)},
          ]}
    m = pr_metrics(pr)
    assert m.size.bucket == "M" and m.size.lines_changed == 350
    assert m.hours_to_first_review == 6.0          # the bot's instant approval does not count
    assert m.hours_to_merge == 48.0 and m.hours_to_close is None
    assert m.review_status == "approved" and m.review_rounds == 1 and m.reviewed


def test_closed_without_merge():
    m = pr_metrics({"status": "closed", "created_at": t(2), "closed_at": t(3)})
    assert m.hours_to_close == 24.0 and m.hours_to_merge is None and not m.reviewed and m.size is None


# ── percentiles and summary ───────────────────────────────────────

def test_percentile_linear_interpolation():
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert percentile(data, 50) == 5.5 and percentile(data, 90) == 9.1 and percentile(data, 0) == 1
    assert percentile([], 50) is None and percentile([4], 85) == 4
    d = Distribution.of([1, 2, 3, None, 100])
    assert (d.n, d.median, d.mean) == (4, 2.5, 26.5)          # the median resists the outlier


def test_summarize_prs_and_unreviewed_merges():
    prs = [
        {"status": "merged", "created_at": t(2), "merged_at": t(3), "lines_added": 50, "lines_deleted": 0,
         "reviews": [review("bob", "APPROVED", t(2, 6))], "author_login": "alice"},
        {"status": "merged", "created_at": t(2), "merged_at": t(2, 1), "lines_added": 5, "lines_deleted": 0},
        {"status": "open", "created_at": t(3), "lines_added": 2000, "lines_deleted": 10},
    ]
    data = summarize_prs(prs).to_dict()
    assert (data["prs"], data["merged"], data["open"]) == (3, 2, 1)
    assert data["unreviewed_merge_rate"] == 50.0
    assert data["size_buckets"] == {"XS": 1, "S": 1, "M": 0, "L": 0, "XL": 1}
    assert data["hours_to_merge"]["median"] == 12.5
    assert data["hours_to_first_review"]["n"] == 1


# ── flow: items ───────────────────────────────────────────────────

def tr(item, frm, to, at):
    return {"item_id": item, "from_status": frm, "to_status": to, "created_at": at}


def test_item_points_rule():
    assert item_points({"points": 5}) == 5 and item_points({"story_points": 8}) == 8 and item_points({}) == 1


def test_cycle_lead_and_blocked_time():
    items = [{"id": "A", "status": "done", "created_at": t(1)}, {"id": "B", "status": "blocked", "created_at": t(1)}]
    transitions = [
        tr("A", "todo", "in_progress", t(2, 9)), tr("A", "in_progress", "blocked", t(2, 12)),
        tr("A", "blocked", "in_progress", t(3, 12)), tr("A", "in_progress", "done", t(4, 9)),
        tr("A", "done", "in_progress", t(5, 9)), tr("A", "in_progress", "done", t(6, 9)),   # reopened, done again
        tr("B", "todo", "blocked", t(5)),
    ]
    flows = {f.item_id: f for f in flow_for_items(items, transitions, now=datetime(2026, 11, 6, tzinfo=UTC))}
    a, b = flows["A"], flows["B"]
    assert a.cycle_hours == 96.0                    # Nov 2 09:00 -> final done Nov 6 09:00
    assert a.lead_hours == 129.0                    # created Nov 1 00:00 -> Nov 6 09:00
    assert a.blocked_hours == 24.0
    assert b.done_at is None and b.cycle_hours is None and b.blocked_hours == 24.0   # still blocked at "now"


def test_daily_throughput_includes_zero_days():
    done = [datetime(2026, 11, d, 10, tzinfo=UTC) for d in (2, 2, 4, 9)]
    assert daily_throughput(done, date(2026, 11, 2), date(2026, 11, 5)) == [2, 0, 1, 0]


def test_littles_law_consistency():
    # one item per day, each in progress for exactly 2 days -> WIP 2 = 1/day x 2 days
    items, transitions = [], []
    for d in range(1, 21):
        items.append({"id": f"I{d}", "status": "done", "created_at": t(d)})
        transitions += [tr(f"I{d}", "todo", "in_progress", t(d, 12)), tr(f"I{d}", "in_progress", "done", t(d + 2, 12))]
    flows = flow_for_items(items, transitions, now=datetime(2026, 11, 25, tzinfo=UTC))
    law = littles_law(flows, date(2026, 11, 5), date(2026, 11, 18))
    assert law.throughput_per_day == 1.0 and law.average_cycle_days == 2.0
    assert law.average_wip == 2.0 and law.ratio == 1.0


# ── flow: sprints ─────────────────────────────────────────────────

SPRINT = {"id": "S1", "start_date": t(2), "end_date": t(13), "started_at": t(2, 9),
          "committed_points": 20, "status": "active"}


def test_sprint_completion_by_points_and_items():
    items = [{"status": "done", "points": 5}, {"status": "done", "points": 3}, {"status": "todo", "points": 8},
             {"status": "in_progress"}]
    c = sprint_completion(items)
    assert (c.items, c.done_items, c.points, c.done_points) == (4, 2, 17, 8)
    assert c.by_points == round(800 / 17, 2) and c.by_items == 50.0


def test_scope_creep_counts_only_changes_after_start():
    changes = [
        {"sprint_id": "S1", "item_id": "x", "action": "added", "points": 8, "at": t(1)},    # planning: ignored
        {"sprint_id": "S1", "item_id": "y", "action": "added", "points": 5, "at": t(4)},
        {"sprint_id": "S1", "item_id": "z", "action": "removed", "points": 2, "at": t(5)},
        {"sprint_id": "S2", "item_id": "w", "action": "added", "points": 9, "at": t(5)},    # other sprint
    ]
    creep = scope_creep(SPRINT, changes)
    assert (creep.added_points, creep.removed_points, creep.net_change) == (5, 2, 3)
    assert creep.creep_percent == 25.0
    assert scope_creep({"id": "S1"}, changes).creep_percent is None     # never started: no snapshot


def test_velocity_and_say_do():
    sprints = [{"end_date": t(13), "completed_points": 18, "committed_points": 20},
               {"end_date": t(1), "completed_points": 10, "committed_points": 15},
               {"end_date": t(27), "completed_points": 22, "committed_points": None}]
    v = velocity(sprints)
    assert v.completed == [10, 18, 22] and v.last == 22 and v.rolling_mean == 16.67
    assert v.say_do_ratios == [0.67, 0.9, None]


def test_burndown():
    items = [{"id": "A", "points": 10, "status": "done"}, {"id": "B", "points": 10, "status": "todo"}]
    flows = flow_for_items(items, [tr("A", "in_progress", "done", t(4, 15))])
    changes = [{"sprint_id": "S1", "item_id": "C", "action": "added", "points": 4, "at": t(6, 10)}]
    rows = burndown(SPRINT, items, flows, changes, today=date(2026, 11, 7))
    by_day = {r["date"]: r for r in rows}
    assert len(rows) == 6 and rows[0]["ideal_remaining"] == 20.0
    assert by_day["2026-11-03"]["actual_remaining"] == 20.0
    assert by_day["2026-11-04"]["actual_remaining"] == 10.0          # A done
    assert by_day["2026-11-06"]["scope"] == 24.0 and by_day["2026-11-06"]["actual_remaining"] == 14.0
    assert burndown({"id": "S9"}, items, flows) == []


# ── forecasting ───────────────────────────────────────────────────

def test_monte_carlo_is_reproducible_and_sensible():
    samples = [0, 1, 2, 1, 0, 3, 1, 2, 0, 1]          # mean 1.1 items per day
    f = monte_carlo_forecast(10, samples, days_left=10, seed=42)
    assert f == monte_carlo_forecast(10, samples, days_left=10, seed=42)
    assert 20 < f.probability_on_time < 80               # mean pace finishes right around day 9-10: uncertain
    assert f.days_p50 <= f.days_p85
    assert monte_carlo_forecast(10, samples, days_left=40, seed=1).probability_on_time > 99
    assert monte_carlo_forecast(10, samples, days_left=3, seed=1).probability_on_time < 1


def test_two_level_bootstrap_is_wider_than_plain():
    # few days of history: the pace itself is uncertain, so the 2-level forecast spreads out more
    samples = [0, 2, 1, 0, 3, 1, 0]
    plain = monte_carlo_forecast(15, samples, days_left=14, runs=20_000, seed=3, two_level=False)
    two = monte_carlo_forecast(15, samples, days_left=14, runs=20_000, seed=3, two_level=True)
    assert two.days_p85 - two.days_p50 > plain.days_p85 - plain.days_p50
    assert two.days_p85 >= plain.days_p85


def test_monte_carlo_edge_cases():
    assert monte_carlo_forecast(0, [1], 5).probability_on_time == 100.0
    assert monte_carlo_forecast(5, [0, 0, 0], 5).probability_on_time is None
    assert monte_carlo_forecast(5, [], 5).days_p85 is None


def test_average_velocity_baseline_is_yes_or_no():
    samples = [0, 1, 2, 1, 0, 3, 1, 2, 0, 1]
    f = average_velocity_forecast(10, samples, days_left=10)
    assert f.days_p50 == f.days_p85 == 10 and f.probability_on_time == 100.0
    assert average_velocity_forecast(12, samples, days_left=10).probability_on_time == 0.0


def test_sprint_flow_report_end_to_end():
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    items = [{"id": "A", "status": "done", "points": 5, "created_at": t(1)},
             {"id": "B", "status": "in_progress", "points": 3, "created_at": t(1)},
             {"id": "C", "status": "todo", "created_at": t(3)}]
    transitions = [tr("A", "todo", "in_progress", t(2, 10)), tr("A", "in_progress", "done", t(4, 10)),
                   tr("B", "todo", "in_progress", t(5, 10))]
    report = sprint_flow_report(SPRINT, items, transitions, seed=7, now=now)
    assert report["completion"]["done_points"] == 5 and report["completion"]["points"] == 9
    assert report["cycle_hours"]["median"] == 48.0
    assert report["forecast"]["remaining_items"] == 2 and report["forecast"]["days_left"] == 7
    assert report["forecast_average_velocity"]["method"] == "average"
    assert report["littles_law"]["throughput_per_day"] > 0
    assert report["burndown"][-1]["date"] == "2026-11-06"
