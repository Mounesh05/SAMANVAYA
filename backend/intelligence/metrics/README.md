# Code-quality metrics (Intelligence Engine)

Branch: `feature/code-quality-metrics` (based on `testing`). This document is for reviewers.

## What this branch adds

SAMANVAYA's own implementation of six standard code-quality metrics, connected to the
Python analyzer and the QualityEngine, plus scripts that check the numbers against
established tools.

- **Own code, published algorithms.** Every metric is implemented from scratch with the
  Python standard library only (`ast`, `tokenize`). No radon, lizard or SonarQube at runtime.
- **Deterministic.** The same code always gives the same numbers, so results can be
  reproduced and verified.
- **Explainable.** Cognitive complexity records the reason for every point
  (`line 12: if (nesting 2) = +3`), so the AI agents can cite exact evidence.
- **Validated.** Cyclomatic complexity matches radon on 99.9% of 863 functions, and 100% once
  documented rule differences are accounted for (see *Validation* below).

## The six metrics

| # | Metric | Algorithm | Module | Limit / bands |
|---|---|---|---|---|
| 1 | Cyclomatic complexity | McCabe (1976): 1 + decision points | `cyclomatic.py` | ≤10 low, 11–20 moderate, 21–50 high, >50 very high |
| 2 | Cognitive complexity | SonarSource (Campbell, 2017): flow breaks + nesting + boolean sequences | `cognitive.py` | ≤7 low, 8–15 moderate, >15 high (SonarQube's limit) |
| 3 | Duplication | Token windows + Rabin–Karp rolling hash (Karp & Rabin, 1987), like PMD CPD | `duplication.py` | ≥100 tokens over ≥10 lines (SonarQube's rule of thumb) |
| 4 | Maintainability index | Oman & Hagemeister (1992), Visual Studio 0–100 scale; token-based Halstead (1977) | `maintainability.py` | ≥20 high, 10–19 moderate, <10 low |
| 5 | Issues per 1,000 lines | issues ÷ (NCLOC ÷ 1000), plus a severity-weighted version | `issues.py` | — |
| 6 | Technical debt + rating | SQALE (Letouzey, 2012): debt ratio = debt ÷ (NCLOC × 30 min) | `debt.py` | A ≤5%, B ≤10%, C ≤20%, D ≤50%, E >50% |

Supporting modules:
- `size.py`: line counts. **NCLOC** (code lines without comments, blank lines or docstrings) is the
  single denominator every metric uses.
- `project.py`: runs all six metrics over a set of files (`analyze_paths`, `analyze_sources`).

Each module's docstring lists its exact counting rules, including choices for Python constructs
the original papers do not cover (comprehensions, `match`, `for…else`).

Duplication finds exact copies (type 1) and copies with renamed identifiers or changed literals
(type 2, `normalize=True`, the default). It does not find copies with added/removed lines (type 3)
or different code with the same behaviour (type 4).

## How it is connected

```
PythonAnalyzer.analyze()                        intelligence/analyzers/python/analyzer.py
  ├─ ruff / mypy / bandit / secrets / tests / architecture   (unchanged)
  └─ apply_code_metrics()                       intelligence/analyzers/common/code_metrics.py
       ├─ runs the six metrics on the changed .py files (in a worker thread)
       ├─ fills evidence.metrics                CodeMetricsEvidence (evidence/models.py)
       ├─ replaces evidence.complexity numbers and evidence.duplication
       └─ counts the analyzers' findings as issues
                    │
                    ▼
QualityEngine.calculate()                       intelligence/quality_engine.py
  ├─ complexity penalty = max(old cyclomatic-average penalty,
  │                           readability penalty: % of function code above cognitive 15,
  │                           50% → maximum penalty)
  └─ result["maintainability"]: rating, debt, MI, issue density   (reported, not weighted)
```

- **Backward compatible.** Without `evidence.metrics` (non-Python files) the engine score is
  calculated exactly as before. The stored weight configuration is untouched: the new
  maintainability section is reported, not given a weight, because the weights must sum to 1.
- **Multi-language PRs.** `EvidenceMerger` keeps `metrics` from the Python analyzer.
- **Path safety.** `apply_code_metrics` only reads files that resolve inside the repository.
  `../x.py` or absolute paths elsewhere are rejected and listed in `metrics.files_rejected`.
- Paths in metric results always use `/`, so they match analyzer findings on Windows too.

## Behaviour changes reviewers should check

1. **Quality scores go down for complex code.** The old complexity penalty only used the
   average cyclomatic complexity, which hides a few very complex functions. On SAMANVAYA's own code:

   | Files | Before | After |
   |---|---|---|
   | 4 most complex files (`evaluation.py`, `workflow_service.py`, `risk_engine.py`, `security.py`) | 92 / A | 74 / C |
   | 4 ordinary files | 96 / A | 86 / B |

   The scale (`QualityEngine.MAX_HARD_TO_READ_SHARE = 50.0`) is a design choice, not an industry
   standard. Tune it after the SonarQube comparison.
2. **Duplication numbers change.** The old line-based detector is replaced for Python by the
   token-based one, and density now uses NCLOC.
3. **Complexity evidence changes.** `average_complexity`, `max_complexity`,
   `high_complexity_functions`, `lines_of_code` and `avg_function_length` now come from our
   metrics for Python. `comment_ratio` and `avg_nesting_depth` are kept from the old analyzer.

## Results on SAMANVAYA's backend

At this commit: 167 files, excluding `tests`, `evaluation` and `intelligence/metrics`.

| Metric | Value |
|---|---|
| Code lines (NCLOC) / functions | 19,930 / 863 |
| Cyclomatic: average / max | 3.90 / 63 (`_run_ai_evaluation` in `api/routes/evaluation.py`) |
| Cognitive: average / max | 3.65 / 71 (same function); 42 functions above 15 |
| Maintainability index: file average / function average | 17.54 / 53.17 |
| Duplication | 9.75% (49 copies; 1.54% counting exact copies only) |
| Issues per 1,000 lines | 4.57 (42 complexity, 49 duplicated blocks) |
| Technical debt | 2d 2h 13min, ratio 0.18%, rating **A** |

The rating A only reflects the rules SAMANVAYA implements (complexity and duplication). With ruff
and bandit installed, their findings are added automatically. SonarQube applies hundreds of
rules, so expect a higher debt there.

Notable findings in the code:
- `domain/services/workflow_service.py`: `transition_task` (lines 51–160) and `transition_story`
  (162–271) are the same 110-line method with "task" renamed to "story".
- `api/routes/employees.py`: the same `EmployeeResponse(...)` construction is repeated field by field.

## Validation against reference tools

Script: `backend/evaluation/compare_reference_tools.py`. Report:
`backend/evaluation/results/reference_comparison.md`.

| Metric | Reference | Exact match | After documented rule differences |
|---|---|---|---|
| Cyclomatic | radon 6.0.1 | 99.9% of 863 functions | 100% |
| Cyclomatic | lizard 1.17.10 | 99.1% | 100% |
| Cognitive | cognitive_complexity 1.3.0 | 82.1% of 855 | 100% on the 698 functions both tools score by the same rules |
| MI formula | radon, using radon's own inputs | 100% identical (with radon's comment constant 2.46) | — |

Every disagreement was checked:
- **radon** adds +1 for `assert`, `try…else` and loop `else`, which are not branches.
- **lizard** reads tokens, not syntax: it misses decisions inside f-strings, counts `finally`
  and does not understand `match`.
- **cognitive_complexity** deviates from SonarSource's specification. Each case was confirmed with
  small test functions: it ignores `async for`, comprehensions and `match`; it scores `else:` +
  nested `if` like `elif`; and it misses the nesting penalty in a branch followed by `elif`.
- MI values differ from radon **by design** (radon uses logical lines, operator-only Halstead and
  always adds a comment bonus). Our formula gives radon's exact numbers when given radon's inputs.

## Open items

- [ ] **Run jscpd and SonarQube** for duplication and technical debt. Scripts and step-by-step
      commands are in `backend/evaluation/README.md`. They need Node.js / Docker, and a SonarQube
      token created in its web UI.
- [ ] **Label the 42 renamed-copy pairs** (normalized-only clones) as real or false alarm to
      measure their precision. A sample showed both real copies and false alarms on data models
      with similar field lists.
- [ ] **Tune `MAX_HARD_TO_READ_SHARE`** in the QualityEngine with the SonarQube results.
- [ ] **Python only.** Other languages still use the existing tool-based analyzers.
- [ ] **Existing bug, not fixed on this branch:** `domain/services/github_analysis_service.py`
      (around line 324) builds `QualityBreakdown` from engine score keys that do not exist
      (`correctness`, `maintainability`, `security`, `performance`, `readability`), so they are always 0.
      `testing` and `architecture` arrive on a 0–100 scale while the model allows at most 15 and 10,
      which raises a `ValidationError`. The deep PR analysis from GitHub sync therefore never
      produces a code-quality report.
- [ ] **Weak score inputs, existing:** the TESTING dimension only reads a leftover `.coverage` file
      (nothing runs the tests with coverage), and ARCHITECTURE is two text rules. Together they are
      45% of the quality score.

## Running the tests

New tests: `test_metrics_*.py` (cyclomatic, cognitive, duplication, maintainability, issues/debt),
`test_code_metrics_integration.py`, `test_evaluation_external.py`. 151 tests in total.

With the backend requirements installed (`pip install -r backend/requirements.txt`), from `backend/`:

```bash
python -m pytest tests/test_metrics_*.py tests/test_code_metrics_integration.py tests/test_evaluation_external.py
```

Without the full requirements (for example without `mongomock_motor`), skip the shared test
setup. The metric tests only need the standard library, pytest, pytest-asyncio and pydantic:

```bash
SECRET_KEY=test python -m pytest tests/test_metrics_*.py tests/test_code_metrics_integration.py tests/test_evaluation_external.py --noconftest
```

Existing tests that touch the changed code also pass on this branch: `test_quality_engine.py`,
`test_risk_engine.py`, `test_contribution_credit.py`, `test_evaluation_validation.py`,
`test_github_client.py`.

## Using the metrics directly

```python
from intelligence.metrics import analyze_paths

summary = analyze_paths(paths, root="path/to/repo")
summary.to_dict()        # project totals + per-file results
summary.functions        # per-function cyclomatic, cognitive, MI, code lines
summary.issues           # issues and density
summary.debt             # debt, ratio, rating
```
