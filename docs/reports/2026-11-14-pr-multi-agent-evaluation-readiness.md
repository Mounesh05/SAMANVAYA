# Task 5 — Multi-agent evaluation and rollout readiness

Date: 2026-11-14. Branch: `codex/pr-multi-agent-task5`.
Reviewed baseline: `57c68623daf4d6ca605f6f715b482619faf0a9f9`.

**Verdict: NO-GO for production rollout.** The controlled evaluation establishes
claim-handling and reliability safeguards within the tested scope. It does not
establish better live-model accuracy, acceptable Ollama resource consumption or
an entirely passing backend suite. No feature was enabled, deployed or redesigned.

## Context and scope

Read the complete safe multi-agent specification supplied in Downloads, SHA-256
`cc6dc444a24d44d38e7b822a04c828e64d77a31567c9d5bb13c3d42074d78404`, and
the [Task 2](./2026-11-13-pr-multi-agent-phase1-orchestration.md),
[Task 3](./2026-11-13-pr-multi-agent-durability-verification.md) and
[Task 4](./2026-11-14-pr-multi-agent-api-ui-verification.md) reports.
HEAD and branch matched the requested baseline before editing. The index was
empty and the working tree contained only previously unrelated untracked files.
Those files remain outside this change.

Task 5 adds evaluation fixtures, test-only tooling and documentation. It changes
no application modules, APIs, prompts, scoring policies, dependencies, environment
files, MongoDB schemas, webhook behavior or GitHub operations. No automatic trigger,
new infrastructure, multi-agent feature expansion, merge or push is included.

## Deliverables

| File | Purpose |
| --- | --- |
| [Predetermined protocol](../evaluation/pr-multi-agent-v1-protocol.md) | Questions, matched conditions, denominators, acceptance gates and approved live follow-up |
| [Nine PR fixtures](../../backend/tests/fixtures/pr_multi_agent_evaluation_v1.json) | Three Python, three JavaScript and three TypeScript cases with expected observations and explicit limitations |
| [Test-only comparison helpers](../../backend/tests/pr_evaluation.py) | Scripted inference, exact source/blob metadata, finite-catalogue scoring and timing aggregation |
| [Evaluation and adversarial tests](../../backend/tests/test_pr_multi_agent_evaluation.py) | Actual legacy and collaborative graphs, matching evidence/assertions, injection, forged authority, scope, timeout and denominator checks |
| [Machine-readable results](../evaluation/pr-multi-agent-v1-results.json) | Ninety measured mode executions, nine pinned snapshots and corpus/protocol/harness hashes |
| This report | Readiness decision, executed checks, baseline blockers and remaining work |

## Evaluation design and evidence

The protocol and corpus were written before the measured run. The stored protocol
hash is `880420364a2d53311ef5d12cfdfd2368ed8778fbfc08caf2695fea44f95a073a`;
the corpus hash is `0c5bf54b4ea26818d2087d33c0abc81957349e3df2457d229593944e8b9b9e28`.
Results record exact hashes of the test and helper code as well.

Fixtures cover reachability, filtering, sorting, recursion, iterative tables,
misleading names/comments and unfamiliar transforms. Expected findings are
function counts and locally recorded CI failure counts. These match the existing
resolver's actual evidence scope. The source collector verifies mocked Git blob
bytes and invokes the existing real static parsers; submitted code is not run.

Each fixture is resolved once through the current authorization/evidence service.
Both modes consume the same immutable snapshot. The legacy Code node receives it
through its existing evidence-summary field; collaborative nodes consume typed
views and QA receives the actual Code handoff. Existing production prompt builders,
parsers and LangGraph transitions execute. Only inference and GitHub transport are
controlled. Five paired repetitions alternate execution order. Collection is
excluded equally from elapsed time; this is not API/network/queue latency.

The scripted legacy response includes the **same substantive assertions** as the
two collaborative responses together. QA evidence is not withheld from the legacy
baseline to manufacture improvement. The legacy graph runs one specialist with
the new workflow flag off; the collaborative graph uses two specialist calls.
The extra call budget is reported, not described as an equal-token comparison.

Metrics use declared positive facts and one explicit negative control per case.
They do not judge arbitrary prose using another model. Repeated agent agreement
does not create another independent finding. Interpretations stay separate from
fact precision/recall. The fixture defect catalogue is deliberately finite and
synthetic; it cannot estimate real PR defect detection or production false alarms.

## Measured controlled results

Metrics below count each distinct case once; timing uses all 45 trials per mode.
Repeated measurements are not treated as 45 independent PRs.

| Metric | Legacy one-specialist | Collaborative Code + QA |
| --- | --- | --- |
| Expected facts emitted (raw TP / FN) | 18 / 0 | 18 / 0 |
| Seeded false factual assertions emitted (raw FP / TN) | 3 / 6 | 3 / 6 |
| Raw precision / recall | 85.71% / 100% | 85.71% / 100% |
| Raw finite-catalogue false-positive rate | 33.33% | 33.33% |
| Unique unverified interpretations emitted | 3 | 3 |
| Structured supported tier | No corresponding legacy schema field | 18 TP, 0 FP, 0 FN |
| Typed factual disagreement detected | No corresponding legacy schema field | 3 / 3 |
| Unsupported interpretations promoted | No corresponding legacy verification tier | 0 |
| Controlled elapsed median | 5.065 ms | 5.805 ms |
| Controlled elapsed nearest-rank p95 | 16.295 ms | 13.685 ms |
| Controlled calls over 45 trials | 45 | 90 |
| Total measured prompt bytes | 249,495 | 528,070 |
| Total measured response bytes | 8,280 | 49,875 |
| Live Ollama CPU/RAM/VRAM/GPU/tokens/latency | Unverified / null | Unverified / null |

The raw accuracy difference is **zero by construction**. The supported tier
filters the seeded false facts; it does not repair the model or make every report
statement verified. All six attempts to assert an agreed cryptographic guarantee
(two per agreement fixture) remain advisory interpretations, not independent proof.
The three false-count assertions are conflicting and remain visible separately.

The controlled p95 happened to be lower for collaborative while its median was
higher. These millisecond values contain no actual inference and are affected by
host scheduling and graph overhead. They establish neither a live speedup nor a
latency regression. Prompt bytes and call count are measured overhead indicators,
not token counts or Ollama memory/CPU measurements.

## Predetermined acceptance gates

| Gate | Outcome |
| --- | --- |
| Matched evidence/assertions, nine cases × five pairs | PASS — snapshot equality and assertion multiset checked |
| Preserve expected facts; no false fact in supported tier | PASS — all 18 retained, all three negatives excluded |
| Agreement cannot establish verification | PASS — zero unsupported promotions |
| Detect three typed factual disagreements | PASS — 3/3; no claim about arbitrary prose consistency |
| Focused security/reliability and MongoDB | PASS — 122 baseline + 20 new tests; also included in the full available run |
| Backward compatibility/full regression | Environment-limited; no unconditional all-backend pass |
| Live accuracy improvement and >=95% precision | UNVERIFIED — controlled responses cannot satisfy this gate |
| Live warm/cold p95 and approved relative latency budget | UNVERIFIED — no live inference |
| Ollama resource measurements and approved host capacity | UNVERIFIED — no approved live measurement/budget |

## Verification

Configured Python 3.12.10 on Windows; existing Node/Vitest/Vite environment and real
local MongoDB. All outcomes below were executed during Task 5.

- Pre-change workflow/API/durability baseline: **122 passed**, six warnings,
  15.35 s, with MongoDB opt-in enabled and no skips.
- New evaluation/adversarial selection: **20 passed**, four warnings, 7.37 s.
  The exported corpus contains 45 paired trials, not 45 extra pytest test cases.
- Full available backend: **3,189 passed, 111 skipped, 197 warnings, one collection
  error**, 123.38 s, **exit 1**. No executed test failed; the suite is nevertheless
  incomplete because the existing Hypothesis module could not collect. The 20 new
  tests, existing stabilization/legacy tests, all workflow/API/durability cases and
  the four real-MongoDB cases are included. Skipped integrations are not passes.
- Full frontend: **194 passed**, 26 files, 79.92 s, `--maxWorkers=1`.
- Production frontend build: **passed**, 2,050 modules. No deployment.
- Frontend lint: exit 0, **ten existing warnings**. No frontend files changed;
  there is no separate configured frontend TypeScript check.
- Scoped Mypy: **passed**, thirteen workflow/evaluation modules.
- New Python Ruff and backend `F821,E9`: **passed**.
- Broad backend Ruff retains **160 existing findings**: 84 F401, 27 F811,
  24 F841, 19 E402, two E712, two F541, one E731 and one E741.
- Broad Mypy remains blocked by duplicate discovery of `transfer_service` and
  `services.transfer_service`; it does not constitute a passing full type check.
- Initial scoped Mypy found six annotation/inference errors in the new test-only
  harness. Explicit heterogeneous-result/Counter annotations corrected them;
  final lint/type checks passed without changing application behavior or criteria.
- Editor diagnostics found no errors in the two new Python files. The four
  recorded protocol/corpus/harness/helper hashes, ninety execution records and nine
  snapshots were independently checked against the saved JSON. An initial
  PowerShell count probe used a property-collection `Count` incorrectly; enumerating
  property names confirmed all nine snapshots without modifying the artifact.

### Security, reliability and UI coverage

New negative cases exercise source prompt injection without executing developer
code; fabricated model verification/action/score/router fields; foreign repository,
foreign organization and stale revision; explicit timeout; and honest empty-metric
denominators. Existing workflow cases cover forged evidence, missing QA, opposing
positions, invalid/oversized replies, moved revisions, HR exclusion and revocation.

Existing API/durability cases exercise authorized/anonymous/revoked access, scoped
project selection before limits, cross-user/project/organization isolation,
historical records, bounded intake, repeated starts, atomic claim races, lease
expiry, generation fencing, late responses, lost acknowledgements, checkpoint
replay, abrupt subprocess death and one immutable canonical publication.
Three real-Mongo durability cases and the real-Mongo API/runtime/report case are
included in the focused selection. Test-owned collections are cleaned up; no
application collection is deleted or migrated.

The complete frontend run includes the existing PR panel loading, failed,
single-specialist partial, conflicting, completed, escaped model-text and
authorization-hidden report tests. This is automated UI verification, not a live
authenticated browser demo.

### Hypothesis environment investigation

The existing property-test module still fails collection with:

```text
ImportError: DLL load failed while importing _native:
An Application Control policy has blocked this file.
```

Collection-only reproduction exited 1; no properties ran. Installed Hypothesis is
6.170.14, extension `_native.cp312-win_amd64.pyd` (214,528 bytes). Both existing
Windows virtual environments contain identical extension bytes, SHA-256
`c1b5920a1fae128a5305b32ee120c1c217428ea28a83e833c76b02e4f101a74c`.
Signature inspection reports unsigned; that observation does not establish the
exact administrative policy rule responsible for rejection.

Docker CLI exists, but its Linux-engine named pipe is unavailable; Docker server
and image enumeration fail. Installed WSL distributions alone do not establish a
configured approved backend test environment. No working approved alternative was
established. No dependency installation/downgrade, DLL replacement, unblocking,
policy modification or security bypass was attempted.

The full available run disables only the broken Hypothesis pytest plugin and uses
`--continue-on-collection-errors` to exercise other tests while retaining the
property module error and nonzero exit. The property tests are not relabeled as
passed. An approved CI/Linux/Python 3.12 environment with the project's existing
dependency set must rerun the blocked module and complete suite before full
backend acceptance.

### Live integrations

No explicitly approved nonproduction GitHub repository/PR and Ollama endpoint/model
was supplied for this run. Existing credentials do not confer that approval.
No live GitHub/Ollama request or inference was attempted. Their read-only transport,
live response quality, inference deadlines, CPU/GPU/RAM/VRAM/token use and warm/cold
latency remain **unverified**, not successful zero-use measurements.
Docker benchmark integrations, replica-set failover, power loss, long-duration
model load and an authenticated browser demonstration remain unverified.

## Reproduction

From the backend directory, using the existing configured Python environment:

```powershell
# Export controlled measurements; overwrites only the dedicated evaluation JSON.
$env:SAMANVAYA_PR_EVALUATION_REPORT = '1'
.venv/Scripts/python.exe -m pytest tests/test_pr_multi_agent_evaluation.py -q --tb=short -p no:cacheprovider -p no:hypothesispytest
Remove-Item Env:SAMANVAYA_PR_EVALUATION_REPORT -ErrorAction SilentlyContinue

# Existing workflow/API/real MongoDB checks.
$env:SAMANVAYA_MONGO_TESTS = '1'
.venv/Scripts/python.exe -m pytest tests/test_pr_workflow_api.py tests/test_pr_workflow_durability.py tests/test_pr_workflow_durability_mongo.py tests/test_pr_multi_agent.py -q --tb=short -p no:cacheprovider -p no:hypothesispytest

# Full available suite; retains the known collection error and nonzero exit.
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
$env:PYTEST_ADDOPTS = '-p no:hypothesispytest --continue-on-collection-errors'
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py

.venv/Scripts/python.exe -m ruff check tests/pr_evaluation.py tests/test_pr_multi_agent_evaluation.py
.venv/Scripts/python.exe -m ruff check . --select F821,E9
.venv/Scripts/python.exe -m ruff check . --statistics
.venv/Scripts/python.exe -m mypy agents/pr_multi_agent.py agents/pr_multi_agent_durable.py domain/models/pr_multi_agent.py domain/models/pr_workflow_durable.py repositories/pr_workflow_repository.py domain/services/pr_workflow_durable.py domain/services/pr_multi_agent_service.py domain/services/pr_multi_agent_evidence.py domain/services/pr_workflow_runtime.py api/routes/pr_workflows.py domain/schemas/pr_workflow_api.py tests/pr_evaluation.py tests/test_pr_multi_agent_evaluation.py --follow-imports=silent --ignore-missing-imports --check-untyped-defs
```

From the frontend directory:

```powershell
npm test -- --run --maxWorkers=1
npm run build
npm run lint
```

The established backend harness isolates cached audit writes and shortens only
Windows reporting IDs. Assertions, properties and production settings are unchanged.

## Compatibility and next decision

All tracked application files compare unchanged to the Task 4 baseline. Legacy
six-agent dispatch, HR isolation, F01–F08 protections, deterministic scoring,
algorithm intelligence, GitHub sync/webhooks and CI/CD execution remain independent.
Both backend flags still evaluate false. The frontend template defaults false and
its exact-`true` gate remains unchanged. No environment file was modified.

Task 5 delivers a reproducible offline evaluation and a conservative readiness
assessment. It does **not** establish the requested live superiority or resource
benefit. Keep production activation disabled. Priorities before reconsideration:

1. Restore an approved working Hypothesis environment; run the blocked module and
   full suite with no collection errors.
2. Obtain approval for a read-only nonproduction PR/model pilot, a pinned model
   version and explicit host capacity budget. Execute the predeclared paired live
   evaluation with independent human adjudication, including unsupported claims.
3. Measure cold/warm inference and resource consumption; verify the 30-second
   specialist deadline is suitable for the approved model/host. Do not relax it
   implicitly to improve results.
4. Review cluster-wide capacity/fairness limits and deployment-topology durability
   separately; current leases prevent duplicate job commits, not global model
   overload by unrelated jobs.

Stop for review. No Task 6, automatic GitHub triggers, rollout, merge or push is
authorized by this evaluation.

## Task 5 checkpoint finalization — 2026-11-15

Reviewed the complete report, protocol and saved results against the requested
Task 4 baseline. The finalization audit parsed every saved record, validated the
strict snapshot contracts and recomputed all fixture/trial aggregates. There are
exactly **nine fixtures** (three per language), **45 paired trials** (**90 mode
executions**) and **nine evidence snapshots**. Every case/repetition/mode key is
present exactly once, and both modes reference the expected case snapshot.
Snapshot digests, source content hashes, scoped reference identities and all 99
observation identities/expected values were checked. The original measurement
artifact was not regenerated during checkpoint testing.

Verified SHA-256 hashes of the original artifact bytes:

| Artifact | SHA-256 |
| --- | --- |
| Protocol | `880420364a2d53311ef5d12cfdfd2368ed8778fbfc08caf2695fea44f95a073a` |
| Corpus | `0c5bf54b4ea26818d2087d33c0abc81957349e3df2457d229593944e8b9b9e28` |
| Evaluation test/harness | `5a8812a2711114c4e11204d7ff57bbac5314abc0c448287090b5fac0f67d7478` |
| Test-only helper | `17f60c2d07658b5a878ff8f6cdf4ed68f1d5a4b9d55818986f7c83e8838b74c8` |
| Saved measured results | `c25e178be87e668235109c60af8db1cf4d8e4473a7acec8341c406a78353eb61` |

Git's existing line-ending normalization stores the measured JSON with LF rather
than its original Windows CRLF bytes. Its **Git-blob SHA-256** is
`64f4cb873d040944edb2729ef18c0a23c361d81773018ac96d6872e6942fccc2`.
The staged JSON was compared in full with the original and is identical after
line-ending normalization, including every parsed value. The other four input
hashes above also match their staged Git blobs exactly. Use the original bytes or
the Git blobs, as appropriate, when verifying these hashes; a checkout that changes
line endings can change raw file hashes without changing measured data. No Git
configuration or artifact contents were changed to suppress this distinction.

Fresh combined regression command:

```powershell
$env:SAMANVAYA_MONGO_TESTS = '1'
Remove-Item Env:SAMANVAYA_PR_EVALUATION_REPORT -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe -m pytest tests/test_pr_multi_agent_evaluation.py tests/test_pr_workflow_api.py tests/test_pr_workflow_durability.py tests/test_pr_workflow_durability_mongo.py tests/test_pr_multi_agent.py -q --tb=short -p no:cacheprovider -p no:hypothesispytest
```

Result: **142 passed**, six existing Pydantic warnings, **24.17 seconds**, no skips.
This includes all **20 evaluation/adversarial tests**, the **122 workflow/API/
durability cases**, and all **four real-MongoDB cases**. Scoped Ruff and Mypy for
the two new Python files passed again. A first read-only integrity probe ran from
the repository root and could not load the backend settings; rerunning from the
configured backend directory completed the audit without changing settings.

Collection-only verification of the existing Hypothesis module was retried and
still exited 1 with the same Application Control native-DLL error. The previous
full backend result remains **3,189 passed, 111 skipped, one collection error**,
not a fresh complete-suite pass. No policy bypass, dependency downgrade or test
weakening was performed. Live GitHub/Ollama, inference accuracy/latency and Ollama
resource measurements remain unverified. The production **NO-GO** verdict and the
remaining readiness gates above are unchanged.

All existing application code compares unchanged with the baseline. Both backend
flags evaluate **False**; the frontend opt-in is unset (disabled), and its template
still specifies false. No production or actual environment configuration changed.
The checkpoint scope is exactly the six files in the deliverables inventory;
unrelated files remain excluded. The containing Git commit identifies this report
and its exact SHA is recorded in the checkpoint handoff. No next-phase branch,
merge, push, deployment or activation is authorized by this finalization.
