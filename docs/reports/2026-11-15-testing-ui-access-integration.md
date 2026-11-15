# Testing integration — UI and access preservation

Date: 2026-11-15. Local integration only; no push, deployment or production activation.

## Histories integrated

- Remote UI/access baseline: `ca36e9e24673c3831f3b027e073d6d8dd02b417a`.
- Reviewed local scoring/stabilization/multi-agent history:
  `57349384c0667979005551aea276e7815ff97898`.
- Common ancestor: `c8544337af8451ae4a46915f399959df877bc4ec`.

The local history includes all seven specialist/multi-agent branches shown by the
user, the earlier scoring integration and the successful Hypothesis verification
report. Remote testing had advanced by 23 commits. A preliminary merge was aborted
without discarding either history. After the user clarified that those UI and role
fixes must be preserved, both histories were reconciled on the temporary
`codex/testing-integration-2026-11-15` branch before updating local testing.
The containing merge commit identifies the final integration.

## Conflict decisions

Eleven files required conflict resolution. The newer login, app shell, dashboards,
charts, permission definitions and shared route-access policy were retained. Git
comparison confirmed no changes from the remote baseline in the authentication UI,
layout/chart modules, primary styles, backend authorization/permission definitions
or authentication service.

- The main application registers both the newer reports router and the separate
  disabled manual PR workflow router/lifecycle.
- The API client retains newer readable validation messages and `.status` behavior,
  while preserving sanitized `.response.status` for the reviewed advisory/scoring
  readers. Raw request configuration, authorization headers and submitted notes
  are not attached to normalized errors.
- Existing Performance and Feedback pages remain the newer default views, with
  their existing eligibility rules and original regression files unchanged.
  The reviewed governed records and assigned-observation flows are retained at
  `/performance/assessments` and `/feedback/assignments`, linked from those pages
  and guarded by the same permission-based page rules. Their original regression
  assertions were retained under the corresponding view names.
- The score card retains the newer card layout and displays explicit assessment
  authority labels; approved metadata takes precedence over historical numbers.
  Numerical scoring formulas, policies and activation gates were not changed.
- GitHub configuration/sync action visibility follows the newer permissions. The
  manual advisory panel is an additional mount and now consumes the backend's
  permission list instead of the retired frontend role-matrix calling convention.

## Authorization reconciliation

An initial integration-specific test reproduced two unsafe mismatches in the older
AI adapter: PMs could enumerate unassigned projects in their organization, and a
CEO with a specified organization could enumerate another organization. Both now
follow the newer boundaries: PM project IDs are restricted to their assignments;
an established organization restricts all project queries. Private ownership,
provenance and current-account/revocation enforcement remain intact.

The newer permissions intentionally remove engineering-AI triggering from CEO/HR
and do not grant it merely through administrator status. The older provider/API
tests had used a CEO to exercise inference, and HR admin to bypass the old guard.
They now use an authorized Lead for inference/failure persistence and explicitly
assert denial, no model call and no persistence for the prohibited HR-admin case.
All six legacy task identifiers/node contracts remain covered. The generic
engineering endpoint's stricter access was not weakened to satisfy old fixtures.

Older PM/unscoped-CEO read expectations were aligned with the newer restrictions,
including an additional positive assigned-PM case. The existing route-module
`has_org_access` helper export was preserved for compatibility with the upstream
org-wide-read contract. GitHub report-rendering tests now use the actual
`SYNC_PR` permission holder (Developer), rather than assuming Lead/DevOps may use
that action. No new permissions or administrator bypasses were introduced.

## Executed verification

| Check | Result |
| --- | --- |
| Final full backend, normal Hypothesis plugin, real MongoDB opt-in | **3,652 passed, 111 skipped, 210 warnings**, 96.77 s; exit **0** |
| Final full frontend, one worker | **334 passed**, 50 files, 146.49 s; exit **0** |
| Focused backend integration/access/API checks | **181 passed**, 86 warnings, 6.11 s |
| Focused frontend report/guard/score checks | **13 passed**, four files, 8.17 s |
| Frontend production build | **Passed**, 2,067 modules; no deployment |
| Frontend lint | Exit **0**, 13 warnings in the combined histories, no errors |
| Scoped Python lint and backend `F821,E9` | **Passed** |
| Scoped access/evidence/runtime/API Mypy | **Passed**, four files |
| Backend feature flags | Internal **False**, manual **False** |

The full backend includes all existing role, project, tenant, employee, approval,
HR, scoring, algorithm, webhook, single-agent and PR-workflow regressions. The four
real-Mongo PR workflow tests ran with their established test-owned collections.
Hypothesis imported and its properties ran normally; neither its plugin nor
collection-error enforcement was disabled. The 111 existing opt-in Docker cases
remain skipped, not counted as passes.

New integration tests cover managed-PM and CEO-organization boundaries, the absence
of an admin engineering-AI bypass, forbidden assigned-feedback routing, authorized
reviewer access, PM performance URL tampering and authoritative score display.
The newer default-page eligibility tests were kept alongside the governed-view
tests, rather than replacing one set with the other.

Earlier combined runs were not green: the backend had **46 failures** (43 older
provider/API actor assumptions, two older scope expectations, one helper-export
contract), with 3,602 passes and 111 skips. The frontend had **five failures** in
the older GitHub report fixture, with 325 passes. A subsequent targeted check also
confirmed DevOps lacks `SYNC_PR`; the fixture was corrected to the actual permitted
actor. These failures led to the documented narrow integration changes. No test
was skipped, deadline relaxed or production permission broadened to obtain green
results. Existing jsdom navigation diagnostics appeared without assertion failures.

## Boundaries and remaining limits

Both multi-agent backend flags remain false; the frontend opt-in defaults false.
The manual workflow remains advisory and blocked outside development/test. No
automatic GitHub trigger, source execution, merge/deployment authority, scoring
activation or new infrastructure was introduced. Live GitHub/Ollama quality,
inference load, Docker benchmarks, replica-set failover and an authenticated visual
browser acceptance pass remain unverified.

The complete merged tree was tested before advancing local testing. Unrelated
untracked editor/audit/scratch files were preserved and excluded from the merge.
Nothing was force-pushed or published. This report supports the local integration;
it is not a production rollout approval.
