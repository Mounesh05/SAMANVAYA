# PR and sprint (flow) metrics

Branch: `feature/flow-metrics` (based on `feature/code-quality-metrics`). This document is for reviewers.

## What this branch adds

| Module | What it does |
|---|---|
| `metrics/pull_requests.py` | PR size (generated/lock files excluded), review status from the reviews, time to first review, time to merge/close, review rounds, median/p85/p90 summaries, unreviewed merge rate |
| `metrics/flow.py` | Velocity + say/do ratio, sprint completion, scope creep, cycle/lead time, blocked time, throughput, Little's Law check, burndown, **Monte Carlo forecast** (two-level bootstrap) and the average-velocity baseline |
| `domain/services/sprint_flow_service.py` | Loads sprint data for the metrics; **starts/completes sprints** (scope snapshot, velocity); logs scope changes |
| `evaluation/backtest_forecast.py` | Backtest of the forecast against the average-velocity method |

The metric modules are standard library only; the service and routes use the existing repositories.

## Bugs fixed

1. **`RiskEngine.analyze_sprint` read sprints wrongly** when it loaded data from the database:
   - it counted stories with status `"completed"`, but stories are marked `"done"`, so **completed stories were always 0**
   - it read `story_points`, but the story field is `points`, so **points were always 0**
   - it used `original_points`, which nothing ever writes, so **scope creep could never be detected**

   It now uses the same rules as `SprintService.calculate_sprint_health`: stories plus tasks without a
   story, status `"done"`, `points` (else `story_points`, else 1). Committed scope comes from the
   start-of-sprint snapshot. The result also gains a `flow` section.
2. **Sprints could never be started or completed.** `SprintService.update_sprint_status` had no callers, so
   sprints stayed in `planning` and velocity was always `None`. New endpoints start and complete them.
3. **PR review status was guessed** from GitHub's `mergeable_state` (merge conflicts and checks; "clean" was
   recorded as "approved" even with no review). Sync now fetches the reviews and derives the status from
   them. When fetching reviews fails, the previous values are kept.
4. **PR lines added/deleted were computed during sync but not stored.**

## How it is connected

**New endpoints**
- `POST /api/sprints/{id}/start` (`CREATE_SPRINT` + project write access): planning → active. Snapshots
  `committed_points` and `committed_item_ids`; only one active sprint per project (409 otherwise).
- `POST /api/sprints/{id}/complete`: active → completed. Stores `completed_points`, `velocity` and
  `completion_pct`.
- `GET /api/sprints/{id}/flow` (project access): the full flow report.
- `GET /api/github/projects/{id}/pr-metrics?exclude_weekends=false` (project access): PR summary for the
  project.

**Changed code paths**
- `PATCH /api/tasks/{id}/sprint` now logs the move in `sprint_scope_changes`. Tasks inside a story are
  counted through the story, so they are not logged.
- GitHub sync (and the PR webhook, which calls the same sync) stores `lines_added`, `lines_deleted`,
  `generated_lines_excluded`, `size_bucket`, `closed_at`, `reviews`, `first_review_at`, `review_rounds` and a
  review-based `review_status`. **One extra GitHub API call per synced PR** (`/pulls/{n}/reviews`).
- `RiskEngine.analyze_sprint`: fixed counting plus `evidence["flow"]`, only when the numbers come from the
  database, not when they are posted by the caller.

**New optional model fields** (existing documents stay valid)
- `Sprint`: `started_at`, `completed_at`, `committed_points`, `committed_item_ids`, `completed_points`
- `PullRequest`: the PR fields listed above

## Definitions

| Metric | Definition |
|---|---|
| Cycle time | First move into an active status (in_progress / review / blocked) → final move into done (reopened work counts until done again) |
| Lead time | Created → done |
| Blocked time | Total time in `blocked` per item |
| Velocity | Points completed per finished sprint; rolling mean of the last 3; say/do = completed ÷ committed |
| Scope creep | Points added after the sprint started ÷ committed points (removed points reported separately) |
| Little's Law | Average WIP = throughput × average cycle time; the ratio checks the flow data is consistent (≈ 1.0) |
| PR size | Lines added + deleted without generated/lock files; XS < 10, S < 100, M < 400, L < 1000, XL |
| Time to first review | First review by a human who is not the author (bots ignored) − opened |
| Review rounds | "Changes requested" reviews |
| Summaries | Median, p85, p90 (linear interpolation); optional weekend exclusion |
| Monte Carlo | Bootstraps past daily throughput, 10,000 runs, in items. **Two-level**: each run first redraws a plausible history, so uncertainty about the team's pace is included |

Unestimated work items count as 1 point (the rule `SprintService` already used).

## Forecast backtest

`python evaluation/backtest_forecast.py` → `evaluation/results/forecast_backtest.md`.

> **Simulated teams, not real project data** (300 per scenario). Rerun on real history once SAMANVAYA has
> completed sprints.

Main result, with work planned from the team's own past throughput:

| Scenario | Brier average | Brier MC 2-level | Date hit average | P85 hit MC 2-level (target 85%) |
|---|---|---|---|---|
| stable | 0.373 | **0.228** | 56.7% | **88.7%** |
| drift ±30% | 0.407 | **0.237** | 55.7% | **88.7%** |

- The average-velocity forecast is a yes/no answer with one date, which held only ~56% of the time. Monte
  Carlo gives a probability and an 85% date that held ~89% of the time, even when the team's pace changed.
- **The backtest led to two changes:**
  - The plain bootstrap was **overconfident**: its 85% dates held only 82–83% of the time. The two-level
    bootstrap (now the default) fixes this.
  - The first backtest design sized work from each team's *true* pace, which no forecast can know, so
    regression to the mean made every history-based forecast look worse. That design is still reported
    ("from true capacity"), next to the realistic one ("planned from history").
- Yes/no accuracy is similar for both methods (~59–62%). Monte Carlo's advantage is honest probabilities and
  dates, not better coin-flip calls. In each well-populated range, observed on-time rates are close to the
  predicted ones (for example 67% predicted, 67% observed).

## Not changed (for the team)

- `POST /api/intelligence/analyze-sprint/{id}` accepts sprint numbers from the caller instead of computing
  them, the same client-supplied-evidence issue as `/api/ai/invoke`.
- Stories default to **3 points** when nobody estimates them, which quietly inflates velocity. Consider
  making the estimate optional (`None`), so "unestimated" stays visible.
- Story moves between sprints have no update route yet, so only task moves are logged as scope changes;
  stories join a sprint when they are created with a `sprint_id`.

## Tests

- `test_metrics_flow.py`: 36 tests (PR helpers and reviews, percentiles, cycle/lead/blocked time,
  throughput, Little's Law, completion, scope creep, velocity, burndown, Monte Carlo, average baseline,
  full report)
- `test_flow_integration.py`: 8 tests (start/complete, one active sprint, scope changes, flow report, fixed
  `analyze_sprint`, posted numbers, GitHub sync fields), with in-memory stand-ins for MongoDB

```bash
SECRET_KEY=test python -m pytest tests/test_metrics_flow.py tests/test_flow_integration.py --noconftest
```

Existing tests touching the changed code also pass: risk engine, sprint health, sprint model, workflow,
quality engine, GitHub client (260 tests in total with the code-quality ones).
