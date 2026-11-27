# Phase 0 — Baseline audit and compatibility verification

Date: 2026-11-12. Scope: **audit only; Phase 1 has not started**.

## Decision

The baseline is reproducible, but the current agent subsystem is **not ready for
multi-agent integration or production enablement**. The existing test suites
pass while missing real provider-signature, timeout, AI-run ownership and
adapter-contract defects. An isolated provider/legacy-contract stabilization
phase is a reasonable next step **only after explicit approval**. Fixing these
findings is not part of this audit.

The current graph dispatches one specialist, with special handling that forces
HR callers to the HR node. It is not an implemented collaborative workflow.
No graph, API, scoring policy, dependency, feature flag, production configuration,
integration trigger or database schema was changed during Phase 0.

## 1. Pinned source and working-tree provenance

| Item | Observed value |
|---|---|
| Repository | `M:/Samanvaya` |
| Branch | `testing` |
| Exact audited commit | `771b41cc037ed24e2b9b763021149c49f14a2267` |
| Commit subject | `feat: integrate scoped scoring reviews and calibration readiness` |
| Initial tracked/index changes | None; `git diff` empty |
| Pre-existing untracked files, excluded | `.vscode/`, `PROJECT.md`, `TEST_INFRA.md`, `TEST_READY.md`, `empirical_harness.py` |
| Specification read | All 837 lines of the supplied `SAMANVAYA_SAFE_MULTI_AGENT_IMPLEMENTATION.md` |
| Specification SHA-256 | `cc6dc444a24d44d38e7b822a04c828e64d77a31567c9d5bb13c3d42074d78404` |

The specification's research snapshot and `d019b1ca` were not used as source
truth. This local commit includes the later scoring integration checkpoint;
several scoring and webhook suspicions in older reviews are therefore stale.
Remote branch state was not fetched or modified. No commit/push, merge or
deployment was performed for this audit. Future implementation should start on
a dedicated feature branch from this pinned commit, after rechecking drift.

Deliverables are this report, the [specification-path index](docs/multi_agent_baseline.md)
and an [audit-only reproduction script](docs/audits/multi_agent_phase0_probe.py).
The script is not imported by the application or default test discovery. It
documents current behavior, including defects; its successful exit does **not**
mean those defects are fixed. Its mocks and environment changes are process-local.

## 2. Executed baseline

| Check executed against the pinned runtime | Result |
|---|---|
| Existing complete backend suite via baseline runner | **2,716 passed, 111 skipped, 78 warnings**; 38.38 s; exit 0 |
| Existing complete frontend suite | **172 passed, 23 files**; 25.44 s; exit 0 |
| Frontend production build | Passed; 2,048 modules; exit 0 |
| Frontend Oxlint | **0 errors, 10 warnings**; exit 0 |
| Complete backend Ruff, default rules | **Failed: 160 findings**; exit 1 |
| Backend Ruff F821/E9 runtime-name/syntax subset | Passed; exit 0 |
| Complete backend Mypy | **Failed: 3 blocking errors**, further checking prevented; exit 1 |
| Installed Python dependency consistency, `pip check` | No broken requirements found; exit 0 |
| Phase 0 isolated characterization script | **16 characterization groups completed**, including six routing cases; exit 0 |
| Ruff on the added audit script | Passed; exit 0 |
| Native Mongo integration tests | Included and passed in backend suite with opt-in enabled |
| Ollama tags health | Existing health check false; explicit local HTTP probe hit `ConnectTimeout`; live inference **not verified** |
| Docker backend | Client 29.9.3 installed; Linux-engine named pipe unavailable; live worker tests **not run** |

The backend runner is the existing [run_scoring_baseline.py](backend/tests/audits/run_scoring_baseline.py:13).
It isolates the module-cached audit logger in mock Mongo and shortens oversized
test IDs for Windows paths. It does not replace application logic or skip new
failures. Mongo opt-in was enabled; Docker opt-in was explicitly disabled.
The 111 skipped cases are not passing evidence. Backend warnings include existing
Pydantic configuration/datetime deprecations and test-class collection warnings.
The frontend used the previously documented 30-second test timeout; this is not
a claim that the default-timeout CI path was exercised or fixed.

Full Ruff counts: F401 84, F811 27, F841 24, E402 19, E712 2, F541 2,
E731 1, E741 1. These are baseline findings; no autofix was run.
Mypy stopped on missing `langchain_community.llms`, missing
`domain.models.qa_ci_config`, and duplicate discovery of `services/transfer_service.py`
as `transfer_service` and `services.transfer_service`. No whole-project type-clean
claim is made. Pylance MCP tools were unavailable; source, installed runtime
objects and executed tests supplied the evidence.

### Installed environment

Python 3.12.10; FastAPI 0.162.0; Pydantic 2.9.2; LangGraph 1.2.19;
langgraph-checkpoint 4.3.1; langchain-core 1.7.4; langchain-ollama 1.1.0;
ollama 0.6.2; Motor 3.7.1; PyMongo 4.18.3; HTTPX 0.27.2; pytest 9.0.3;
Ruff 0.6.9; Mypy 1.11.2; mongomock-motor 0.0.36.
Node 24.19.0; npm 11.17.0; React 19.2.8; Vite 8.2.4; Vitest 5.0.5;
Oxlint 1.80.0. Versions came from installed package metadata/npm, not assumed
from ranges. [requirements.txt](backend/requirements.txt:26) pins the graph/provider
versions currently installed. No packages were installed or upgraded in Phase 0.

### Local integrations and side effects

[database.py](backend/core/database.py:16) lazily creates a Motor client from
settings, with repositories using the same collection accessor. There is no
automatic tenant filter in [BaseRepository](backend/repositories/base.py:19).
The test [conftest](backend/tests/conftest.py:19) supplies a synthetic secret and
test-only Mongo/model settings; normal unit fixtures use in-memory Mongo.
Real Mongo checks owned and cleaned uniquely prefixed collections: scoring
revision arbitration, PR-job deduplication and two process-exit/revocation recovery
cases ([scoring](backend/tests/test_performance_lifecycle_mongo.py:14),
[algorithm](backend/tests/test_pr_algorithm_mongo.py:16),
[restart](backend/tests/test_review_mongo_recovery.py:44)). They did not modify
employee assessments or real webhook deliveries.

Application [lifespan](backend/main.py:29) initializes indexes, starts the existing
webhook recovery processor independently of optional indexes, then stops it
before Mongo shutdown. This audit did not launch the full application lifespan
against production collections. Required secrets and startup validation remain
owned by [config.py](backend/core/config.py:24); no secret values were printed,
and no environment file or production setting was edited.

## 3. Current architecture and caller map

| Surface | Current callers and behavior | Compatibility boundary |
|---|---|---|
| [supervisor.py](backend/agents/supervisor.py:17) | `prepare → selected specialist → finish → END`; six tasks; recursion limit 6; copied per-request state; no checkpointer | Preserve six task names, default single dispatch, HR override and failure clearing |
| [invoke_agent](backend/agents/supervisor.py:100) | Production callers: generic AI route and CI/CD-log route, both via `asyncio.to_thread`; package re-export | Preserve sync invocation shape; do not add fan-out by changing its default graph |
| [ainvoke_agent](backend/agents/supervisor.py:107) | Available async wrapper; current explicit caller is HR-routing test | It does not prove durable or collaborative execution |
| Six specialist nodes | Code/HR permission checks; QA/DevOps/meeting JSON parser; CI/CD line parser | Each terminates; returned `next_agent` does not drive graph execution |
| Direct code-node callers | [GitHub simple/deep](backend/domain/services/github_analysis_service.py:130), [code-quality background route](backend/api/routes/code_quality.py:368), plus supervisor | Must test separately from supervisor; current internal callers omit user context |
| [Ollama factory](backend/agents/llm_provider.py:20) | All six specialists; CI/CD flaky-test helper; period interpreter; PR evaluation route; package re-export | Preserve documented model/temperature/base_url callers; fix actual wrapper contract, not every unrelated service |
| [AIRun](backend/domain/models/ai_run.py:11) | Created by generic AI route, CI/CD log route, GitHub sync; read/list methods in its repository | Existing mutable generic records differ from signed protected scoring artifacts |
| [GitHubAnalysisService](backend/domain/services/github_analysis_service.py:23) | Instantiated by GitHubSyncService; direct integration tests | Risk analysis, source discovery and optional explanation are distinct operations |
| [GitHubSyncService](backend/domain/services/github_sync_service.py:25) | GitHub routes, webhook processor/service | Revision storage, existing discovery/algorithm scheduling and optional AI must remain independent |
| [performance_agent.py](backend/agents/performance_agent.py:17) | PerformanceClaimService and legacy PerformanceService initialization | Separate from the six-node supervisor; numeric period evaluator is retired |
| [tool_using_agent.py](backend/agents/tool_using_agent.py:48) | Prototype/base classes; no production caller found outside that module | Do not treat prototype tools as registered supervisor capabilities |
| [ai.api.js](frontend/src/api/ai.api.js:3) | Health/invoke client wrappers; no current page caller found by repository search | Main PR evaluation UI uses a different API; do not redirect it implicitly |

The six task identifiers are `code_review`, `qa_analysis`, `devops_risk`,
`meeting_insights`, `cicd_analysis`, `hr_assistant`. Source and a patched-registry
probe confirm exactly one selected node executes, including forced HR routing.
The probe proves topology, not six healthy real-provider invocations.

No production `pr_multi_agent_v1` graph, planner, reconciler, workflow endpoints,
workflow collections or multi-agent flags were found in backend/frontend source.
The proposed design is not implemented by virtue of the existing supervisor,
recommendation service, prototype tool classes or webhook processor names.

## 4. Confirmed findings and priorities

Priorities below guide later work; **none was repaired in Phase 0**. Reproductions
use synthetic inputs and in-memory Mongo with actual FastAPI routes/repositories.
Authenticated synthetic principals replace only the JWT dependency where a
resource-scope decision is under test. Separate probes exercise real rejection
of missing headers/invalid JWTs. No real user's data was queried.

### F01 — High: AI-run reads do not enforce private ownership or tenant scope

[list_ai_runs](backend/api/routes/ai.py:188) explicitly includes records without
`context.project_id`; [get_ai_run](backend/api/routes/ai.py:216) checks a project
only if it exists and skips the check for `has_org_access` roles. Neither compares
`triggered_by` to the current user. The [repository query](backend/repositories/ai_run_repository.py:39)
has no tenant/owner predicate and the generic [model](backend/domain/models/ai_run.py:21)
has no first-class owner/project/organization contract.

Reproduced: developer A reads and lists synthetic user B's unscoped CI/CD run,
including its input log: HTTP **200**. A scoped unrelated-project record is
correctly denied **403**, so project checks are present but incomplete. PM O1
reads an O2 scoped record: **200**. The shared
[authorization helpers](backend/core/authorization.py:119) explicitly retain
single-org behavior; [project listing](backend/core/authorization.py:369) fetches
all projects for PM rather than matching organization. This is incompatible with
the new specification's strict tenant contract, even if a deployment has only
one organization today. CEO's documented global role must be handled deliberately,
not casually changed as a general RBAC redesign.

HR filtering is a denylist, not proof of HR-safe contents:
[filter_ai_run_for_hr](backend/api/routes/ai.py:235) removes `input_data.evidence`
but preserves arbitrary `context`, generated analysis and unrecognized nested
output. Synthetic private context survived an HR read. This is part of the same
disclosure boundary and must not be inherited by a shared PR workflow.

Positive boundary: generic AIRun reads reject protected performance artifact
types: **404** in the probe. The [protected-type exclusion](backend/repositories/ai_run_repository.py:39)
is real; this finding does not claim a bypass of signed scoring artifact APIs.

Recommended fix: authenticated private ownership for unscoped runs; trustworthy
server-resolved project/org metadata for scoped ones; filters before pagination;
explicit historical-record handling and HR allowlists. Old records without
provable provenance must not acquire a guessed tenant. Cover role/current-access
revocation and historical compatibility before rollout.

### F02 — High: invocation accepts forged project and evidence provenance

[AgentRequest](backend/api/routes/ai.py:22) accepts arbitrary evidence/context.
[Invocation](backend/api/routes/ai.py:82) computes accessible project IDs but never
validates the requested context project or fetches authoritative evidence.
[Persistence](backend/api/routes/ai.py:113) copies both dictionaries unchanged.

Reproduced: an authorized Lead assigned P1 submits QA evidence for P2/O2 with
`verification_state: SERVER_VERIFIED`; the actual route returns **200**, the run
is `completed`, and the caller's project and verification flag persist verbatim.
The model was stubbed; route, graph, node and persistence were real. There was no
source retrieval, revision pin, hash validation or independent evidence check.

Precise limit: this is **not** a demonstrated server validator granting verified
status or canonical score credit. The current AgentResponse has no verification
field. It is a provenance gap and possible label/scope laundering in stored
inputs; downstream code must not interpret those caller flags as trusted proof.
Ad-hoc assistance may continue with an explicit unverified/private contract.
New authoritative reports must resolve evidence on the server from exact,
authorized resources. Do not quietly convert Phase 2's inferred purposes or
caller dictionaries into approved contracts.

### F03 — High: real provider signature rejects code/HR calls

[get_ollama_llm](backend/agents/llm_provider.py:20) accepts only `model`,
`temperature`, `base_url`. Both [code](backend/agents/code_agent.py:76) and
[HR](backend/agents/hr_agent.py:80) pass `response_format=...`.
Actual node invocation with sufficient permissions produces:
`get_ollama_llm() got an unexpected keyword argument 'response_format'`.
The provider constructor was asserted **not called**: failure is before network
or inference. Nodes catch the exception and return errors; this is not an
uncaught server crash. A healthy Ollama would not repair this Python mismatch.

Existing authorization tests [mock the factory with `lambda **kwargs`](backend/tests/test_ai_authorization.py:141),
which accepts the unsupported keyword and hides this failure. Stabilize the
small provider/caller interface with a real-signature constructor test and no
unrelated scoring changes.

### F04 — High availability risk: configured inference timeout is ignored

The [factory](backend/agents/llm_provider.py:33) supplies `timeout=120` to the
installed `OllamaLLM`. Runtime inspection found no `timeout` Pydantic field;
`client_kwargs` is `{}`, and both underlying HTTPX clients have read timeout
**None**. The argument is ignored rather than a working 120-second deadline.
The 1.5-second tags health timeout is separate.

The generic route awaits a thread without an outer request deadline. A slow
inference can therefore retain a worker beyond the intended bound. The period
interpreter and PR evaluator have their own outer deadlines; they are not proof
the shared factory is bounded. Verify installed sync/async client timeout
configuration and cancellation behavior in the next isolated provider phase.

### F05 — Medium: CI/CD text protocol conflicts with forced JSON mode

The provider [forces JSON](backend/agents/llm_provider.py:32), while the CI/CD
[prompt](backend/agents/cicd_agent.py:90) and
[parser](backend/agents/cicd_agent.py:146) require `ROOT_CAUSE:` lines. A valid JSON
object carrying `root_cause` produces empty analysis; the supervisor reports
`Agent produced no validated analysis`. Live model behavior is unverified; the
deterministic parser incompatibility is reproduced. Stabilize this specialist's
format with explicit old-format compatibility tests rather than switching every
provider caller out of JSON mode.

### F06 — Medium: fallback output is not a strict validated success contract

[safe_parse](backend/agents/parsers.py:54) can fill absent fields from a fallback;
the [legacy models](backend/agents/parsers.py:84) do not enforce finite/ranged
numbers or enumerated risk values. `NaN`, confidence `999`, and risk label
`invented` are accepted by `CodeAnalysisResult` in the probe.

With only the known factory mismatch bypassed by a process-local mock, malformed
code-model output becomes analysis `Failed to parse AI response`, quality `0.0`,
risk `0.0`, and **errors=[]**. The supervisor accepts that nonempty fallback
string as success. This is a latent path behind F03, not a working real-provider
success today. Invalid data should produce explicit failure/unavailable output,
not fabricated numerical findings. Introduce strict versioned contracts with
legacy adapters; do not redefine authoritative engine scores or silently break
historical serialized AIRuns.

### F07 — High correctness risk: internal adapters omit permissions and hide failures

[GitHub simple agent state](backend/domain/services/github_analysis_service.py:132)
omits `user_context`; the code node correctly rejects it at its permission gate.
The adapter discards node errors and [marks the AIRun completed](backend/domain/services/github_analysis_service.py:166).
It also omits project ID from the persisted context, even when `pr_data` includes
one, connecting this defect to F01. Reproduced without a model: `analysis=None`,
status `completed`, no project key.

The [deep GitHub state](backend/domain/services/github_analysis_service.py:323)
and [code-quality background state](backend/api/routes/code_quality.py:384) also
omit permission context and ignore returned node errors. Those callsites are
source-confirmed variants; only the simple path's false-completion behavior was
directly reproduced. Preserve internal automation authorization explicitly; do
not remove the code node's permission guard to make callers appear healthy.
The [CI/CD route](backend/api/routes/cicd_logs.py:175) similarly persists completed
AI status without checking graph errors and should receive targeted coverage.

### F08 — High correctness risk: deep report adapter mixes engine and legacy units

[QualityEngine](backend/intelligence/quality_engine.py:83) returns dimensions such
as testing/architecture on a **0–100** scale. The
[GitHub adapter](backend/domain/services/github_analysis_service.py:337) copies
them into [QualityBreakdown](backend/domain/models/code_quality_report.py:12),
which caps testing at **15** and architecture at **10** and expects different
dimension names. Nominal synthetic evidence produces two Pydantic errors:
`testing=100 > 15`, `architecture=100 > 10`. Several unmatched dimensions instead
default to zero. This is not an LLM score override; it is an existing adapter
incompatibility that can prevent a report from being returned.

The public analysis wrapper catches failures and returns an AI-analysis error;
do not describe this as every endpoint crashing. A later fix needs a deliberate
schema/adapter compatibility decision. Do not invent dimension weights, divide
values arbitrarily, or modify either deterministic scoring policy in this audit.

## 5. Deterministic authority and subsystem compatibility

### Scoring authority: what is established and what is not

The deep PR report explicitly uses engine-derived quality and risk fields at
[report construction](backend/domain/services/github_analysis_service.py:352).
An additional deliberately degraded synthetic evidence case, which fits the
legacy breakdown caps, produced **quality=52, risk=38, MEDIUM** using the actual
engine formulas/default-config fixture. A conflicting stubbed model supplied
quality/risk **0/0**; the report retained **52/38**. This isolates authority from
the separate F08 reporting failure. It does not certify every possible caller.

The background code-quality route also persists
[engine values](backend/api/routes/code_quality.py:434), not node scores. No
multi-agent model is wired into these engines.

The specification's older performance account differs from current code:

- [Period model numeric methods](backend/agents/performance_agent.py:21) now
  reject numerical scoring; snapshot interpretation is advisory and uses
  deterministic claim validation, bounds and an outer timeout.
- [Canonical composition](backend/domain/models/performance_scoring.py:98) is
  explicitly 90/10 with typed units. Workflow approval requires exact signed
  [measurement/release authority](backend/domain/services/performance_lifecycle_service.py:160).
- [Readiness](backend/domain/services/performance_readiness_service.py:24) is
  explicitly false for production; calibration remains incomplete. No live
  scoring activation occurred during this audit.
- The 60/30/10 [contribution helper](backend/intelligence/contribution_credit.py:122)
  still exists and marks its output advisory-only. Repository caller search
  found calculations in tests/audit probes, not a current production period
  creation path. Its presence does not establish two live authoritative formulas.
- The separate [PR evaluation route](backend/api/routes/evaluation.py:1326) still
  produces legacy model-derived 0–10 dimensions, optionally composed 90/10 with
  a human score. Those are **not deterministic engineering measurements** and
  must not be promoted to canonical period scores or multi-agent verified truth.
  Leave that independently governed workflow unchanged here; its existing
  evidence/citation tests are included in the baseline.

Accordingly, a universal claim that no model-generated numbers exist would be
false. The established conclusion is narrower: the inspected engine-report and
canonical-period boundaries do not accept generic supervisor numbers as their
authority. Legacy per-PR evaluation is a separate compatibility/labeling risk.

### Compatibility matrix

| Workflow | Existing authority / persistence / independence | Evidence and limits |
|---|---|---|
| Generic AI invocation | Six-task single-dispatch; generic `ai_runs`; advisory output | Existing auth tests and new probes; F01–F07 limit claims of readiness |
| Code quality | Static analyzer registry → evidence → QualityEngine/RiskEngine → `code_quality_runs`/findings | Analyzer, quality, risk and discovery tests pass; background invocation is not durable recovery |
| Algorithm intelligence | Existing discovery → approved contracts/requirements → finite correctness/compatibility → isolated workers → deterministic decision policy | Contract, behavioral, requirement, PR-workflow and decision tests pass; native Mongo dedup passes; live Docker tests skipped |
| GitHub PR sync | Revision-aware `store_revision`; algorithm scheduling and exact-source discovery precede optional AI | [Sync order](backend/domain/services/github_sync_service.py:119), no-model discovery and stale/duplicate PR tests pass; live GitHub not called |
| Webhooks / DevSecOps | HMAC and persisted delivery dedup → bounded lease/recovery worker → existing actions | [HMAC](backend/domain/services/webhook_service.py:29), [startup](backend/main.py:52), recovery/process-exit tests pass; no real delivery injected |
| CI/CD logs | Deterministic LogAnalyzer results plus optional legacy interpretation and AIRun | Engine evidence is separate; F05/false completed status must be addressed before relying on AI success |
| Period performance / HR | Typed evidence/claims, signed governed artifacts, immutable lifecycle; production calibration gate remains disabled | Existing scoring, access, human, lifecycle, key-rotation and readiness tests pass; no empirical calibration or production activation certified |
| PR evaluation UI | Separate evaluation API, evidence manifest and legacy model dimensions | Existing evaluation/backend and frontend suites pass; do not route into new supervisor or canonical scoring implicitly |
| Recommendations | Role-aware deterministic risk recommendations and optional AI suggestions stored separately | [RecommendationEngine](backend/domain/services/recommendation_engine.py:28) is not a collaborative coordinator; no new automatic publishing |
| HITL | Existing `approvals` collection and approval membership/CAS | [Service](backend/domain/services/hitl_workflow_service.py:143) is not a durable LangGraph resume integration; see risks below |

The algorithm [worker](backend/intelligence/algorithms/runner.py:262) retains
network-off, non-root, read-only and capability restrictions. The PR
[authority resolver](backend/domain/services/pr_algorithm_intelligence_service.py:129)
requires an exact connected repository/project; approved contract matching
does not use inferred function purpose as an approval. Existing automatic
algorithm scheduling is already implemented and independent; it must not be
replaced or represented as the proposed new multi-agent trigger.

There is no implemented new feature flag to compare ON/OFF. This audit verifies
the current baseline and no runtime diff, **not** future integration equivalence.

## 6. Public API and persistence compatibility snapshots

Current generic API request remains:

```json
{"task_type":"qa_analysis","evidence":{},"context":{},"save_run":true}
```

Task enum is the six identifiers above; evidence is required, context defaults to
`{}`, save defaults true. Success HTTP **200** keys are exactly:

```text
run_id, task_type, analysis, recommendations, risk_level, confidence,
agent_history, errors, execution_time_ms
```

`run_id` is null for unsaved invocations, execution time is variable, and node
errors currently travel in a 200 response rather than a new HTTP status.
No numeric `quality_score`, proof/verification state or workflow ID is exposed
by AgentResponse. Introducing strict response fields there may break callers;
use explicit adapters or separately versioned contracts later.

Executed in-process HTTP snapshots:

| Request/context | Observed response |
|---|---|
| Allowed Lead, QA model stub | 200, current nine response keys, no errors |
| Non-admin developer invocation | 403, `{"detail":"Insufficient permissions"}` |
| Allowed Lead, health check false | 503, `{"detail":"Ollama service not available. Ensure Ollama is running at OLLAMA_BASE_URL."}` |
| Unsupported task type | 422 validation response |
| Missing Authorization on run listing, real dependency | 422 required-header response |
| Invalid Bearer JWT, real dependency | 401 |
| Unowned unscoped run read/list | 200 — confirmed F01 |
| Unrelated scoped project, ordinary user | 403 |
| PM O1 reading synthetic O2 scoped run | 200 — confirmed F01 |
| Protected scoring artifact through generic run endpoint | 404 |

Normal non-admin role permissions, directly evaluated from the registry:

| Role | TRIGGER_AI_EVALUATION | VIEW_AI_EVALUATION |
|---|---|---|
| Developer | No | Yes |
| QA | No | Yes |
| DevOps | No | Yes |
| Lead | Yes | Yes |
| PM | No | Yes |
| HR | No | No |
| CEO | Yes | Yes |

Admin/designation overlays can change this; defaults are not a full role-policy
matrix. Run list/read currently require authentication but do not separately
require VIEW_AI_EVALUATION. A routing test that forces HR through the graph is
not proof that a normal HR user may invoke that HTTP endpoint.

Synthetic stored generic record shape used in the probe:

```json
{
  "id":"<generated UUID>", "agent_type":"cicd_analysis",
  "input_data":{"evidence":{"log_excerpt":"SYNTHETIC_PRIVATE_LOG"},
                "context":{"note":"SYNTHETIC_CONTEXT"}},
  "output_data":{"analysis":"Synthetic private summary"},
  "status":"completed", "triggered_by":"b@synthetic.invalid",
  "error_message":null, "execution_time_ms":null, "model_name":"ollama",
  "created_at":"<UTC timestamp>", "updated_at":"<UTC timestamp>"
}
```

No real records were exported. Existing persistence remains: generic `ai_runs`;
signed protected scoring envelopes in that collection; `code_quality_runs` and
`code_quality_findings` with PR algorithm job records; approved algorithm
contracts and `algorithm_benchmark_runs`; revision-aware `pull_requests`;
`webhook_events`; `approvals`; recommendations. New multi-agent job/step/report
collections do not exist as implemented workflow storage in the inspected code.
Do not overload legacy AIRun to pretend it already stores durable graph checkpoints.

## 7. Recovery, integration risks and missing coverage

- **Durability:** code quality uses FastAPI
  [BackgroundTasks](backend/api/routes/code_quality.py:122), with no equivalent
  app-start recovery found for pending/running code-quality jobs. Static finding
  persistence is not crash recovery. Existing algorithm local-executor jobs
  explicitly [fail expired work without replaying code](backend/domain/services/pr_algorithm_intelligence_service.py:155);
  do not silently retrofit their semantics while adding a durable agent job.
- **HITL:** current [approval update](backend/domain/services/hitl_workflow_service.py:160)
  checks approver/status but lacks an expiration predicate at decision time;
  cleanup is separate. The agent notification/resume hook is a
  [TODO](backend/domain/services/hitl_workflow_service.py:290). These are
  source-confirmed reuse risks, not a demonstrated new deployment capability.
  Do not assume this service already validates pinned workflow hashes, current
  project permissions and durable resume. No consequential new action is needed
  for a read-only v1 report.
- **Provider coverage:** current successful node tests mock `get_ollama_llm`
  using permissive kwargs. Missing cases include actual factory signature,
  transport timeout configuration, cancellation of thread-based inference,
  supported/fallback provider behavior, and six real-format success/error paths.
- **Validation coverage:** missing strict enum/finite-number/size/depth/unknown
  field tests for legacy model outputs. No approved generic evidence resolver or
  claim-specific proof registry currently establishes user input as verified.
- **Authorization coverage:** existing unit HR filtering tests do not cover
  private ownership, PM tenant scope, arbitrary nested context, and pagination
  after access filtering. New characterization probes reproduce these gaps;
  they are not desired-behavior security regression tests yet.
- **Adapters:** missing end-to-end permission/error propagation and quality-unit
  tests for direct GitHub/code-quality node callers. A patched registry routing
  test cannot cover these callers. Fixing F03 alone exposes F06 rather than
  solving it.
- **No integration certification:** no live Ollama response, actual GitHub API
  round-trip, signed-in browser session, isolated deployment-host check or new
  multi-agent concurrency/prompt-injection/restart test was performed. Docker
  tests remain unverified because its server is unavailable. Do not start services
  or change flags to conceal these gaps.
- **Auth drift already fixed elsewhere:** current
  [JWT dependency](backend/core/dependencies.py:59) checks revocation, reloads
  current account authority, and optional auth delegates to it. Older findings
  about purely claim-based authority/optional revocation are not repeated as
  present defects. Generic resource-scope gaps above still remain.

## 8. Prioritized next work and Phase 1 readiness

**Phase 0 gate: satisfied as an audit baseline**, including explicitly recorded
failures and missing coverage. **Production/multi-agent gate: not satisfied.**
No permission to begin Phase 1 is inferred from this report.

Priority order:

1. **Before publishing any new shared reports:** repair F01/F02 in a separately
   reviewed security/evidence scope. Preserve legitimate private ad-hoc use and
   old record visibility only where provenance/ownership can be established.
   This is not authorization to redesign application-wide RBAC in Phase 0.
2. **First isolated implementation PR:** stabilize the existing provider and six
   legacy specialist contracts (F03/F04/F05/F06), with default single dispatch.
   No multi-agent graph, background worker, new UI or score authority.
3. **Separate adapter compatibility PR:** resolve F07/F08 and CI/CD false-complete
   status, with engine-output and historical-schema tests. A legacy seven-point
   breakdown cannot be reconstructed from unrelated engine dimensions by an
   invented mapping; make the compatibility decision explicit.
4. **Later phases only after their own gates:** tenant-scoped immutable evidence,
   claim proof, opt-in bounded graph, durable Mongo execution, UI/HITL and rollout.
   Carry the documented durability/type/lint gaps without mislabeling them as new
   workflow regressions. Keep production period scoring disabled.

### Concrete first implementation scope, for approval only

Suggested branch: `fix/ai-provider-legacy-contracts`, based on the pinned SHA.

| File scope | Smallest proposed change |
|---|---|
| [llm_provider.py](backend/agents/llm_provider.py) | Align schema argument and transport timeout with installed Ollama wrapper, preserving the three existing optional factory parameters |
| [code_agent.py](backend/agents/code_agent.py), [hr_agent.py](backend/agents/hr_agent.py) | Use the agreed factory contract and preserve permission/HR isolation; expose invalid output as failure |
| [parsers.py](backend/agents/parsers.py) | Add strict versioned specialist result validation and deliberate legacy adapters; no invented neutral numerical results |
| [cicd_agent.py](backend/agents/cicd_agent.py) | Align JSON output/parsing and test legacy formatting where retained |
| QA/DevOps/meeting nodes, only if required by shared adapter | Keep legacy successful API behavior; explicit malformed/unavailable outcomes |
| New narrowly scoped backend tests | Real factory signature/constructor tests, six specialist contract cases, parser negatives, outage/timeout and current HTTP snapshots |

Acceptance criteria for that isolated first PR:

1. No unsupported `response_format` TypeError in actual code/HR factory calls;
   no test hides the signature behind `lambda **kwargs` as its only evidence.
2. Effective finite sync/async transport deadlines are asserted against installed
   clients. A stalled model reaches a defined error; execution/cancellation limits
   are tested rather than inferred from a timeout keyword or recursion limit.
3. Six legacy tasks keep one-specialist dispatch and HR isolation. Valid provider
   outputs, outages, malformed/empty/oversized JSON and non-finite/out-of-range
   values have explicit compatible outcomes. No fabricated zero/neutral success.
4. The existing generic request fields, task enum, successful response shape,
   permission/503 behavior, and saved/unsaved run semantics remain compatible;
   any necessary change is explicitly versioned and tested.
5. Engine-derived quality/risk numbers, canonical 90/10 policy, signed approval
   gates, algorithm contracts/workers, webhook semantics and HR data boundaries
   are unchanged. F01/F02/F07/F08 cannot be declared fixed by provider tests.
6. Existing backend/frontend tests and relevant integration tests are rerun;
   baseline lint/type failures and unavailable infrastructure remain explicit.
7. No graph fan-out, new framework/infrastructure, automatic GitHub writes,
   production configuration change or scoring activation is introduced.

## 9. Reproduction commands

From `backend/`, using the existing configured Python 3.12 environment:

```powershell
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe ../docs/audits/multi_agent_phase0_probe.py
.venv/Scripts/python.exe -m ruff check . --statistics
.venv/Scripts/python.exe -m ruff check --select F821,E9 .
.venv/Scripts/python.exe -m mypy . --no-incremental
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m ruff check ../docs/audits/multi_agent_phase0_probe.py
```

From `frontend/`:

```powershell
npm test -- --run --maxWorkers=2 --testTimeout=30000
npm run build
npm run lint
npm ls react vite vitest oxlint --depth=0
```

Docker availability commands executed: `docker version --format
'{{.Client.Version}} {{if .Server}}{{.Server.Version}}{{end}}'` and
`docker info --format '{{.OSType}}'`; both showed no reachable server.
The provider's existing tags check returned false. Do not interpret unavailable
infrastructure as passing tests. On Windows, the test/build commands required
authorized child-process execution outside the restricted sandbox.

**Stop condition:** Phase 0 ends here. Approve a separate implementation scope
before changing runtime behavior or starting Phase 1.
