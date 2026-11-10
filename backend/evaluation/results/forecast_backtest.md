# Sprint forecast backtest: Monte Carlo vs average velocity

> **Simulated teams, not real project data** (300 per scenario, seed 2026, 2000 Monte Carlo runs per forecast). Rerun on real history once SAMANVAYA has completed sprints.

Each team: 30 days of history, forecast made with 10 days left.

| Work sized | Scenario | Teams | On time | Brier average | Brier MC plain | Brier MC 2-level | Date hit average | P85 hit MC plain | P85 hit MC 2-level | Accuracy average | Accuracy MC 2-level |
|---|---|---|---|---|---|---|---|---|---|---|---|
| planned from history | stable | 300 | 53.0% | 0.373 | 0.228 | **0.228** | 56.7% | 81.7% | **88.7%** | 62.7% | 61.3% |
| planned from history | drift ±30% | 300 | 49.7% | 0.407 | 0.240 | **0.237** | 55.7% | 82.7% | **88.7%** | 59.3% | 58.7% |
| from true capacity | stable | 300 | 54.7% | 0.420 | 0.258 | **0.256** | 58.3% | 87.0% | **90.7%** | 58.0% | 58.0% |
| from true capacity | drift ±30% | 300 | 52.0% | 0.410 | 0.264 | **0.260** | 57.7% | 84.7% | **88.0%** | 59.0% | 61.0% |

- **Brier**: lower is better; 0.25 is what always answering 50% would score.
- **Hit rates**: how often the team finished within the forecast's 85% date (target 85%). The average forecast gives one date with no stated confidence; its hit rate shows how often that date held.
- **Planned from history** is how teams plan sprints and is the main result. **From true capacity** sizes work with information no forecast can have (the team's real pace), so every history-based forecast is pulled off by regression to the mean there; it is kept to show that limit.
- **Stable** follows Monte Carlo's own assumption (the future looks like the past), so it favours Monte Carlo; **drift** changes the team's pace by up to ±30% after the forecast.

Calibration, MC 2-level, planned from history, stable (small groups are noisy):

| Predicted range | Teams | Mean predicted | Observed on time |
|---|---|---|---|
| 20-40% | 82 | 33.3% | 30.5% |
| 40-60% | 128 | 49.5% | 57.8% |
| 60-80% | 88 | 67.1% | 67.0% |
| 80-100% | 2 | 80.2% | 50.0% |

Calibration, MC 2-level, planned from history, drift ±30% (small groups are noisy):

| Predicted range | Teams | Mean predicted | Observed on time |
|---|---|---|---|
| 20-40% | 84 | 33.5% | 32.1% |
| 40-60% | 136 | 49.0% | 50.7% |
| 60-80% | 78 | 68.3% | 66.7% |
| 80-100% | 2 | 80.6% | 50.0% |

Calibration, MC 2-level, from true capacity, stable (small groups are noisy):

| Predicted range | Teams | Mean predicted | Observed on time |
|---|---|---|---|
| 0-20% | 32 | 12.4% | 34.4% |
| 20-40% | 60 | 30.8% | 46.7% |
| 40-60% | 106 | 49.1% | 58.5% |
| 60-80% | 85 | 69.4% | 61.2% |
| 80-100% | 17 | 84.2% | 64.7% |

Calibration, MC 2-level, from true capacity, drift ±30% (small groups are noisy):

| Predicted range | Teams | Mean predicted | Observed on time |
|---|---|---|---|
| 0-20% | 34 | 14.1% | 41.2% |
| 20-40% | 81 | 29.8% | 42.0% |
| 40-60% | 83 | 51.0% | 53.0% |
| 60-80% | 79 | 69.3% | 64.6% |
| 80-100% | 23 | 85.2% | 56.5% |

