# PR risk prediction (just-in-time defect prediction)

**Question answered:** how likely is this pull request to introduce a bug?

Before this change, `RiskEngine.analyze_pull_request` added up fixed points
(files changed, lines changed, tests). Those thresholds were never checked
against real outcomes. This package learns the answer from the project's own
git history and is measured on data it has not seen. When no trustworthy model
exists, the risk engine falls back to the old rules.

Standard library only. git runs with argument lists, never a shell. No new
packages are needed in production.

## Pipeline

| step | module | method |
|---|---|---|
| 1. history | `git_history.py` | Changes that landed on the main branch, oldest first: direct commits and merged PRs (the merge's diff against the main line). Each merge is mapped to the commits it brought in. Only product code counts: tests, docs, examples, scripts and vendored code (`vendor/`, `_vendor/`, `third_party/`, `pkg/packages/`, …) are excluded. |
| 2. labels | `szz.py` | **SZZ** (Śliwerski, Zimmermann & Zeller, MSR 2005). Fix commits are found by keywords (fix/bug/defect/patch), skipping docs, typo, lint, CI and test "fixes". The lines a fix deleted or changed (blank and comment lines skipped) are traced with `git blame -w` on the fix's parent. The change that last touched each line is labelled *bug-introducing*. |
| 3. features | `features.py` | The **14 change metrics of Kamei et al. 2013** (IEEE TSE), computed in one pass through time, so a change only ever sees its past: LA, LD, LT (size), NS, ND, NF, ENTROPY (diffusion), FIX (purpose), NDEV, AGE, NUC (history), EXP, REXP, SEXP (author experience). |
| 4. models | `model.py` | **Logistic regression:** log1p plus standardisation, L2, Newton/IRLS with exact convergence, balanced class weights. Explanation = w·z per feature (exact). **Gradient-boosted stumps:** Friedman 2001 with logistic loss, 32 quantile bins, shrinkage 0.1, 200 rounds. Additive per feature, so explanations are exact too. Both are deterministic and stored as JSON. |
| 5. train + select | `predictor.py` | Three candidates: logistic on size only (LA, LD, NF), logistic on all 14, stumps on all 14. They are compared on a held-out period, and a richer model is used only if it beats the simpler one. The winner is refitted and saved with the history state needed to score new PRs. |

## Evaluation on open-source projects

`evaluation/evaluate_risk_model.py` (full table: `evaluation/results/risk_model_evaluation.md`).

- **Data:** the complete main-branch history of httpx, requests and flask, which have 1,415, 2,670 and 2,283 changes.
- **Time-ordered split:** the oldest 60% is used for training and the next 30% for testing. The newest 10% is dropped, because bugs in recent changes have not been found yet.
- **LightGBM 4.5.0:** a reference model only, run in a separate environment.

Mean over the 3 projects (test period):

| method | AUC | F1 | recall@20% effort (per line) |
|---|---|---|---|
| rules v0, as deployed | 0.552 | 0.089 | 0.512 |
| rules v0, bugs fixed | 0.585 | 0.040 | 0.193 |
| size only, LA+LD (ranking) | 0.797 | – | 0.106 |
| smallest change first (Yang et al. 2016) | 0.203 | – | 0.516 |
| **logistic, size features** | **0.801** | **0.500** | 0.511 |
| logistic, 14 features | 0.764 | 0.467 | 0.461 |
| boosted stumps, 14 features | 0.774 | 0.439 | **0.540** |
| LightGBM (reference) | 0.779 | 0.445 | 0.488 |

What this shows (stated as measured):

1. **The rules barely beat chance.** AUC is 0.55, and F1 is 0.09 because almost no PR reaches MEDIUM. Every learned model does much better: AUC about 0.77–0.80, F1 about 0.44–0.50.
2. **Our pure-Python models match LightGBM.** Stumps reach 0.774 vs 0.779 AUC. The implementation is sound, and LightGBM is not needed in production.
3. **Change size is the strongest single signal on these projects.** A three-feature size model ties or beats the 14-feature models. This matches the literature: size is a top Kamei feature, and SZZ favours large changes because they have more lines that can be blamed. This is why the trainer compares candidates per project and deploys the simplest one that is not worse.
4. **Effort-aware review is a different goal.** If reviewers can only read 20% of changed lines, reviewing small changes first finds about 52% of the bugs. Ranking by model risk per line does the same (0.46–0.54). Ranking by raw risk (the AUC winner) finds only about 11%, because the riskiest changes are also the biggest. The evaluation reports both views.

Known limits:
- SZZ labels are noisy. Some fixes have no keyword, and some blamed lines were only refactored.
- Fixes that only add lines cannot be traced.
- Only 3 Python projects were tested.
- The score is trained with balanced class weights, so 0.5 means "as likely buggy as clean", not "50% of such PRs have bugs". It is a ranking score, not a calibrated rate.

## How SAMANVAYA uses it

- `POST /api/risk-model/projects/{project_id}/train` (LEAD, PM, with project write access) starts training in the background.
  - The project's GitHub repository (from `github_project_configs`) is cloned into a temporary folder.
  - The server's `GITHUB_TOKEN` is passed only as an environment-level git header, never in the URL or the arguments.
  - The model and history state are stored in `risk_models`, and each run's evaluation goes to `risk_model_history`.
  - A second request while training is running gets 409. A run that is stuck for over 2 h counts as interrupted.
- `GET /api/risk-model/projects/{project_id}` returns the status, the selected model, the held-out AUC/F1, and whether it is used.
- The PR sync (`GitHubSyncService`) passes per-file additions and deletions, the git e-mail of the author of most commits, the commit messages and the creation time.
  - **The model is used only if its held-out AUC ≥ 0.65, with ≥ 200 labelled changes and ≥ 20 bug-introducing ones.**
  - The evidence then carries `scoring_method: "ml"`, `risk_score = round(100 × score)` and `ml_prediction` (score, model, AUC, top factors, all 14 features).
  - The rule result is kept as `rule_score` and `rule_factors`.
  - With no usable model, or if anything in the model path fails, the rules are used (`scoring_method: "rules"`).
  - During a retrain, the previous model keeps scoring.

## Rule fixes made at the same time

1. **Tests:** every synced PR got +15 "No passing tests", because test results are never passed in (the default was 0). Now `None` means unknown and adds nothing. A reported run with 0 passing still adds +15. The evidence shows `test_results_known`.
2. **Lines:** PRs loaded from the database never read `lines_added` / `lines_deleted`, so the churn rule could never fire. They are now read.

## Reproduce

```bash
python evaluation/evaluate_risk_model.py --repos <clone of httpx> <clone of requests> <clone of flask> --cache <dir>
# add --lightgbm when lightgbm and numpy are installed (reference only)
```

Tests: `tests/test_risk_model.py`. SZZ is tested on a small real git repository built during the test.
