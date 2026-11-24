# Multi-PR release management verification

## Executive summary

Samanvaya can discover, review and gate a release spanning several merged PRs in one repository. The gate uses the exact release, commit and immutable artifact. QA attests to the complete task set and a different DevOps reviewer approves the candidate. Controlled verification used GitHub provider fixtures, the mounted FastAPI routes, and a disposable local MongoDB database. Live TaskFlow rehearsal is blocked pending confirmed webhook secret rotation and authorized workflow installation.

## Starting state and version control

Work started on `testing` at `1b34e395`. The working tree already contained delivery-pilot code, UI changes and reports. The dedicated feature branch is `feature/multi-pr-release-management`. The commits include the release implementation and its prerequisites, including the earlier single-task gate that was present locally. Unrelated changes remain in the working tree. The branch has no merge into main or upstream push.

## Architecture and file map

| Area | Main files |
| --- | --- |
| Provider discovery and build verification | `backend/domain/services/release_discovery.py`, `backend/integrations/github/client.py` |
| Candidate contracts, evidence and state | `backend/domain/models/release.py`, `backend/domain/services/release_test_evidence.py`, `backend/domain/services/release_management.py` |
| Release endpoints and credential-backed gate | `backend/api/routes/releases.py`, `backend/api/routes/release_gates.py`, `backend/main.py` |
| Review workspace and client | `frontend/src/pages/releases/`, `frontend/src/api/releases.api.js`, route and sidebar registrations |
| Build and rehearsal | `.github/actions/samanvaya-release-gate/`, the two workflow templates and the TaskFlow runbook |
| Verification | `backend/tests/test_release_management.py`, `test_release_discovery.py`, `test_release_test_evidence.py`, `test_release_gate_action.py`, `frontend/src/pages/releases/ReleaseManagementPage.test.jsx` |

Discovery requires verified ancestry and attributable commits. Provider time, run attempt, repository ID, workflow path and bytes, and archive digest establish provenance. Only the configured combined-target test suites satisfy the QA gate. Historical manifests and reviews stay readable. MongoDB stores candidate identities, append-only revisions, environment baselines and active selections, and successful gate receipts. Unique revision identities and compare-and-set updates serialize reviews. A signed GitHub deployment observation needs the exact release, repository, revision, environment, artifact and manifest to change candidate deployment status. [Architecture, API contracts, configuration and indexes](../runbooks/multi-pr-release-management.md)

## Authorization and frontend

| Role | Workspace access |
| --- | --- |
| DevOps assigned to the project | Initialize the production baseline, create or refresh candidates, submit, hold, approve and supersede |
| QA assigned to the project | Inspect PRs, tasks and combined test evidence, then verify the whole candidate |
| PM and Team Lead with project access | Read scope, blockers, current readiness and deployment evidence. Lead can inspect existing exact-PR-revision engineering advice. |
| Developer | Read releases containing currently assigned work within accessible projects |
| CEO and HR | Release technical detail and approval controls are outside these roles |

Approval requires two distinct current reviewers. Stale revisions, missing task attestations, changed task state, missing evidence, mismatched artifacts, and project or credential conflicts fail closed. Legacy mode retains its existing payload and, when release scope enforcement is enabled, proves that the baseline delta contains exactly one reviewed task and PR. AI remains advisory.

## Verification and acceptance

The following results refer to controlled tests. GitHub provider fixtures exercise discovery and artifact identity separately from the mounted release lifecycle. The browser check used real app sign-in and fixture release responses.

| Command or check | Observed result |
| --- | --- |
| `python tests/audits/run_scoring_baseline.py` with the disposable release MongoDB test enabled | 3,966 passed, 119 skipped on the integrated working tree before the final history and revert review additions |
| `python -m pytest -q -p no:cacheprovider` for release, GitHub, QA, DevOps and access regressions with `SAMANVAYA_RELEASE_TEST_MONGO=1` | 151 passed |
| `npm.cmd test -- --run --reporter=dot` | 418 passed. An earlier run exposed missing route metadata, which was corrected and rerun. |
| Temporary archive of feature commits with local dependencies | 70 focused backend tests, 48 focused frontend tests, production build passed before the final revert acknowledgment |
| `npm.cmd test -- --run ReleaseManagementPage --reporter=dot` | 8 passed after the revert review change |
| Production build, frontend lint and Ruff on the release modules | Build passed, frontend lint passed with six existing warnings, and focused Ruff passed |

| Scenario | Controlled result | Live TaskFlow |
| --- | --- | --- |
| A. Single-task, single-PR gate | PASS | NOT RUN |
| B. Three PRs, multiple tasks, exact artifact and independent decisions | PASS | BLOCKED |
| C. One required task missing from the QA verification | PASS / denied | BLOCKED |
| D. New failed or incomplete combined evidence | PASS / denied | BLOCKED |
| E. Artifact or revision mismatch | PASS / denied | BLOCKED |
| F. Expanded candidate needs a new review and production slot | PASS / denied | BLOCKED |
| G. Revert traceability and explicit review of uncertain effects | PASS | BLOCKED |
| H. Baseline-scoped hotfix with ordinary QA and DevOps review | PASS | BLOCKED |
| I. Unauthorized organization, project, role or credential | PASS / denied | BLOCKED |
| J. Multi-PR delta through legacy input | PASS / denied when scope enforcement is active | BLOCKED |
| Live deployment execution and independently matched live deployment observation | NOT RUN | BLOCKED |

The gate checks evidence immediately before the workflow step. An external deployment may begin after a valid check and before a later hold. Discovery is bounded to 150 commits, 40 PRs and 100 tasks. Incomplete GitHub history and unverifiable rebases stay blocked. Rollbacks can be represented but remain ineligible under this policy. The rehearsal workflow writes a marker in GitHub's job summary, so an environment event from that job alone cannot establish a real artifact deployment.

## Run the controlled pilot

From the repository root, use the configured app prerequisites and run the API from `backend` with `.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`. In a separate terminal, run `npm.cmd run dev --prefix frontend`. Set the release feature flag and trusted workflow settings in the isolated pilot environment before starting the API. Leave workflow code protected and use the documented environment-scoped secret. Copy the exact build and manual rehearsal templates only after the pilot repository owner approves. Use separate named QA and DevOps accounts. [Activation and contracts](../runbooks/multi-pr-release-management.md) · [Workflow files, setup and rehearsal](../runbooks/taskflow-multi-pr-pilot.md)
