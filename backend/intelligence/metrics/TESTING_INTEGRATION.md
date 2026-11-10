# Design: feeding the testing metrics into SAMANVAYA

Status: **proposal for team review**. The metrics themselves are implemented and tested
(`intelligence/metrics/testing.py`, `tests/test_metrics_testing.py`). Nothing below is
implemented yet, because it changes the contract between SAMANVAYA and the CI workflows it
installs in project repositories.

## Why

The QualityEngine's TESTING dimension carries **25% of the quality score**, but today it is
almost always empty:

| What | Today | Where |
|---|---|---|
| Coverage | Only read if a leftover `.coverage` file exists where the analyzer runs; nothing produces one | `PythonAnalyzer._testing()` |
| Test results | CI uploads **suite totals only** ("412 passed, 3 failed") | `ci/upload_junit_results.py` → `POST /api/qa/test-runs` |
| Re-runs | A re-run on the same commit **overwrites** the earlier result (id = repo + commit + suite) | `api/routes/qa_test_runs.py` |
| Flaky tests | Not detectable: no per-test history, and retries are lost | — |
| Engine penalty | Coverage below 80% only; no coverage → no penalty | `QualityEngine._testing_penalty()` |

## What the new metrics need

| Metric | Input | Function |
|---|---|---|
| Line / branch coverage | Cobertura XML or LCOV from CI | `parse_coverage()` |
| Diff coverage (changed lines only) | coverage + the PR's unified diff | `parse_unified_diff()`, `diff_coverage()` |
| Pass rate | per-test JUnit results | `parse_junit()`, `pass_rate()` |
| Flaky tests | per-test results **across runs, including retries** | `classify_tests()`, `flakiness()` |
| Bug density | QA defects + code lines (NCLOC) | `bug_density()` |

## Proposed changes

### 1. CI scripts (in the project repositories)

`ci/run_tests.sh`
- Python: `pytest --junitxml=... --cov --cov-branch --cov-report=xml` when `pytest-cov` is installed.
- vitest / jest: add the `cobertura` (or `lcov`) coverage reporter.
- Maven / Gradle: JaCoCo XML, converted to Cobertura, or added as a later step.

`ci/upload_junit_results.py` gains optional fields, so old SAMANVAYA servers keep working:
- `run_id`, `run_attempt` from `GITHUB_RUN_ID` / `GITHUB_RUN_ATTEMPT`, so retries are kept, not overwritten.
- `test_cases`: `[{id, status, duration}]` from the JUnit XML (capped, e.g. 10,000 per run).
- `coverage`: totals, plus covered/uncovered **line ranges for the files changed in the PR only**,
  so the payload stays small.
- `changed_lines`: the PR's changed-line ranges from `git diff -U0 origin/$GITHUB_BASE_REF...HEAD`
  (pull requests only).

**Note:** `domain/services/qa_workflow_provisioning_service.py` embeds its own copies of both
scripts (`_run_tests_script_content()`, `_upload_script_content()`) and the workflow YAML.
Every change must be made there **and** in `ci/`. Better: generate the embedded copies from the
files in `ci/` so they cannot drift apart.

### 2. API: `POST /api/qa/test-runs`

- `TestRunSubmission` gets the optional fields above (validated sizes; same token check).
- Record id includes `run_id` and `run_attempt`.
- Per-test results go to a new collection `test_case_runs`, one document per test per run:
  `{project_id, repository, branch, commit_sha, run_id, run_attempt, test_id, status, duration, created_at}`,
  indexed on `(project_id, test_id, created_at)`, with a retention period (for example 90 days).
- Coverage summary and changed-line coverage are stored on the run document.

### 3. Metrics and evidence

- A small service builds `TestRunRecord` history from `test_case_runs` and calls `flakiness()`;
  computes `diff_coverage()` for a PR from the run of its head commit; and `bug_density()` from
  the project's defects and NCLOC.
- `TestingEvidence` already has `coverage_percentage` and `changed_code_coverage` (unused today).
  Add `pass_rate`, `flaky_tests` and `flaky_test_ids`.
- `PythonAnalyzer._testing()` reads these from the stored CI results instead of a local `.coverage`.

### 4. QualityEngine testing penalty

Today: overall coverage gap below 80%. Proposed: the **largest** of
- overall coverage gap below 80% (unchanged)
- **diff coverage gap below 80%**: SonarQube's default quality gate also requires 80% coverage
  on new code
- failing tests: a share of failed tests
- flaky tests: a smaller penalty per flaky test

As today, missing data gives no penalty but lowers the analysis confidence, so a project
without coverage data is not punished as if it had 0%.

Bug density goes into the reported (unweighted) section next to maintainability, like the
technical debt.

## Questions for the team

1. Is it OK to change the CI contract and re-provision the workflow in existing project repositories?
2. Should `pytest-cov` (and coverage reporters for JS) be required, or used only when present?
3. Retention for per-test history: 90 days?
4. Diff-coverage target: 80% (SonarQube's default for new code)?
5. Generate the provisioning service's embedded scripts from `ci/` (removes the duplicated copies)?
