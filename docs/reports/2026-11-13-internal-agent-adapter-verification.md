# F07/F08 internal adapter verification

13 November 2026. Review handoff for the isolated internal adapter scope.

## Reviewed baseline

Read the Phase 0 audit, the F03–F06 verification report and the F01/F02 security
verification report. Reviewed the uncommitted F01/F02 source, provenance models,
repository filters and tests before editing the F07/F08 implementation.
The acceptance rerun passed **138 tests**, with 96 warnings, in 5.41 seconds.
No new blocker was identified within that documented security scope.

Accepted and saved the 11-file F01/F02 change as the separate commit
`127d9efc5a0154d6808ec89fbe999defac7d7228`, with subject
`fix: enforce AI-run ownership and evidence provenance`. Its parent is the
reviewed F03–F06 commit `56264de7614c1bff83b3f9823707ba371314714d`.

Created `codex/internal-agent-adapters` from the saved security commit.
The F07/F08 changes form a separate reviewed checkpoint on this branch. Pre-existing unrelated untracked
files and the Phase 0 audit deliverables were preserved.

## F07 findings and changes

The initial adapter regression run reproduced **32 failures and 1 pass**.
Direct GitHub and background code-quality callers omitted the user permission
context. They discarded node failures, and GitHub/CI log persistence could mark
empty or invalid interpretation as completed.

### User authority

GitHub HTTP handlers pass their authenticated actor into single and batch sync.
The analysis adapter reloads the current account and resolves its current role,
permissions, project membership and organization through the existing F01/F02
boundary. Removed or inactive users, HR technical analysis, missing authority,
operator-shaped identities and unrelated projects fail before model invocation.
The trigger email supplies audit information and confers no authorization.

Background code-quality work retains the initiating employee ID and reloads
that account before the optional interpretation step. Code-quality initiation
and technical AI permissions are checked at that point. The original code-agent
permission guard still executes for every authorized call.

### Server-owned automation

The GitHub sync service constructs a `GitHubAutomation` job for internal calls
that have no user actor. Its scope fixes one project, repository and full
40-character commit SHA obtained by the sync service. The resolver requires a
current active project with organization provenance and an exact, unambiguous
configured repository binding. A mismatched revision or repository is rejected.

Its identity is `github-automation:<project_id>`. It receives only
`VIEW_AI_EVALUATION` for the code interpretation step and an accessible-project
list containing that project. User dictionaries cannot impersonate that
server-side job type. An explicit user actor is always checked as a current
account and cannot fall back to automation after denial.

The job context is an in-process server capability. Its legitimate entry point
and repository connection configuration remain trusted server boundaries.

### Failure handling and persistence

The shared adapter applies the existing strict specialist schemas to returned
interpretations. Explicit statuses distinguish completed, failed, unavailable
and skipped outcomes. Missing evidence, node errors, empty text, invalid values,
provider failures and incompatible engine data cannot become completed AI runs.
Error responses use sanitized codes and omit raw provider exception data.

Direct node calls receive copied state, including engine results and permission
context. A regression mutates those node inputs and verifies that the original
quality and risk measurements remain intact.

GitHub AIRuns now contain the F01 access version, authenticated or server-owned
owner, resolved project and organization. Missing authorization produces no
unowned AI record. Authorized failed interpretations produce failed records
with an error message. Internal observations are labeled `SERVER_OBSERVED`,
caller context is explicitly unverified and model interpretation remains
`ADVISORY`. These records do not acquire `SERVER_VERIFIED` authority from labels
inside incoming evidence.

A successful deterministic code-quality run can have a failed optional
interpretation. Its existing run status represents deterministic analysis, and
the separate `ai_status`, `ai_analysis.status` and errors expose the AI outcome.
The stored AI scope is checked again on run-detail and latest-run reads.
HR, cross-organization readers and unprovable legacy AI scopes receive withheld
AI fields with an unavailable status. The existing static-result access rules
continue to govern static fields. Skipped AI retains its skipped status.

CI/CD log persistence uses the same strict outcome checks, retains private
ownership and unverified uploaded-input provenance, and records failures as
failed AIRuns. Responses add `ai_status` and `ai_errors`. Provider or persistence
exceptions clear interpretation fields while retaining deterministic log
measurements. The shared log-analysis function enforces technical AI access,
including when reached through the file-upload route.

Source references include [authority resolution](../../backend/domain/services/internal_agent_adapter.py#L36),
[interpretation validation](../../backend/domain/services/internal_agent_adapter.py#L84),
[GitHub analysis](../../backend/domain/services/github_analysis_service.py#L67),
[background work and read filtering](../../backend/api/routes/code_quality.py#L303) and
[CI/CD analysis](../../backend/api/routes/cicd_logs.py#L79).

## F08 units and schema compatibility

The inspected QualityEngine output contains `quality_score`, `quality_grade`,
`dimension_scores` and `penalties`. Its aggregate score is the existing clipped
and rounded `100 - weighted penalties`, with weights from the existing project
configuration. Individual dimension scores are the existing clipped and rounded
`100 - dimension penalty`.

| QualityEngine dimension | Score units | Minimum | Maximum |
|---|---|---|---|
| `static_security` | Independent quality index | 0 | 100 |
| `testing` | Independent quality index | 0 | 100 |
| `complexity` | Independent quality index | 0 | 100 |
| `architecture` | Independent quality index | 0 | 100 |
| `duplication` | Independent quality index | 0 | 100 |

The corresponding five penalties use unweighted 0–100 penalty units.
Dimension scores are independent indices. Their sum is not an aggregate score.

| Legacy QualityBreakdown dimension | Units | Minimum | Maximum |
|---|---|---|---|
| `correctness` | Advisory points | 0 | 20 |
| `maintainability` | Advisory points | 0 | 20 |
| `security` | Advisory points | 0 | 20 |
| `testing` | Advisory points | 0 | 15 |
| `performance` | Advisory points | 0 | 10 |
| `architecture` | Advisory points | 0 | 10 |
| `readability` | Advisory points | 0 | 5 |

The legacy maximum total is 100 points. The two schemas have different names
and meanings. Engine `static_security` provides no independent split into
legacy correctness, maintainability and security. Complexity and duplication
lack matching legacy dimensions, while performance and readability lack
matching engine dimensions. Shared testing/architecture names have different
units. A lossless translation cannot be established from these contracts.

### Versioned representation

New deep reports identify `quality_representation` as `quality-engine-v1` and
store the exact five dimensions, penalties, aggregate score and grade in
`engine_quality`. Their legacy `quality_breakdown` is null. No legacy
contributions or absent dimensions are synthesized.

Historical reports retain `legacy-advisory-v1` as the default representation,
and valid historical seven-dimension payloads continue to parse and roundtrip
with their original values. New consumers must branch on the representation
field and handle an absent legacy breakdown.

The complete RiskEngine result is retained in `engine_risk`. The explicit
`engine_results_v1` envelope carries unchanged raw quality and risk outputs
through the GitHub sync result and stored deep output, including when an engine
schema cannot be represented by the typed v1 report. Unsupported dimensions
produce an explicit compatibility failure and preserve their raw measurements.

Quality/risk totals, risk level and confidence in the report come from the
existing engines/evidence. Model-generated numerical fields cannot replace
them. The legacy `failure_risk` wire name is retained, with its description
corrected to the engine's 0–100 risk-index units.

Existing revision-pinned `source_files` and diagnostics are passed to the deep
analyzers, keeping their inputs aligned with the authorized PR context.
Deterministic deep results survive model unavailability. Formula, weighting,
risk configuration and scoring activation code have no diff in this branch.

Source references include [QualityEngine output](../../backend/intelligence/quality_engine.py#L44),
[legacy dimensions](../../backend/domain/models/code_quality_report.py#L12),
[versioned engine models](../../backend/domain/models/code_quality_report.py#L40) and
[deep report adapter](../../backend/domain/services/github_analysis_service.py#L292).

## Changed files

| File | Change |
|---|---|
| `backend/domain/services/internal_agent_adapter.py` | Current-account/server-job scope, strict outcomes, copied node state and scoped observation persistence |
| `backend/domain/services/github_analysis_service.py` | Authorized direct callers, explicit failure handling and independent versioned engine results |
| `backend/domain/services/github_sync_service.py` | Pass user actor or server-owned job, preserve result status/scope and raw engine envelope |
| `backend/api/routes/github.py` | Forward authenticated actors for single/batch user calls |
| `backend/api/routes/code_quality.py` | Pass actor into background work, record separate AI status and gate AI fields on reads |
| `backend/api/routes/cicd_logs.py` | Validate outcomes before completed persistence, explicit AI status/errors and technical-access guard |
| `backend/domain/models/code_quality_report.py` | Exact engine-v1 types, preserved legacy parsing, separate engine risk and interpretation status |
| `backend/tests/test_internal_agent_adapters.py` | 62 adapter/security/unit/persistence regression cases, including the seven automation review cases |
| `backend/tests/test_function_discovery_integration.py` | Give the outage test legitimate authority and assert the explicit unavailable outcome |
| `frontend/src/pages/github/GitHubSyncPage.test.jsx` | Five normal-form submission/rendering checks for versioned, historical, absent and unavailable results |
| This report | Baseline acceptance, units, results and review handoff |

## Executed verification

Python checks used the existing Python 3.12 environment. The complete backend
run used the existing baseline runner with its audit-log isolation and Windows
test-ID handling. Mongo opt-in was enabled, and Docker opt-in was disabled.

| Check | Result |
|---|---|
| F01/F02 acceptance before commit | 138 passed, 96 warnings, 5.41 s |
| Initial F07/F08 regressions against the saved baseline | 32 failed, 1 passed |
| Focused adapter, discovery and F01/F02 security run before the last legacy-scope case | 148 passed, 52 warnings, 5.38 s |
| Implementation complete backend suite before added checkpoint cases | **3,051 passed, 111 skipped**, 197 warnings, 59.72 s |
| Checkpoint complete backend suite | **3,057 passed, 1 timing failure, 111 skipped**, 197 warnings, 184.81 s |
| Checkpoint focused retry including the timing-sensitive property, all 62 adapter cases and 85 security cases | **148 passed**, 52 warnings, 24.83 s |
| Added frontend compatibility checks | **5 passed**, 7.24 s |
| Complete frontend tests after checkpoint review | **177 passed**, 24 files, 46.35 s |
| Frontend build | Passed, exit 0 |
| Frontend lint | Exit 0, 10 existing warnings |
| Ruff on changed runtime and test files | Passed |
| Whole-backend Ruff F821/E9 | Passed |
| Whole-backend default Ruff | 160 existing findings |
| Scoped Mypy for adapter and report contracts | Passed for 2 source files |
| Whole-backend Mypy | 2 existing blocking errors |
| Editor diagnostics | No errors reported in the checked changed runtime/new test files |
| `pip check` | No broken requirements found |
| `git diff --check` | Passed |

Focused and complete counts overlap. Frontend tests used the documented
two-worker, 30-second-timeout settings. Native Mongo process-recovery,
PR-job deduplication and scoring-writer arbitration checks are included in the
complete backend run. They use owned temporary collections and cleanup.

The tests cover successful and failed user/automation calls, actual Code-node
permission guards, current permission removal, forged identities, missing
evidence, node mutation, empty/invalid model output, outages, CI persistence
failure, HR uploads, AI read redaction, incompatible units and historical
report parsing. They also exercise GitHub sync through actual AIRun persistence.

### Existing baseline failures

Default Ruff retains 84 F401, 27 F811, 24 F841, 19 E402, 2 E712, 2 F541,
1 E731 and 1 E741 findings. Mypy still stops on the missing
`domain.models.qa_ci_config` module and duplicate discovery of
`services/transfer_service.py`. Its blockers prevent a whole-repository
type-clean conclusion. Existing Pydantic and naive-UTC warnings persist.

The checkpoint whole-suite run reported Hypothesis `FlakyFailure` in
`test_qa_workflow_multi_language_bugfix.py::test_multi_language_detection_property`.
One example took 706.03 ms against its existing 200 ms deadline, and Hypothesis
reported that the failure did not reproduce on its subsequent call. A focused
retry of that unchanged test together with all adapter/security review cases
passed all 148 cases. The retry retained the source and deadline. This timing
failure remains recorded separately from the three accepted review conditions.

### Live integration limits

Live GitHub retrieval, live Ollama generation and live Docker workers were
unverified in this scope. GitHub transport boundaries and model responses use
controlled test data. The reviewed provider tests separately exercise real
loopback HTTP timeouts. Skipped integration cases remain unverified.

Automation relies on trusted server entry points and connected repository
configuration. Existing broader static-data access helpers elsewhere retain
their documented legacy behavior. The new AI-field gate enforces the F01
boundary for optional code-quality interpretation data.

## Acceptance and review

F07 callers establish explicit authority, retain the Code-node guard, propagate
failure states and avoid false-completed AI records. F08 preserves engine
measurements in explicit versioned units and preserves supported historical
report parsing. Existing generic AI responses retain their six task identifiers
and single-agent dispatch. Signed performance artifact exclusions remain covered
by the security regression suite.

New compatibility fields include `quality_representation`, `engine_quality`,
`engine_risk`, `engine_results_v1`, `ai_status` and `ai_errors` on their relevant
report/result surfaces. Unauthorized or unprovenanced historical code-quality
AI text is withheld. Authorized static results remain available under their
existing endpoint rules.

## Checkpoint review conditions

The three requested review conditions passed their source and executable-test
checks and are accepted for the checkpoint commit. The whole-suite timing
failure and successful focused retry are recorded above.

| Condition | Evidence and acceptance scope |
|---|---|
| Server-owned automation identity | The sync service constructs the job and the HTTP routes forward the authenticated actor. Tests verify the exact service identity, single-project permission grant, actual Code-node permission guard and rejection of forged dictionaries. Seven additional cases deny wrong project/repository/revision, missing organization, inactive project and missing/ambiguous mappings before invocation or AI persistence. |
| Frontend versioned report handling | Five DOM tests submit the actual GitHub form and render its API result. The current JSON results view preserves the `engine-results-v1` envelope and original engine values, handles `quality-engine-v1` with a null legacy breakdown, and supports historical, failed, unavailable and absent results. Its presentation remains the existing JSON results view. |
| Historical AI-data visibility | Rerun adapter and F01/F02 security tests cover legacy records without owner/tenant provenance, private ownership, HR and cross-organization redaction, legacy quality-unit parsing, malformed historical scope and skipped status. Valid legacy report schemas remain readable, while AI text without established access provenance is withheld. |

The frontend checks use controlled API responses in the normal React component.
They establish compatibility for that results view. Live GitHub/Ollama/browser
integration remains outside the executed checks listed above.

## Reproduction

From `backend` in the configured environment, run the focused checks or the
complete available suite.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_internal_agent_adapters.py tests/test_function_discovery_integration.py tests/test_ai_run_security.py -q --tb=short -p no:cacheprovider
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
```

From `frontend`, run the existing checks.

```powershell
npm run test -- --run --maxWorkers=2 --testTimeout=30000
npm run build
npm run lint
```
