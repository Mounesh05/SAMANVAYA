# Task 2 — Phase 1 PR orchestration verification

Date: 2026-11-13. Review status: internal prototype; not approved for public use.

## Checkpoint and scope

- Branch: `codex/pr-multi-agent-v1`, created from the reviewed Task 1 checkpoint.
- Reviewed base: `56b1a66ce9bc9205241592197ff237f5c651dc8c`.
- Earlier stabilization checkpoints: F01/F02 `127d9efc5a0154d6808ec89fbe999defac7d7228`; F03–F06 `56264de7614c1bff83b3f9823707ba371314714d`.
- This implementation and report are included in a separate Task 2 checkpoint. The containing Git commit identifies the exact implementation; its SHA is also recorded in the checkpoint handoff. No merge, push, deployment, production activation, or Task 3 implementation was performed.
- Read the [Phase 0 audit](../../PHASE_0_AUDIT.md), [F03–F06 report](./2026-11-12-agent-stabilization-verification.md), [F01/F02 report](./2026-11-13-ai-run-security-verification.md), [F07/F08 report and review addenda](./2026-11-13-internal-agent-adapter-verification.md), and the complete safe multi-agent specification supplied from Downloads. The specification SHA-256 remains `cc6dc444a24d44d38e7b822a04c828e64d77a31567c9d5bb13c3d42074d78404`.

Existing unrelated untracked editor, audit, planning and test-harness files were preserved. The reviewed checkpoint already contained the stabilization work; it was not recommitted or rebased.

## Gap analysis and implementation

The existing supervisor dispatches one of six legacy tasks and does not provide a sequential collaborative handoff. Its task identifiers, routing, prompts, output schemas, authorization guards and APIs remain unchanged. Existing static discovery can inspect Python/JavaScript/TypeScript source without importing developer modules. Existing GitHub evidence resolution already validates repository scope, pinned commit/tree identity and file hashes. Existing QA ingestion stores CI submissions, but those records do not independently prove test execution or coverage.

The new workflow composes those existing pieces through a separate fixed LangGraph:

```text
START -> resolve_evidence -> code_analysis -> qa_analysis -> reconcile -> finalize -> END
```

The real graph, rather than a replacement test stub, is exercised with controlled specialist outputs. Every step records its transition. Skipped specialists have explicit outcomes; a node visit is not counted as specialist execution.

| File | Responsibility |
| --- | --- |
| [Configuration](../../backend/core/config.py) | One new setting: `PR_MULTI_AGENT_INTERNAL_ENABLED = False` |
| [Workflow contracts](../../backend/domain/models/pr_multi_agent.py) | Frozen, strict, versioned requests, scope, evidence snapshots, observations, claims, handoffs, outcomes and reports |
| [Evidence resolver](../../backend/domain/services/pr_multi_agent_evidence.py) | Fresh account/project authorization; pinned GitHub source integrity; existing deterministic discovery; scoped recorded CI observations |
| [Sequential graph](../../backend/agents/pr_multi_agent.py) | Distinct Code/QA responsibilities, explicit handoff, bounded async inference, deterministic reconciliation and report finalization |
| [Internal service](../../backend/domain/services/pr_multi_agent_service.py) | Manual internal entry point; environment gate; fresh authorization and revision checks; whole-run deadline |
| [Regression tests](../../backend/tests/test_pr_multi_agent.py) | Real orchestration, source parsing/integrity, model failure, cancellation, evidence scope and authority boundaries |
| This report | Scope, validation results, compatibility and limitations |

Only the configuration file changes existing runtime code. There are no new imports into the legacy supervisor, public routes, startup scheduling or webhook paths. There are no dependency changes, new collections or background workers.

## Authority, evidence and handoffs

1. The internal caller supplies a project ID and PR number, optionally the expected full head SHA. Repository names, evidence objects, scores, approval labels and automation identities are rejected as request fields.
2. The resolver reloads the current active account. Both AI trigger and view permissions, existing project membership, organization boundaries and unambiguous repository configuration must hold. HR is excluded even with administrative flags. It reuses F01 access resolution and F02 repository/file integrity checks; there is no automation bypass.
3. The GitHub PR identity, repository and full head/base revisions are established by the server. File evidence must match the exact commit, complete regular-file tree entry, Git blob SHA and SHA-256 bytes. The PR is checked again after collection. A moving revision aborts collection before inference.
4. Code evidence consists of existing deterministic discovery output: function counts, bounded structural indicator counts and declaration names/locations. Raw source, comments, test bodies and raw CI prose are not sent to the model. Developer modules are never imported or executed. The complete code-quality toolchain is deliberately not invoked: some existing analyzers can collect/import tests or consult developer-controlled tool configuration. This prototype performs structural analysis, not a complete security/correctness review or score recalculation.
5. QA requires an enabled project/repository registration and actual stored submissions matching the project, repository, exact head revision and PR. Records must have server-received timestamps, workflow identity/attempt metadata and complete consistent counts. Explicit conflicting tenant metadata is rejected. Missing, incomplete, unrelated or disabled sources cannot manufacture QA eligibility. A test-like function name is not QA execution evidence.
6. QA facts are named `ci_reported_*` and labeled `LOCAL_RECORDED_SUBMISSION`. The legacy ingestion token and stored metadata establish a local submission, not independently verified GitHub execution. The report always preserves that limitation. No test success, code correctness, coverage percentage or production readiness is inferred from it.
7. Code and QA receive the same immutable evidence snapshot. QA receives the complete typed Code outcome, including failure/timeout/skip when applicable, with `ADVISORY_NOT_INDEPENDENT_EVIDENCE` handoff authority. It has no tool or action channel. Fresh authorization is required before each eligible specialist and before returning a report.
8. Finalization rechecks the PR revision. A moved head/base produces `STALE_ADVISORY` for the original pinned scope. Revoked permission or changed project/tenant authority prevents report return.

### Deterministic reconciliation

All model prose retains `statement_status = ADVISORY`, including prose accompanying an exact factual assertion.

| Assertion status | Meaning |
| --- | --- |
| `SUPPORTED` | Only the separately structured observation ID, evidence reference and exact typed value match a server observation. The supported conclusion is generated from that observation, not copied from the model's prose. |
| `PROPOSED` | An interpretation cites available evidence but still needs independent validation. A second model agreeing never promotes it. |
| `UNSUPPORTED` | Missing/foreign citations, a previous model assertion used as evidence, or an assertion without the required matching observation. |
| `CONFLICTING` | A structured assertion contradicts an observed value, or specialists take opposing typed positions on the same topic. No model winner is selected. |

Conflict detection is limited to matching typed topics and observation identities; it does not prove that arbitrary natural-language statements are mutually consistent. The report states this limitation.

Report statuses distinguish collaborative advisory, partial collaborative advisory, single-specialist partial advisory, insufficient evidence, failure and stale evidence. `COLLABORATIVE_ADVISORY` means two valid contributions were produced; it is not test approval, correctness verification or permission to act. Code-only and QA-only results are both `PARTIAL_SINGLE_SPECIALIST_ADVISORY`.

## Bounds and failure handling

- Default disabled; explicitly blocked outside development/test even if the flag is set. A direct check of the current configured environment returned `PR_MULTI_AGENT_INTERNAL_ENABLED=False`.
- At most four changed source entries, each at most 32 KiB, using the existing file-evidence bound. Unsupported, removed, invalid or unavailable files remain limitations.
- Up to six structural indicator kinds and four function identities per file; at most four CI submissions. Truncation is reported.
- Snapshot bounds: eight evidence references and 64 observations; per specialist: 12 claims and eight limitations.
- Model prompt: 48 KiB; existing strict parser response bound: 64 KiB, with duplicate-key, depth, finite-value and extra-field validation.
- Evidence collection: 60 seconds; each specialist: 30 seconds; entire workflow: 180 seconds. These are prototype resource bounds, not production SLOs.
- Uses native awaited async inference. Timeout or caller cancellation cancels the awaited operation; no detached inference thread or durable job is created.
- Malformed, unsupported, unavailable and timed-out responses have explicit non-success outcomes and sanitized error codes. Valid structural observations survive model failure.
- Report contracts are immutable and read-only, with `authoritative_score = null` and `durable = false`. No AI run or quality result is persisted.

## Verification

Environment: configured backend Python 3.12.10 environment, Windows native subprocess access where required for the existing JS/TS parser, Vite and Vitest. Tests used real LangGraph transitions, mocked GitHub transport, controlled model responses and the existing database fixtures. No live GitHub/Ollama PR analysis was represented as tested.

| Check | Executed result |
| --- | --- |
| Complete backend suite, established isolated audit harness, Mongo opt-in enabled, Docker opt-in disabled | **3,113 passed, 111 skipped, 197 warnings**, 438.05 s |
| Final workflow + F01–F08 focused regression selection | **405 passed**, 124 warnings, 16.79 s; includes **57** new workflow cases |
| Final strengthened injection and typed-response-bound cases | **2 passed, 54 deselected**, four warnings, 46.75 s |
| Four new workflow modules, scoped Mypy with installed dependency interfaces | **Passed**, no issues |
| Changed/new Python files, Ruff | **Passed** |
| Backend Ruff `F821,E9` | **Passed** |
| Repository-wide backend Ruff | Existing **160 findings**: 84 F401, 27 F811, 24 F841, 19 E402, two E712, two F541, one E731, one E741 |
| Repository-wide backend Mypy | **Blocked** by existing duplicate `transfer_service` / `services.transfer_service` module discovery; subsequent checking prevented |
| Frontend initial default-concurrency run | **162 passed, 15 failed**, eight failing files, 143.07 s; async UI waits/test deadlines failed |
| Full frontend repeat with one worker, unchanged assertions/timeouts | **177 passed**, 24 files, 178.21 s |
| Frontend production build | **Passed**, 2,048 modules transformed |
| Frontend lint | Exit 0; **10 existing warnings**, zero errors |
| Editor diagnostics and Git whitespace check | No diagnostics in the six Python files; `git diff --check` passed |

The complete backend run preceded the final uniform typed-response byte-bound guard and the repository-name bound correction. The final 405-case focused run covers all final edits, including the strengthened injection test with an otherwise valid response and a valid long connected-repository identity. The separate two-case check preceded the final repository identity case. The report does not represent a second full backend run after those final corrections.

The previously documented Hypothesis 200 ms timing failure did **not** reproduce in this complete backend run; its existing timing sensitivity remains a verification limitation, and its deadline/property were not changed. Likewise, the frontend default-concurrency failures are recorded rather than erased by the successful one-worker repeat. Their concurrency sensitivity is observed; a broader test-infrastructure diagnosis is outside Task 2.

During development, three language integration assertions initially used `sort_call` instead of the existing `sorting_call` indicator. These assertions were corrected and the language cases passed. Scoped Mypy initially exposed missing literal/collection/state annotations, which were repaired. An initial sandbox run hit Windows temporary-directory access denial; the native authorized run passed. No failing test was skipped or weakened to obtain these results.

The backend full-suite skips include unavailable/opt-in integrations; they are not counted as passes. No live Docker, Ollama or GitHub integration success is claimed. The established Mongo opt-in flag was enabled for the complete backend run.

### Reproduction

Run from the backend directory using its configured Python environment:

```powershell
$env:SAMANVAYA_MONGO_TESTS = '1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py

.venv/Scripts/python.exe -m pytest tests/test_pr_multi_agent.py tests/test_internal_agent_adapters.py tests/test_function_discovery_integration.py tests/test_ai_run_security.py tests/test_agent_stabilization.py tests/test_agent_stabilization_api.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest tests/test_pr_multi_agent.py -k 'prompt_injection_and_scores or typed_specialist_replies' -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m mypy agents/pr_multi_agent.py domain/models/pr_multi_agent.py domain/services/pr_multi_agent_service.py domain/services/pr_multi_agent_evidence.py --follow-imports=silent --ignore-missing-imports --check-untyped-defs
.venv/Scripts/python.exe -m ruff check agents/pr_multi_agent.py domain/models/pr_multi_agent.py domain/services/pr_multi_agent_service.py domain/services/pr_multi_agent_evidence.py tests/test_pr_multi_agent.py core/config.py
.venv/Scripts/python.exe -m ruff check . --select F821,E9
.venv/Scripts/python.exe -m ruff check . --statistics
.venv/Scripts/python.exe -m mypy . --ignore-missing-imports --no-incremental
```

Run from the frontend directory:

```powershell
npm test -- --run
npm test -- --run --maxWorkers=1
npm run build
npm run lint
```

The existing audit harness isolates cached audit writes and shortens Windows reporting IDs. Native execution was used where Windows sandbox temp/subprocess restrictions prevented a meaningful check. No runtime dependencies or production configuration were changed for verification.

### Coverage and acceptance

Executed cases cover actual graph ordering, immutable shared snapshots, successful explicit handoff, Code-only and QA-only partial outcomes, no evidence, incomplete/foreign CI metadata, disabled QA registration, unavailable/invalid model output, timeout and cancellation, account revocation between steps, project/tenant/HR boundaries, valid long repository names, revision movement, source/blob integrity, Python/JavaScript/TypeScript parsing, fake test names, source injection without execution, forged authority/action/score fields, unsupported citations, contradictory assertions and model agreement without independent proof.

Task 2's internal orchestration acceptance criteria are met within the documented source and CI-submission scope. This is readiness for review of the internal prototype, **not** readiness for public or production activation. Existing repository-wide lint/type-check debt and concurrency-sensitive test behavior remain visible above.

### Compatibility and remaining limits

- F01–F08 regression coverage is included. Legacy six-task dispatch, HR isolation, private AI-run visibility, versioned quality reports and internal automation guards remain independent.
- Canonical performance formulas, production activation policies, deterministic quality/risk formulas, algorithm intelligence, benchmark execution, CI/CD execution authority and GitHub/webhook processing are unchanged.
- No public API/UI, automatic triggers, new score dimensions, automatic test generation, source edits, PR approvals, merges or deployment capabilities were introduced.
- Live GitHub permissions/network behavior, live Ollama response quality and Docker-backed benchmarks are not validated in this task.
- Structural source scope and recorded CI submissions are intentionally narrower than a comprehensive PR assessment. Missing evidence remains explicit.
- There is no durable run state, replay recovery, worker ownership, idempotent public submission or report retrieval API. Those require Task 3 and separate approval. This workflow must remain internal/test-only.

## Task 2 checkpoint finalization

The implementation was reviewed again against `56b1a66ce9bc9205241592197ff237f5c651dc8c` before committing. No blocking regression was found within Task 2's documented scope.

- All **57 workflow tests passed**, with four existing Pydantic deprecation warnings, in **3.41 seconds**. This was a fresh run of the complete workflow test file, not a previously recorded result.
- Ruff passed for all six Python files in this checkpoint.
- The default setting and the current configured environment both leave `PR_MULTI_AGENT_INTERNAL_ENABLED=False`. The regression cases also verify rejection in production even when the flag is set.
- Reference inspection found no workflow integration into existing public APIs, the legacy supervisor, startup paths or frontend. A Git comparison of those existing surfaces against the reviewed base was empty.
- Exactly seven intended files are included: the configuration setting, four new workflow modules, workflow regression tests and this verification report. Unrelated untracked files remain excluded.
- The Task 3 preparation branch is `codex/pr-multi-agent-durability`, created from the resulting checkpoint. Creating that branch does not implement durability or activate the workflow.

Stop after the checkpoint and branch handoff, as requested. Task 3 implementation remains pending; no MongoDB jobs, leases, checkpoints, persisted reports or new endpoints are introduced by this commit.
