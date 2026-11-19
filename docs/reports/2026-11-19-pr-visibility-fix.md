# Pull-request visibility and review-queue repair

Initial investigation base: `9e156526851f314c4d7344ecb1c2c571e8b2dadc`, branch `testing`. The initial verification below is historical; the final checkpoint review is recorded separately below.

## What actually happened

The supplied log recorded a successful PR #4 sync and no failed poller syncs. MongoDB inspection confirmed PRs 1–4 were already stored, with #4 open. The frontend empty list was not proof of failed processing.

The Developer personal endpoint searched for `author_id=MOUNESH`, while the imported PR author was `Mounesh05`. All synthetic accounts had null GitHub identity mappings. The Lead dashboard/review queue also compared imported author IDs with employee IDs. Additionally, the normalizer treated GitHub `mergeable_state=clean` as human review approval, removing open PR #4 from the pending queue.

The forbidden requests in this log were remote GitHub check-run reads. They do not grant or remove local project rights, and missing CI evidence no longer aborts synchronization. GitHub still requires `checks=read` permission for that evidence.

## Changes

- [PR repository](../../backend/repositories/pr_repository.py): added current employee-to-stored-GitHub identity lookup, preserving legacy employee-ID authors. Matching is case insensitive for explicit GitHub logins and scoped to current organization and assigned/team projects. Names are never used to guess identity.
- [Developer endpoints](../../backend/api/roles/developer.py): personal list and dashboard use the same scoped lookup.
- [Lead endpoints](../../backend/api/roles/lead.py): read PRs of the Lead's team or explicitly assigned projects in the current organization, independently of author mappings.
- [Normalizer](../../backend/integrations/github/normalizer.py): mergeability no longer invents approval or changes-requested evidence. Without independently loaded review evidence, status remains pending. This does not certify actual review completion or branch-protection satisfaction.
- [PR screen](../../frontend/src/pages/pull-requests/PullRequestsPage.jsx): unlinked developers see an explicitly labeled authorized project view and identity-link explanation. Explicitly linked developers retain the personal view. Account-scoped cache keys, project-loading/error handling, actual GitHub author fields, external links and unavailable CI display were corrected. Pending-review counts now exclude merged/closed PRs; the browser-found defect was reproduced before repair.
- Existing frontend test account data now explicitly declares a GitHub link when testing the linked personal-view behavior. New regressions cover unlinked fallback and CI/author display.

## Executed verification

- Backend reproductions: missing identity-query support and mergeability-derived false approval reproduced before repair.
- Frontend reproduction: unlinked developer failed to display the existing project PR before repair.
- Final focused backend suite: **145 passed**, 37 existing deprecation warnings, exit 0. Includes identity/tenant/project boundaries, team queue, developer authorization, GitHub client/check-evidence/poller, discovery and internal adapters.
- Final focused frontend suite: **18 passed** across three files, exit 0, including the additional pending-review counter regression.
- Production frontend build: passed. Frontend lint: exit 0 with existing warnings. Scoped Ruff and diff whitespace checks: passed.
- Actual local HTTP login using the synthetic developer, followed by `POST /api/github/sync-pr` for lab PR #4 with `use_ai=false`: **200**, `PR synced successfully`, AI result null, review pending, CI evidence explicitly unavailable due to HTTP 403.
- The same developer's authorized project-PR endpoint returned **[4, 3, 2, 1]**.
- Actual synthetic Lead login and review-queue request returned **[4]**.
- Synthetic API test sessions were logged out. No GitHub writes, token changes, permission grants, live AI inference or multi-agent activation were performed by these verification requests. Existing background application behavior was not redesigned.

An initial live request hit a backend connection reset during development reload; health returned 200 afterward, and the complete request was rerun successfully. The frontend was initially unreachable, so a local IPv4 Vite server was started. Automatic approval review initially rejected the credential-loading method because it would serialize passwords to tool output; that rejected command did not execute. The user then manually approved that exact action, and the credentials were consumed in tool orchestration without printing their result in chat. A real browser login was completed: all four PRs, one open and three merged, appeared with correct authors and explicit unavailable CI. PR #4's existing algorithm report opened and displayed 18 analyzed functions and zero validated comparisons. New functions lacked a previous lexical match and an approved applicable contract, so no replacement conclusion was fabricated. This is successful inspection, not proof of behavioral compatibility.

## Remaining limits

- Checks API permission failures remain distinct from unavailable CI evidence. The separately committed [Actions compatibility fix](./2026-11-19-github-actions-ci-compatibility.md) now collects exact-revision Actions outcomes when accessible; these are GitHub-reported Actions results, not fabricated check-run records or proof about third-party providers. Broader permissions are not required for that fallback.
- Proposed synthetic GitHub identity links were presented for confirmation. No identity mapping or credential file was changed without confirmation. Until an explicit link is saved through employee administration, the developer sees the authorized project view rather than being falsely assigned PR authorship.
- The full backend suite was not run against the populated shared demo database. No universal authorization/security certification is claimed from these focused checks.
- No commit or push was performed during the initial investigation. The final local checkpoint is described below; no push or merge is authorized.

## Final PR-visibility checkpoint review

Reviewed on `fix/verification-defects` from security checkpoint `e69d87c4e16f5b0cdf290cbe3fb3cb8108460ceb`. Independent source re-review found no remaining blocking defect after the following narrowly scoped corrections.

- New regressions reproduced five backend scope failures involving ambiguous project/PR tenant metadata, MongoDB scalar/array matching and an omitted explicitly assigned Lead project. Project provenance now requires a scalar organization with no conflicting alias; PR queries reject array project identifiers and conflicting/array tenant metadata before returning results. Team identity alone cannot cross the organization boundary. Missing PR-level tenant fields inherit only a validated owning project's scope; conflicting explicit metadata is rejected.
- A separate signed-account regression reproduced missing-organization access through the project fallback. The read-only [project PR endpoint](../../backend/api/routes/github.py) now fails closed without an organization. This two-line guard and the existing [QA access test](../../backend/tests/test_qa_access.py)'s realistic tenant/project fixture are necessary additions to the original six-file slice. Synchronization and CI collection are unchanged.
- Assigned Leads can use the review queue even without a team. The dashboard's separate team-workload requirement remains unchanged. Same-organization Developer, Lead and QA project reads pass; cross-organization reads and missing-organization accounts are denied. PM and HR technical PR reads remain denied by the established permission contract. Inactive mapped accounts fail closed; explicit GitHub mappings use escaped literal matching and never grant project membership.
- A frontend regression reproduced whitespace-only GitHub identities incorrectly selecting the personal view. These now use the clearly labeled authorized-project fallback. Added tests cover empty projects, denied responses and partial CI state. Test-only retry delay is zero; production retry behavior is unchanged.

Fresh verification (all executed successfully):

- Backend: **322 passed, 0 failed, 0 skipped**, exit 0; 20 existing deprecation/collection warnings. Covers PR identity/repository/CAS behavior, Developer/Lead/PM/QA/DevOps authorization, project and tenant scope, normalization, GitHub client/Checks/Actions/poller, algorithm-intelligence and dashboard/session compatibility. All tests used in-memory MongoDB, with the application database provider replaced before imports.
- Frontend: **58 passed across 8 files, 0 failed, 0 skipped**, exit 0. Includes PR page, Actions display, Developer/Lead/PM/QA access and algorithm report regressions.
- Scoped Ruff passed (the existing route/test import-order rule E402 was explicitly excluded); scoped Mypy passed for all five changed Python production files. Scoped frontend lint, production Vite build and Git whitespace checks passed. These are scoped checks, not a claim that the full repository suite passed.
- Read-only GitHub and stored-record inspection confirmed TaskFlow PR #4 repository, author, open/pending state and exact head `8ad02ac50587c6bb668dc480ae68efdc9f411b68` match. No synchronization, workflow trigger, repository-code execution or new analysis was performed. Its existing unsupported algorithm comparison is unchanged; TaskFlow Phase 2 remains incomplete.
- Final read-only collection-count/document-hash comparison matched the pre-review baseline exactly: the populated demo database is unchanged.

Checkpoint scope: the six original files, the two necessary backend additions above, [PR identity tests](../../backend/tests/test_pr_identity_visibility.py), [PR page tests](../../frontend/src/pages/pull-requests/PullRequestsPage.test.jsx), and this report: **11 files**. Unrelated audit files, editor configuration, credentials, environment files and demo data are excluded. No scoring, algorithm rules, CI execution, multi-agent flags or production settings changed. The resulting local commit SHA is reported after commit; no push, merge or deployment is performed.
