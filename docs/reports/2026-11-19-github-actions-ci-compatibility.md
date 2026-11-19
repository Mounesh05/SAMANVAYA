# GitHub Actions CI evidence compatibility

## Outcome

**TaskFlow CI evidence collection is ready for controlled local testing with the existing token.** An authenticated PR #4 sync returned HTTP 200, persisted two exact-commit workflow runs and four jobs, and returned a matching normalized evidence digest. GitHub reported successful outcomes. SAMANVAYA did not manufacture check-run records, executed-test counts, correctness guarantees or an all-provider CI pass.

Branch: `testing`. Base HEAD: `9e156526851f314c4d7344ecb1c2c571e8b2dadc`. The working tree already contained the separate PR-visibility repair when this task started; it was preserved. Nothing was committed, pushed, merged or deployed for this task.

## Exact 403 and permission verification

The failing request is:

`GET /repos/{owner}/{repo}/commits/{head_sha}/check-runs`

For the configured TaskFlow repository and PR #4 head `8ad02ac50587c6bb668dc480ae68efdc9f411b68`, GitHub returned HTTP 403 with `Resource not accessible by personal access token`. The accepted-permission response header identifies `checks=read`. The same configured token successfully read:

- `GET /repos/{owner}/{repo}/actions/runs?head_sha={exact_sha}` — HTTP 200, `actions=read` accepted-permission header.
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs` — HTTP 200.

This establishes a Checks-specific access denial and working Actions read access for this token. It does not establish a universal inability of every fine-grained PAT to use Checks: [GitHub's Checks documentation](https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference) lists fine-grained token support. No broader permission or replacement token was requested. [Workflow-run reads](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-repository) and [job reads](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt) use Actions read permission. Token values, passwords and authorization headers were not printed or stored in reports.

## Before and after

| Situation | Previous behavior | Current behavior |
| --- | --- | --- |
| Checks allowed, including an authorized App token | Existing Checks normalization | Preserved; no Actions permission is additionally required |
| Checks denied, Actions readable | PR sync continued but CI evidence was unavailable | PR sync continues and separately collects Actions observations |
| Workflow success | No Actions evidence path | Explicit GitHub-reported outcome; no synthetic check runs or test results |
| Third-party checks inaccessible | Generic missing CI indication | Non-Actions provider coverage explicitly unavailable, never assumed passed |
| No exact-head Actions runs | No fallback | Explicit `missing` Actions evidence; no branch/latest-run substitution |
| Rate limits / transient errors | Generic optional-evidence failure | Permission, rate-limit, transient and malformed-response conditions remain distinct |

## Collection and provenance

- Added versioned `github-actions-ci-v1` snapshots under `github_actions_ci` in stored/returned PR data and `actions_ci` in the GitHub evidence-fetch result.
- Run queries retain the exact SHA on every page. Every run must identify the expected repository, commit, workflow ID, run ID and positive attempt number. Unexpected scopes are rejected before fetching their jobs.
- Jobs are fetched using the run-attempt endpoint, not whichever attempt is latest later. Job ID, run ID, SHA, run URL/repository and any returned attempt field must match. The attempt-specific request also pins identity where GitHub omits an attempt field.
- Only allowlisted outcome/identity fields are retained, with canonical API references, retrieval time, source authority `GITHUB_REPORTED_OUTCOME`, verification scope `SOURCE_IDENTITY_ONLY`, and a SHA-256 digest of the normalized snapshot. The digest is traceability/integrity metadata, not a GitHub signature or independent correctness proof.
- Multiple matching runs are retained separately, not collapsed into extra independent votes. Failed, timed-out, cancelled, queued, neutral and skipped states do not become successful tests. Incomplete collection produces an unknown summary.
- Collection is bounded to three pages per resource (100 records per page) and twenty run records. Truncation, duplicate identities, malformed results, job outages and identity mismatches are explicit partial/unavailable conditions. No success summary is emitted for partial evidence.
- Transient transport/server failures receive one short retry. Permission failures are not retried. Rate-limited reads are deferred; a rate limit encountered on Checks does not immediately spend more requests on Actions. Retry/reset metadata is retained where supplied. Recovery occurs on a later normal sync; this task adds no queue or scheduler.
- The public sync route now also binds an explicit project ID to its server-stored repository link before any GitHub fetch. This closes a reproduced cross-repository provenance gap. Role grants, authentication, project-membership and organization checks remain unchanged. Configured legitimate syncs still work; arbitrary repositories cannot be attached to an authorized project by request fields alone.

## Downstream compatibility

Existing `check_runs` records remain actual Checks API records. The new fallback does not insert workflow jobs into that list. Existing `ci_status` remains null when Checks is inaccessible; Actions success cannot silently become a universal CI pass. Provider-specific data, partial coverage and limitations are additive.

The PR UI shows `Actions: success` (or another reported outcome) with an explicit non-Actions coverage limitation and a correctness disclaimer. Missing/partial evidence remains distinguishable from a genuine GitHub-reported failure. Existing personal/project PR visibility behavior is preserved.

The legacy evaluation manifest's check-run citation rules and multi-agent workflow's recorded-CI-submission contracts were not broadened. Actions observations are not silently promoted into those stronger proof categories. Scoring formulas, policies, algorithm intelligence, task-transition logic, authentication and feature flags were not changed.

## Files changed for this task

| File | Purpose |
| --- | --- |
| [GitHub client](../../backend/integrations/github/client.py) | Read-only exact-SHA workflow queries and run-attempt job queries |
| [CI evidence collector](../../backend/integrations/github/ci_evidence.py) | Bounds, scope validation, outcomes, provenance, failure classification and retries |
| [GitHub API service](../../backend/domain/services/github_api_service.py) | Actions fallback and separate evidence result |
| [GitHub normalizer](../../backend/integrations/github/normalizer.py) | Provider-separated CI summary; earlier review-status fix preserved |
| [Sync service](../../backend/domain/services/github_sync_service.py) | Persist and return the versioned snapshot |
| [PR model](../../backend/domain/models/pull_request.py) | Additive source/coverage metadata |
| [GitHub routes](../../backend/api/routes/github.py) | Verify project-to-repository binding before collection |
| [Actions regressions](../../backend/tests/test_github_actions_evidence.py) | Thirty evidence and isolation cases |
| [Existing developer tests](../../backend/tests/test_developer_access.py) | Supply the real repository-link prerequisite in the positive sync fixture |
| [PR screen](../../frontend/src/pages/pull-requests/PullRequestsPage.jsx) | Source-specific Actions outcome and coverage label |
| [PR screen tests](../../frontend/src/pages/pull-requests/PullRequestsPage.test.jsx) | Prevent an Actions success from appearing as an all-provider pass |
| This report | Verification and remaining limits |

Other PR-visibility changes and unrelated untracked workspace files predate this task; they were not removed or included in a commit.

## Tests executed

| Check | Result |
| --- | --- |
| New collector tests before implementation | 22 failed because the collector did not exist |
| Final new Actions regression module | **30 passed** |
| Combined backend: Actions, Checks, client, poller, discovery, internal adapters, developer access, PR identity, dashboard scope, existing algorithm workflow, multi-agent orchestration, manual API and durability tests | **303 passed, 1 skipped, 37 warnings; exit 0** |
| Relevant frontend tests, four files | **24 passed; exit 0** |
| Production frontend build | Passed |
| Frontend lint | Exit 0, existing warnings |
| Scoped Ruff | Passed |
| Mypy on the new collector | Passed, one source file |
| Editor diagnostics on collector/API/route/UI | No errors reported |
| Diff whitespace | Passed |

The skipped case is the existing opt-in real-Mongo manual workflow API test in `test_pr_workflow_api.py`, gated by `SAMANVAYA_MONGO_TESTS=1`. It was not enabled against the populated shared demo database. The full backend suite was not run. No skipped test was relabeled as passed.

New coverage includes fine-grained-PAT fallback, Checks 403, authorized-App Checks retention, run/job success, failed/cancelled/pending states, multiple runs, no matching evidence, inaccessible non-Actions coverage, cross-repository/commit/job/attempt rejection, cross-project and cross-organization denial, rate limits, transient retry, malformed data, bounds and existing sync behavior. The first cross-scope fixture patched an instance method and interfered with a later test; it was corrected to patch the class, and the mixed suites were rerun successfully. A genuine explicit-project cross-repository gap was reproduced as HTTP 200 before repair and HTTP 403 afterward.

## Live TaskFlow verification

- Authorized repository: `Mounesh05/taskflow-samanvaya-lab`.
- Project: `PRJ-A7E48B66`; PR: `4`; exact head: `8ad02ac50587c6bb668dc480ae68efdc9f411b68`.
- Two matching workflow runs were returned, including run IDs `44521347474` and `44521183772`, attempt 1, with four validated job observations in total.
- Actions collection status: available; GitHub-reported outcome: success.
- Checks failure classification: permission denied; non-Actions providers: unavailable; all-provider `ci_status`: null.
- Real local HTTP login and authorized sync with `use_ai=false`: **HTTP 200**. The stored snapshot's content digest matched the returned snapshot through the authorized project PR-list API. The verification session was logged out.
- No GitHub write, workflow execution/rerun, merge, deployment or model inference was requested for verification. No test cases or test-pass counts were inferred from job names or workflow success.

The previously shared browser tab was no longer available at the final refresh attempt, so a fresh visual walkthrough of this new CI cell is not claimed. Component tests, production build and authenticated API/persistence checks completed successfully.

## Remaining limits and readiness

TaskFlow is ready for **controlled Actions CI evidence testing** with the current read-only token. Checks may still return a permission-denied probe; that no longer prevents ordinary Actions observations. Third-party checks cannot be enumerated or certified through Actions and remain explicitly unavailable. No broader permission is necessary for the tested path.

Only exact-head evidence is accepted: workflows whose API SHA belongs only to a merge commit or another revision are not substituted. Required-workflow policy, branch protection, test correctness, artifacts/log parsing and production readiness are not established by workflow/job outcomes. A snapshot describes the recorded run attempts at collection time; it is not a guarantee that no later rerun or provider update exists.

Partial or bounded collections need a later refresh or separately scoped inspection. No arbitrary live scoring, algorithm benchmarking or multi-agent activation was introduced. Stop after this verification; no automatic merge or deployment.
