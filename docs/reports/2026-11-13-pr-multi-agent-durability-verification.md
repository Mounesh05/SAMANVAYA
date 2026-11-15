# Task 3 — Durable PR multi-agent execution

Date: 2026-11-13. Status: internal/test-only implementation; production activation is not approved.

## Baseline and scope

- Approved Task 2 base checkpoint: `b7a838e50a7e49495ebc8530fe1fca912a5b4aff`.
- Branch: `codex/pr-multi-agent-durability`.
- Task 3 implementation, tests and this report are included in a separate reviewed checkpoint. Its containing Git commit identifies the exact implementation; the SHA is recorded in the checkpoint handoff. No merge, push, deployment, production activation, UI or automatic trigger was performed.
- Context: [Task 2 verification](./2026-11-13-pr-multi-agent-phase1-orchestration.md), its reviewed F01–F08 prerequisites, and the supplied safe multi-agent specification. This task implements the durability milestone, independently of the earlier scoring phases.
- Existing unrelated untracked editor, audit and planning files were preserved.

Task 2 had pinned immutable evidence, typed sequential Code/QA handoffs and deterministic reconciliation, but its state disappeared with the process. Existing webhook repositories demonstrate atomic claiming/recovery patterns; they do not provide the new workflow's generation fencing or single-report publication boundary. Those existing queues and their behavior were not modified.

## Implementation and compatibility

| File | Change |
| --- | --- |
| [Existing PR contracts](../../backend/domain/models/pr_multi_agent.py) | Extract shared report content into a base model. The original v1 report retains exactly its original fields, version and `durable=false`. |
| [Persistence contracts](../../backend/domain/models/pr_workflow_durable.py) | Versioned checkpoint, immutable step-result payload and durable v2 advisory report. |
| [Mongo repository](../../backend/repositories/pr_workflow_repository.py) | Idempotent insertion, server-time leases, generation fencing, atomic step/checkpoint commits, recovery queries, integrity checks and one final report. |
| [Durable graph adapter](../../backend/agents/pr_multi_agent_durable.py) | Reuse the existing sequential LangGraph nodes; replay committed outcomes, persist new outcomes and finalize through the fenced repository. |
| [Internal durable service](../../backend/domain/services/pr_workflow_durable.py) | Explicit authorized start/read operations, bounded worker execution, heartbeat, error classification and recovery pump. |
| [Fault/authorization tests](../../backend/tests/test_pr_workflow_durability.py) | Mock-backed race, restart, timeout, revocation, corruption, compatibility and immutable-publication checks. |
| [Real Mongo tests](../../backend/tests/test_pr_workflow_durability_mongo.py) | Actual atomic races, server-clock leases, competing workers and abrupt subprocess exit/recovery. |
| This report | Verification, limits and recovery behavior. |

There is no new framework, database, queue server, public endpoint, application startup registration or background trigger. The existing feature flag remains false by default and the environment gate still excludes production. Existing six-task dispatch, single-agent APIs, HR isolation, performance scoring, quality/risk formulas, algorithm intelligence, CI/CD authority and GitHub/webhook behavior remain independent.

## Persistence and atomicity

One new collection, `pr_multi_agent_jobs`, contains each complete bounded execution ledger. Its job schema is `pr-workflow-job-v1`; embedded steps and checkpoints have their own v1 schemas. Final advisory reports use `pr-multi-agent-report-v2` and `durable=true`. The original ephemeral v1 report remains available through its unchanged internal entry point.

Embedding these records is intentional: the step result and checkpoint commit together, and final status and report commit together, in one atomic MongoDB document update. This works on the tested standalone MongoDB instance without multi-document transactions or another infrastructure dependency.

The job's unique `_id` is a canonical digest of the workflow version and complete server-resolved scope: owner, organization, project, repository, PR number, exact head SHA and base SHA. Matching repeated starts return the existing job. Different owners or revisions receive different identities. The first accepted snapshot is retained even if further CI submissions arrive later. Duplicate inserts cannot replace it.

The ledger persists the normalized pinned request, exact scope, snapshot ID, source references/hashes, structural observations, per-step outcomes, attempt/generation metadata, checkpoints and final report digest. It does not persist raw source code, raw model responses, credentials, HR context or arbitrary caller evidence.

### Lease and publication invariants

1. Claiming is atomic and increments both attempt count and a monotonically increasing generation. A server-created worker UUID identifies the claimant; it does not confer project permissions.
2. Lease eligibility, expiry, renewal and retry scheduling use MongoDB `$$NOW`, rather than a worker's wall clock. A controlled clock exists only as a deterministic repository test seam.
3. Every worker read/write checks job version/ID, exact authorization scope, `RUNNING` status, worker UUID, generation and an unexpired lease. An expired worker is rejected even before a replacement claims the job.
4. Each step commit additionally checks the checkpoint sequence. It atomically appends a versioned result and advances the checkpoint only when appropriate. Completed outcomes cannot be overwritten.
5. Snapshot/step/checkpoint/report consistency and content hashes are checked before consumption. Corrupt records are not accepted as verified analysis. Hashes detect inconsistent stored data; they are not a defense against a privileged database administrator rewriting data and hashes together.
6. Final publication requires both specialist outcomes, matching committed results, the exact immutable snapshot, the current lease generation, the expected checkpoint sequence and no existing report. The canonical report and `FINALIZED` state are written together.
7. Terminal jobs cannot be claimed again. Report history and evidence are never deleted or replaced by retry/recovery operations. No TTL index is installed.
8. The new ledger alone uses journaled majority writes, a finite five-second write-concern timeout, primary reads and majority read concern. Existing application collections retain their existing settings.

These guarantees concern one canonical stored report under MongoDB's atomicity/durability guarantees. They do not turn advisory model interpretations into proven correctness or authoritative scores.

### Failure and recovery behavior

- Prototype limits: three total claims per job, 90-second lease, 20-second heartbeat, 180-second attempt deadline, two- and four-second retry backoff, at most 20 jobs per recovery batch, six step-result entries and a two-MB document bound. These are internal engineering limits, not approved production workload SLOs.
- Each service instance serializes its work. There is no distributed cross-job model-capacity quota; production capacity remains uncalibrated.
- Model unavailability and inference timeouts retain failed attempt evidence and retry within the claim budget. A completed Code result survives a later QA failure and is reused.
- Invalid model responses are non-success outcomes and are not retried indefinitely. QA may still produce a partial advisory result when evidence permits, preserving Task 2 behavior.
- `FINALIZED` means an advisory report was atomically stored. `analysis_status` and the report's own status distinguish collaborative, partial, insufficient and failed analyses. It never means tests passed or an implementation was approved.
- Expired leases are reclaimable. A worker that dies on its last allowed claim becomes explicitly `FAILED / RETRY_EXHAUSTED`; its partial evidence remains intact and no report is fabricated.
- If MongoDB loses a write acknowledgement, execution leaves the uncertain result alone. Recovery examines the committed ledger after expiry: an acknowledged step is reused, and an already finalized report is not published again.
- Heartbeat loss cancels the awaited graph; cancellation is an optimization. The database fencing guard is the final protection against late model responses.
- Caller/process cancellation leaves the lease for restart recovery rather than reporting success. A crash after the last specialist but before publication still leaves `RUNNING`, with committed steps and no report, until a new authorized generation finalizes it.

## Authorization and historical access

Start uses the existing account/project/repository resolver and constructs evidence on the server. Client roles, verification labels, repository identities or evidence objects do not establish authority.

Read first retrieves only the minimal scope/ownership header. The current active account must still own the job and satisfy existing AI trigger/view permissions, project membership, tenant scope and repository binding before evidence/model payloads are fetched. Authorization is checked again before return. HR remains excluded.

Workers operate only for the stored server-resolved owner and scope, reloading that owner's current permissions. Checks occur before consuming snapshots, before inference/replayed steps, after inference before committing, and immediately before final publication. Revocation blocks further publication and private reads; it does not rewrite or delete historical reports. This does not redesign application-wide RBAC or change signed performance artifacts.

Historical reports remain bound to their original head/base revision and are readable by their currently authorized owner even after a PR moves. They are not silently changed to describe the new head. New revisions create new jobs. Revoked authority cannot view an old report simply because it was once authorized.

## Internal operation and rollback

The workflow remains disabled and inaccessible outside development/test. No worker is registered with FastAPI startup. An authorized internal operator must explicitly await the service's start/execution/recovery operations; a public asynchronous API and its lifecycle are outside this task.

```python
# Internal server code only. authenticated_user must come from the existing authentication boundary.
service = DurablePRWorkflowService()
job = await service.start(request, authenticated_user)
await service.run_ready(limit=10)  # Also used after a worker restart; bounded and awaited.
record = await service.get(job["job_id"], authenticated_user)
```

Recovery does not proceed unless the internal pump is run. A crash before a specialist result is durably committed can repeat that read-only inference; this task guarantees fenced result commits, not exactly-once model invocation.

Turning the existing flag off prevents starts, execution, recovery and report access through this service. In-flight publication also rechecks the gate; existing stored documents remain intact. No legacy workflow requires this collection or its indexes when the feature is off.

## Verification

Tests were added before implementation; the initial collection failed because the new durable service did not exist. Tests exercise the actual LangGraph and production repository methods with controlled specialist/GitHub outputs. No live Ollama or GitHub success is claimed.

The real database was **MongoDB 8.3.7, standalone**. Test-owned UUID-prefixed collections in `samanvaya_test` were dropped in fixture cleanup. No application collection was cleared or migrated.

The abrupt-process test runs the production repository in a separate Python child, claims a job, commits a controlled Code outcome, then calls `os._exit(23)`. A new service/worker generation resumes QA through the real graph without repeating that Code result. This is a persistence-boundary crash test with controlled model data, not a live-model deployment demonstration.

| Check | Executed result |
| --- | --- |
| Final complete backend suite, Mongo opt-in enabled, Docker opt-in disabled | **3,151 passed, 111 skipped, 197 warnings**, 77.90 s |
| Final targeted durability + Task 2 regression run | **93 passed**, four warnings, 6.12 s: 57 Task 2 cases plus 36 Task 3 cases |
| Real MongoDB checks | **Three passed**, included again in subsequent targeted/full runs; covers server time, journaled majority options, races and separate-process recovery |
| Stabilization regression selection during implementation | **438 passed**, 124 warnings, 20.92 s, before the last three durability coverage additions |
| Final scoped Ruff, seven Python files | **Passed** |
| Final scoped Mypy, five implementation modules | **Passed**, no issues |
| Backend fatal syntax/undefined-name Ruff (`F821,E9`) | **Passed** |
| Broad backend Ruff | **160 existing findings**, unchanged: 84 F401, 27 F811, 24 F841, 19 E402, two E712, two F541, one E731 and one E741 |
| Broad backend Mypy | **Blocked** by existing duplicate `transfer_service` / `services.transfer_service` discovery; later checking prevented |
| Full frontend (`--maxWorkers=1`) | **177 passed**, 24 files, 50.27 s |
| Frontend build | **Passed**, 2,048 modules transformed |
| Frontend lint | Exit 0, **10 existing warnings**, no errors |
| Configured feature flag | Direct runtime check returned **False** |

The final complete backend run includes every final code/test change and all 36 new durability cases, including the three real MongoDB tests. The previously documented Hypothesis timing failure did not reproduce. Existing deprecation/collection warnings remain visible; skipped optional integrations are not counted as passing tests.

Task 3's internal durability acceptance criteria are met on the tested standalone topology. This is readiness for review of the implementation, not authorization to deploy or activate it. Eight intended files comprise the change; unrelated files and protected legacy surfaces remain unchanged.

Failures found and resolved during implementation:

- The first bounded-retry assertion omitted the separate skipped QA ledger entry. It now explicitly expects three failed Code attempts and one skipped QA outcome, rather than confusing model invocations with persisted step entries.
- The installed `mongomock_motor.with_options` returns a synchronous collection. A test-only async-wrapper shim fixes that fixture gap; production Motor code keeps journaled majority concerns, which were exercised against real MongoDB.
- A new heartbeat test initially raced model startup and failed once in a full run. It now waits for an explicit inference-start event before simulating lease loss. Production deadlines and the cancellation/no-write assertions were retained.
- A controlled stalled-authorizer test reproduced a real deadline gap: the attempt timeout started after authorization. Authorization and graph execution now share the attempt deadline; the test checks both stalled authorization and stalled inference.

The existing frontend default-concurrency failures documented in Task 2 were not re-run as a separate parallel suite here; the complete one-worker suite passed with unchanged tests/timeouts. This report does not claim the older concurrency sensitivity was repaired. Earlier Hypothesis timing sensitivity remains an existing baseline limitation; no property/deadline was altered.

### Reproduction commands

From the backend directory, using the configured Python 3.12.10 environment:

```powershell
$env:SAMANVAYA_MONGO_TESTS = '1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe -m pytest tests/test_pr_workflow_durability.py tests/test_pr_workflow_durability_mongo.py tests/test_pr_multi_agent.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m ruff check agents/pr_multi_agent_durable.py domain/models/pr_multi_agent.py domain/models/pr_workflow_durable.py repositories/pr_workflow_repository.py domain/services/pr_workflow_durable.py tests/test_pr_workflow_durability.py tests/test_pr_workflow_durability_mongo.py
.venv/Scripts/python.exe -m mypy agents/pr_multi_agent_durable.py domain/models/pr_workflow_durable.py repositories/pr_workflow_repository.py domain/services/pr_workflow_durable.py domain/models/pr_multi_agent.py --follow-imports=silent --ignore-missing-imports --check-untyped-defs
.venv/Scripts/python.exe -m ruff check . --select F821,E9
.venv/Scripts/python.exe -m ruff check . --statistics
.venv/Scripts/python.exe -m mypy . --ignore-missing-imports --no-incremental
```

The full suite uses the established audit-isolation/Windows reporting-ID harness. Native subprocess access was used for the existing JS/TS parser and the explicit worker-crash test. Docker remains opt-in and disabled. Skipped tests are not counted as passed.

From the frontend directory:

```powershell
npm test -- --run --maxWorkers=1
npm run build
npm run lint
```

### Remaining limits

- Live GitHub/Ollama operation and Docker benchmark execution remain unverified in this task.
- Replica-set failover, MongoDB server/power loss, backup restoration, long-duration model load and older MongoDB versions were not exercised. Majority/journal options are configured and tested on the available standalone server; this is not certification of an untested deployment topology.
- No UI, public API, automatic GitHub trigger, worker daemon registration, global distributed quota or production activation is included.
- Recovery requires an explicitly running internal pump. Repeated same-scope/revision starts reuse the original evidence; there is no in-place refresh/reset of a historical job.
- Existing broad lint/type-check debt and prior concurrency-sensitive frontend/Hypothesis timing behavior are reported separately from Task 3 failures.

## Task 3 checkpoint finalization

The complete Task 3 change was reviewed against `b7a838e50a7e49495ebc8530fe1fca912a5b4aff` before committing. No blocking regression was found within its documented internal scope.

- Fresh durability run: **36 passed**, including all **three real MongoDB tests**, with four existing deprecation warnings, in **4.53 seconds**. The Mongo opt-in flag was enabled; no Mongo cases were skipped.
- Fresh Task 2 regression run: **57 passed**, four existing warnings, in **3.51 seconds**. Disabled/production gates and legacy report compatibility remain covered.
- Fresh scoped Ruff passed for all seven Python files; scoped Mypy passed for the five implementation modules.
- The current configured flag was checked directly and remains `PR_MULTI_AGENT_INTERNAL_ENABLED=False`. Execution/recovery remain explicit internal operations without a public route or automatic registration.
- Review confirmed unexpired-lease/generation guards, atomic immutable publication, committed-step replay and restart recovery. The regression runs include stale responses, duplicate publication races, uncertain acknowledgements and abrupt subprocess exit.
- Existing agent/supervisor, API, core configuration, intelligence/scoring, service, repository and frontend files compare unchanged against the base, except the explicitly documented shared PR report-content model. New durability imports remain confined to the new implementation and its tests.
- Exactly eight intended files are included: the shared report model, four new implementation modules, two durability test files and this report. Unrelated untracked files remain excluded.
- Task 4 preparation branch: `codex/pr-multi-agent-task4`, created from the resulting Task 3 checkpoint. No Task 4 implementation is included.

The earlier full backend/frontend results above remain recorded as implementation verification; they are not represented as fresh reruns during this checkpoint finalization. Existing deployment/topology and live-model limitations remain unchanged.

Stop after the checkpoint and Task 4 branch handoff. Do not merge, push, deploy or activate production functionality.
