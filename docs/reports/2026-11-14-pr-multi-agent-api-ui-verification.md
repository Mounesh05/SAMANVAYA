# Task 4 — Manual PR analysis API and UI verification

Date: 2026-11-14. Status: checkpoint acceptance reviewed with the documented environment limitation; disabled by default; no production activation.

## Baseline and reviewed context

- Branch: `codex/pr-multi-agent-task4`.
- Reviewed base: `53b9f913cad198c58864b4d59d4647e20257af66`, the approved Task 3 checkpoint.
- Reviewed the [Task 2 report](./2026-11-13-pr-multi-agent-phase1-orchestration.md), [Task 3 report](./2026-11-13-pr-multi-agent-durability-verification.md) and the supplied safe multi-agent specification. Its SHA-256 remains `cc6dc444a24d44d38e7b822a04c828e64d77a31567c9d5bb13c3d42074d78404`.
- The final checkpoint includes only the fifteen files listed below. Its exact commit SHA is recorded in the checkpoint handoff; the containing Git commit identifies this report without a self-referential hash. No merge, push, deployment, GitHub repository write or Task 5 implementation is authorized. Existing unrelated untracked files are excluded.

Task 3 supplied durable jobs, immutable evidence, atomic claims, lease-generation fencing, checkpoints and one canonical report, but required an explicitly invoked internal pump. Task 4 adds a separate manual API, an application-owned pump and an opt-in GitHub panel. It does not replace the existing GitHub sync/review flow or agent supervisor.

## Changed files

| File | Purpose |
| --- | --- |
| [Backend settings](../../backend/core/config.py) | Add `PR_MULTI_AGENT_MANUAL_ENABLED=false`; preserve the internal master flag and environment guard. |
| [Backend template](../../backend/.env.example) | Document both opt-in flags as false; actual environment files were not changed. |
| [Application entry point](../../backend/main.py) | Register the separate router and start/stop one lifecycle-owned runtime before MongoDB closes. |
| [Evidence authorization](../../backend/domain/services/pr_multi_agent_evidence.py) | Extract the existing current-account guard for reuse by the authorized project picker; scope/permission logic is unchanged. |
| [Versioned API](../../backend/api/routes/pr_workflows.py) | Manual start, status, report and authorized project-choice endpoints. |
| [API projections](../../backend/domain/schemas/pr_workflow_api.py) | Versioned accepted/status/project responses, with persistence internals omitted. |
| [Controlled runtime](../../backend/domain/services/pr_workflow_runtime.py) | Bounded intake, one owned sequential polling task, restart recovery and awaited shutdown. |
| [API/runtime tests](../../backend/tests/test_pr_workflow_api.py) | Authorization, idempotency, lifecycle, recovery, flags and actual MongoDB API execution. |
| [Frontend API](../../frontend/src/api/prWorkflows.api.js) | Versioned paths and abort signals for reads. |
| [Frontend API tests](../../frontend/src/api/prWorkflows.api.test.js) | Path/payload/cancellation compatibility. |
| [Manual panel](../../frontend/src/components/github/ManualPRAnalysisPanel.jsx) | Project/PR form, progress, historical retrieval, advisory claims, contributions and limitations. |
| [Panel tests](../../frontend/src/components/github/ManualPRAnalysisPanel.test.jsx) | Loading, failed, partial, completed, conflict, feature-off and privacy behavior. |
| [Existing GitHub page](../../frontend/src/pages/github/GitHubSyncPage.jsx) | One import and one panel mount; existing controls and results remain unchanged. |
| [Frontend template](../../frontend/.env.example) | `VITE_PR_MULTI_AGENT_MANUAL_ENABLED=false`. |
| This report | Verification outcomes and operational limits. |

Fifteen intended files comprise Task 4. No dependency, database, queue or AI framework was added. Existing Task 3 persistence and fencing implementation files were not modified.

## API contract

All new routes use `/api/ai/workflows/v1` and the existing JWT authentication dependency. They require both backend flags and the existing development/test environment gate. Production/staging are rejected even if flags are set.

| Method/path | Behavior |
| --- | --- |
| `GET /projects` | Return up to 100 server-authorized project IDs/names, with a truncation indicator. Current account permissions and F01 tenant/membership rules are applied before the limit. Client organization parameters do not select scope. |
| `POST /pr-analysis` | Accept `project_id`, positive integer `pr_number` and optional exact `expected_head_sha`; return HTTP 202 with a job ID, stored status and snapshot identity. No model executes inside the request. |
| `GET /jobs/{job_id}` | Reauthorize and return pinned project/repository/PR/revisions, snapshot ID, progress, failure codes and evidence limitations. |
| `GET /jobs/{job_id}/report` | Reauthorize and return the immutable `pr-multi-agent-report-v2` advisory report; return 409 while no report exists. |

Request schemas reject caller evidence, repository overrides, ownership, tenant approval labels and scores. Repository/PR identity, exact revisions and evidence remain server-resolved through the existing service.

The POST response uses `pr-workflow-accepted-v1`; status uses `pr-workflow-status-v1`; project choices use `pr-workflow-projects-v1`. Private worker IDs, lease generations/expiry, checkpoints, raw snapshots and complete step ledgers are excluded from the status projection. The separately authorized report retains the evidence needed for review.

Repeated accepted requests for the same owner/scope/revisions reuse the existing job and frozen evidence, including after publication. No historical report is reset or overwritten. Intake contention returns 429 before accepting another preparation request; retrying after acceptance returns the existing matching job.

Missing/invalid resources or disabled features return 404; permission failures return 403; invalid/revoked JWTs return 401. Missing authorization headers retain the existing dependency's required-header validation behavior (422). Invalid resource bodies/IDs return 422. Worker absence or source/database unavailability returns a sanitized 503. Error bodies do not contain model output, raw persistence records or provider details.

The project picker shares the existing current-account and F01 accessible-project resolver, rather than trusting the browser's declared organization. This is a narrow reuse of existing authorization, not an application-wide RBAC redesign.

## Controlled execution and recovery

- The FastAPI lifespan owns one `PRWorkflowRuntime` per application instance. Lifecycle locking makes repeated/concurrent starts idempotent.
- With flags off, start does not construct a durable service or touch its MongoDB collection. Existing workflows do not acquire a new database dependency.
- Enabled instances have one awaited polling task, process one job at a time through `run_ready(limit=1)`, and poll/wake at a two-second interval. POST wakes that poller after durable insertion; it does not create a background task per request.
- Evidence preparation permits one in-flight request per instance; extra preparation requests receive 429. Accepted jobs remain in the existing MongoDB ledger.
- Multiple application processes may own polling tasks, but existing atomic claims and generation fencing prevent duplicate execution/publication of the same job. This is not a distributed quota for different jobs.
- Startup polls persisted pending/retry/expired jobs. The existing three-claim budget, server-time leases, checkpoints, failure classification, retry backoff and immutable publication rules are reused unchanged.
- Shutdown cancels/awaits the poller. Task 3 cleanup awaits graph/heartbeat cancellation; committed checkpoints remain and uncommitted work is recoverable after lease expiry. MongoDB closes only after this runtime and the existing webhook processor stop.
- Poll failures are retried without creating additional workers. Logs record exception classes, not model/provider content.
- Current owner permissions, tenant/project boundaries, repository binding and HR exclusion are rechecked before sensitive operations and publication. A worker UUID grants no project authority.

## Frontend behavior

The existing GitHub page mounts a new panel only when `VITE_PR_MULTI_AGENT_MANUAL_ENABLED` is exactly `true` and the existing UI permission checks allow both trigger and view; HR remains excluded. Backend checks remain authoritative.

The panel selects an authorized project and PR number. Repository and evidence fields are not client inputs. Opening a previous analysis ID performs reads without resubmitting it. Status polls stop on terminal states or read errors; explicit refresh is available. Reads carry abort signals, and query keys include the signed-in identity and organization. Cached advisory content is hidden on authorization/read errors; account changes remount isolated panel state.

Progress identifies Code and QA participation separately. Published single-specialist results are labeled **“Single-specialist advisory — partial”**. A stored report is not presented as approval or proof of correctness. Supported structured observations, proposed interpretations, unsupported claims and conflicts remain distinct; a supported value does not validate the model's accompanying prose. Source references, missing evidence, specialist failures and limitations are visible.

Model text is rendered as plain React text. No model-generated HTML, Markdown actions or arbitrary links are executed. No score, approval, merge, code-edit or deployment control is added. Original GitHub sync forms, analysis results and the six legacy tasks retain their behavior.

## Verification

Environment: configured Python 3.12.10 environment, existing Node/Vite/Vitest installation and local real MongoDB integration using test-owned UUID-prefixed collections. Controlled GitHub/model outputs were used; no live GitHub/Ollama success is claimed.

| Check | Result |
| --- | --- |
| Final Task 4 + Task 2/3 selection | **122 passed**, six warnings, 5.90 s: 29 new API/runtime cases plus the existing 93 workflow/durability cases |
| Stabilization/Task 2/3/API selection during implementation | **469 passed**, 125 warnings, 13.37 s, before the final real-Mongo API case was added |
| Full available backend attempt | **3,169 passed, 111 skipped, 197 warnings, one collection error**, 43.71 s; exit 1, not a fully green suite |
| Real MongoDB | The existing three durability cases and the new API-to-owned-worker-to-report case passed, including actual leases/fencing and persistence |
| Targeted frontend + original GitHub tests | **22 passed**, three files, 4.92 s |
| Full frontend | **194 passed**, 26 files, 40.07 s, one worker |
| Default frontend build | **Passed**, 2,050 modules transformed; no deployment |
| Frontend lint | Exit 0, **10 existing warnings**, no new warnings |
| Scoped new/refactored backend implementation lint | **Passed**; existing main entry-point E402 findings remain unchanged |
| Scoped Mypy | **Passed**, four API/runtime/authorization modules |
| Backend `F821,E9` | **Passed** |
| Broad Ruff | Same **160 existing findings**: 84 F401, 27 F811, 24 F841, 19 E402, two E712, two F541, one E731 and one E741 |
| Broad Mypy | Existing duplicate `transfer_service` / `services.transfer_service` discovery blocks later checking |
| Editor diagnostics / whitespace | Checked API/runtime/panel files had no diagnostics; `git diff --check` passed |
| Current configured backend flags | Internal **False**, manual API **False** |

### Environment-limited backend coverage

The installed Hypothesis version is **6.170.14**. Windows Application Control rejects its native extension with:

```text
ImportError: DLL load failed while importing _native:
An Application Control policy has blocked this file.
```

The existing [QA language property-test module](../../backend/tests/test_qa_workflow_multi_language_bugfix.py) could not collect. The full command disabled only Hypothesis's unrelated pytest plugin and used `--continue-on-collection-errors` to execute all other collectable tests, while preserving that error and nonzero exit. No Hypothesis assertions, deadlines or library/security settings were changed, and no dependency was installed/downgraded to bypass the policy.

This is a current environment blocker, distinct from the earlier timing flake. The previous Task 3 fully green suite cannot be represented as a fresh Task 4 result. Unqualified full-backend acceptance remains pending restoration of an approved working Hypothesis environment and rerunning that module/full suite.

### Faults found during implementation

Initial tests failed because the new routes/component did not exist. Frontend tests then caught React Query passing a mutation context argument, duplicate text queries, and a text-prefix mismatch; the mutation now explicitly forwards only the request payload, and UI assertions target the actual advisory region/plain text. No failure was hidden by changing application authority or weakening authorization.

Executed coverage includes JWT logout/revocation, current permission changes, HR exclusion, cross-owner/project/organization access, historical reports, forged evidence fields, duplicate submissions, preparation contention, default-off/production gates, one-worker lifecycle ownership, poll-error recovery, shutdown/resume after a committed Code step, late-response fencing, immutable publication, UI loading/failure/partial/two-specialist states, conflicts, safe text rendering, versioned paths and identity-isolated client state.

## Reproduction

From the backend directory with its configured environment:

```powershell
$env:SAMANVAYA_MONGO_TESTS = '1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe -m pytest tests/test_pr_workflow_api.py tests/test_pr_workflow_durability.py tests/test_pr_workflow_durability_mongo.py tests/test_pr_multi_agent.py -q --tb=short -p no:cacheprovider -p no:hypothesispytest
$env:PYTEST_ADDOPTS = '-p no:hypothesispytest --continue-on-collection-errors'
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m ruff check api/routes/pr_workflows.py domain/schemas/pr_workflow_api.py domain/services/pr_workflow_runtime.py domain/services/pr_multi_agent_evidence.py tests/test_pr_workflow_api.py core/config.py
.venv/Scripts/python.exe -m mypy api/routes/pr_workflows.py domain/schemas/pr_workflow_api.py domain/services/pr_workflow_runtime.py domain/services/pr_multi_agent_evidence.py --follow-imports=silent --ignore-missing-imports --check-untyped-defs
```

From the frontend directory:

```powershell
npm test -- --run --maxWorkers=1
npm run build
npm run lint
```

## Configuration, rollback and remaining limits

Both backend flags and the frontend build flag are documented as false in their templates. No actual `.env` was modified. To evaluate this feature later in an explicitly approved local development/test session, the backend must start with both opt-ins enabled and the frontend must be built/run with its opt-in; merely enabling a browser control cannot authorize execution. Production/staging remain blocked by the server environment guard.

Turning off the manual API flag blocks new manual operations and subsequent poll iterations; it does not reset records. An already running read-only attempt may finish if the internal master flag stays on. Turning off the internal master flag also prevents subsequent protected commits/publication. Stop/restart the backend to end the lifecycle-owned worker; committed checkpoints remain for later authorized recovery. Disabling the frontend flag removes the panel without altering the original GitHub view.

No automatic GitHub trigger, repository write, public reset/cancel operation, new AI task, framework, database or queue was introduced. Per-process worker capacity is bounded; cluster-wide model capacity/quotas, replica-set failover, power-loss testing, live-model response quality and a browser-based authenticated demo remain unverified. Existing optional Docker checks remain disabled/skipped. The current Hypothesis collection block is documented above.

## Final checkpoint acceptance rerun — 2026-11-14

Reviewed the complete Task 4 changes against the approved Task 3 base, including all new implementation and test files. No new blocking Task 4 defect was found. The staging scope is exactly the fifteen files in the inventory above; unrelated audit, editor and scratch files are excluded.

Fresh checkpoint results:

- Focused backend selection: **122 passed, six warnings, 10.14 s**, with `SAMANVAYA_MONGO_TESTS=1`; no skips. This includes all three real-MongoDB durability tests and the API-to-runtime-to-report MongoDB test.
- Relevant frontend selection: **22 passed, three files, 4.25 s**, including the existing GitHub page tests.
- Frontend build: **passed**, 2,050 modules. Full frontend lint: **exit 0, ten existing warnings**. Scoped lint of the four new frontend files: **passed without findings**. The frontend has no separate configured TypeScript check; scoped backend Mypy passed for all four selected implementation modules.
- Scoped backend Ruff: **passed** for the API, schemas, runtime, evidence authorization, API tests and settings. Whitespace validation passed.
- Current configured backend flags: **internal False, manual False**. Both settings/templates default to false. The production-mode frontend environment has no manual opt-in value, so the exact-`true` gate disables it; its template explicitly specifies false. No actual environment file was changed.
- Worker tests confirm idempotent start, one owned sequential task, awaited stop before database closure, recovery after a committed specialist checkpoint, current-account/project/tenant authorization and stale-response fencing. Task 3 persistence, generation guards and immutable publication source files remain unchanged.
- Protected-path comparison against the base found no changes to agents/six-task dispatch, deterministic intelligence/scoring, repositories, legacy AI/GitHub/CI/CD/performance routes, durable service, GitHub analysis/sync services or webhook processor. The existing GitHub page changes are only the new import and panel mount; application lifecycle additions wrap only the new runtime.

The blocked Hypothesis module was retried with collection only and **still failed**, exit 1, with the same Windows Application Control native-DLL error. No approved working alternative environment was established. The full-backend attempt above remains an implementation-stage result, not a fresh fully passing checkpoint suite. No system policy was bypassed and no dependency was downgraded. Live GitHub/Ollama behavior, optional Docker checks and authenticated browser integration remain unverified.

The authorized next Git operation after this checkpoint is creation of `codex/pr-multi-agent-task5` at the same commit. This branch creation does not authorize Task 5 implementation. Stop after recording the checkpoint SHA and branch; do not merge, push, deploy or enable production functionality.
