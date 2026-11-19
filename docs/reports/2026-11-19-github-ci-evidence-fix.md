# GitHub check-run fallback repair

## Cause

GitHub PR metadata, files and commits were readable, but the commit check-runs endpoint returned HTTP 403. The exception fallback in [GitHubAPIService](../../backend/domain/services/github_api_service.py) returned a list. [GitHubNormalizer](../../backend/integrations/github/normalizer.py) expected a dictionary and called `.get()`, causing `AttributeError` and aborting PR synchronization.

## Repair

- The collector now returns a dictionary with an empty loaded-check list, explicit unavailable-evidence status and a safe failure reason.
- The normalizer preserves unknown CI status instead of reporting passing or failing CI from inaccessible evidence. Zero counts describe loaded checks, not an assertion that GitHub ran no checks.
- [GitHubSyncService](../../backend/domain/services/github_sync_service.py) persists the evidence availability and reason alongside the existing CI status. Previously unavailable metadata is cleared on a later successful refresh.
- Successful and genuinely empty check-run responses retain their existing behavior. Polling schedules, permission checks, scoring and AI dispatch were not changed.

## Verification

[Regression tests](../../backend/tests/test_github_check_evidence.py) first reproduced the list/dictionary mismatch and sync crash: 3 failed, 2 passed. After repair, the new tests plus existing GitHub client, poller, function-discovery integration and internal-agent-adapter tests passed: **88 passed, 33 existing deprecation warnings, exit 0**. Scoped Ruff and diff whitespace checks passed.

A read-only live check against the explicitly authorized TaskFlow lab repository verified that PR #3 metadata, 4 files and 1 commit were collected and normalized without the previous exception. CI remained `null`, with evidence marked `unavailable`. Full live PR synchronization was not manually triggered; its continuation was tested with mocked API/storage dependencies. No GitHub writes or live Ollama inference were performed for verification. The full backend suite was not run against the populated shared demo database.

GitHub returned `Resource not accessible by personal access token` and the response header `x-accepted-github-permissions: checks=read`. The token needs repository **Checks: Read** access before check-run evidence can be retrieved. Existing repository/PR read access does not imply this permission. Token permissions and stored credentials were not altered.

## Other log entries

The login and dashboard HTTP 200 entries are successful requests. The HTTP 409 from the legacy performance-evaluation endpoint is intentional: [the route](../../backend/api/routes/performance.py) returns the pending-period/scoring-policy response instead of generating an unapproved employee rating. That safeguard was preserved.

Changes remain uncommitted. Earlier TaskFlow setup and dashboard fixes remain in the working tree unchanged.
