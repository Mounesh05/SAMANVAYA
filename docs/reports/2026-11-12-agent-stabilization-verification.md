# F03–F06 stabilization verification

Date 12 November 2026. Review requested before further implementation.

## Source and scope

The inspected base was `testing` at
`771b41cc037ed24e2b9b763021149c49f14a2267`, exactly the audited commit.
There were no tracked changes from that baseline before implementation.
The complete Phase 0 audit and all 837 lines of the supplied safe multi-agent
implementation specification were read before editing.

Work is on `fix/ai-provider-legacy-contracts`. A final checkout check found
`testing` selected at the same SHA, and the existing feature branch was restored
before verification finished. HEAD still identifies the audited base because
these changes are uncommitted.

Pre-existing untracked audit deliverables, `.vscode/`, `PROJECT.md`,
`TEST_INFRA.md`, `TEST_READY.md` and `empirical_harness.py` were preserved.

## Implementation decisions

### F03 provider contract

The real factory retains its existing `model`, `temperature` and `base_url`
parameters. Code and HR now call that supported signature. The pinned
`langchain_ollama.OllamaLLM` accepts JSON mode and rejects a schema dictionary
as its `format`, which was reproduced during implementation. JSON mode is
retained and strict response validation runs locally. The unpinned fallback
provider import was removed so inference uses the installed supported wrapper.

Source references are [provider](../../backend/agents/llm_provider.py#L19),
[Code](../../backend/agents/code_agent.py#L76) and
[HR](../../backend/agents/hr_agent.py#L80).

### F04 effective inference timeouts

The factory configures `client_kwargs.timeout` as 120 seconds. Tests inspect
connect, read, write and pool timeouts on both underlying HTTPX clients.
Loopback HTTP tests use the actual SDK, stall a received inference request and
verify sync and async read timeouts with a shortened test-only timeout. Another
test verifies cancellation propagation through the SDK's async invocation.

These are finite transport inactivity timeouts. An indefinitely trickling
response can exceed 120 seconds of total elapsed time. Async cancellation was
tested for the SDK call. Existing graph execution of synchronous specialist
nodes uses its existing executor, whose running synchronous work may continue
until its transport returns. Remote model computation cancellation and a global
wall-clock deadline were outside the verified scope. See
[transport tests](../../backend/tests/test_agent_provider_transport.py#L42).

### F05 CI/CD protocol compatibility

The specialist prompt requests the JSON contract used by the provider.
The parser also supports the existing named text sections when all required
fields are valid, including explicit confidence. Duplicate sections, incomplete
results and unsupported inline recommendation lists fail validation.
No default confidence is manufactured. Existing CI/CD execution authority and
the separate flakiness helper were preserved. See the
[CI/CD adapter](../../backend/agents/cicd_agent.py#L135).

### F06 strict specialist contracts

The shared internal `legacy-specialist-v1` models enforce required substantive
analysis, recommendation lists, known risk values and finite confidence within
0–1. Code advisory scores are bounded within 0–100, with legacy breakdown units
bounded to their existing dimensions. Unknown fields, unsupported versions,
boolean/string numerical coercion, duplicate JSON keys and non-finite values
are rejected. Optional absent numerical results remain null. Actual zeros are
preserved.

Engineering parser limits are 64 KiB per raw response, nesting depth 16,
16,000 characters for analysis, 2,000 for short fields/list items and 32 list
items. These limits were chosen for this stabilization and require reviewer
confirmation. They apply after a provider response is collected and provide
bounded parsing and validation. Generation resource usage remains a separate
limitation.

Supported unambiguous JSON, fenced JSON, prose-wrapped JSON and textual message
content retain legacy adapters. Invalid responses raise an explicit validation
failure. The retained third `safe_parse` argument supplies no missing facts.
Nodes return sanitized `MODEL_TIMEOUT`, `INVALID_MODEL_RESPONSE` or
`MODEL_UNAVAILABLE` errors and clear previous output fields. See
[schemas](../../backend/agents/parsers.py#L30) and
[failure handling](../../backend/agents/parsers.py#L139).

## Files changed

| File | Change |
|---|---|
| `backend/agents/llm_provider.py` | Supported provider construction and effective sync/async transport timeouts |
| `backend/agents/parsers.py` | Versioned strict bounded models, explicit validation errors and sanitized node failures |
| `backend/agents/code_agent.py` | Supported factory call, strict validation, absent numerical values preserved as unknown |
| `backend/agents/hr_agent.py` | Supported factory call and strict validation with existing authorization/filtering |
| `backend/agents/cicd_agent.py` | JSON prompt and validated legacy section adapter |
| `backend/agents/qa_agent.py` | Strict validation and explicit model failures |
| `backend/agents/devops_agent.py` | Strict validation and explicit model failures |
| `backend/agents/meeting_agent.py` | Strict validation and explicit model failures |
| `backend/tests/test_agent_stabilization.py` | 149 factory, six-task, parser, permission and HR-isolation cases |
| `backend/tests/test_agent_provider_transport.py` | 3 real loopback HTTP timeout/cancellation cases |
| `backend/tests/test_agent_stabilization_api.py` | 43 invocation shape, permission, health and persistence cases |
| `docs/plans/2026-11-12-agent-stabilization.md` | Scoped implementation plan and limits |
| This report | Verification and review handoff |

## Executed verification

Python checks used the existing backend Python 3.12 environment.
The new regression tests were first exercised against the defects, with
103 failures and 5 passes in the initial cleanly collected red run.
Subsequent tests exposed the wrapper's unsupported schema-dictionary format
and a test actor lacking existing HR permissions. Provider construction and
test setup were corrected without changing authorization policy.

| Check | Final observed outcome |
|---|---|
| Three new modules plus existing `test_ai_authorization.py` | **205 passed**, 76 warnings, 5.76 s |
| Complete backend baseline runner | **Collection failed** in `test_qa_workflow_multi_language_bugfix.py`; Windows Application Control blocked Hypothesis 6.170.14's `_native` DLL |
| Remaining backend suite with that module explicitly excluded and its plugin disabled | **2,900 passed, 111 skipped**, 150 warnings, 34.78 s |
| Native MongoDB checks | Included successfully with `SAMANVAYA_MONGO_TESTS=1`; PR job deduplication, lifecycle writer arbitration and two process-recovery cases |
| Complete frontend tests | **172 passed**, 23 files, 14.73 s |
| Frontend build | Passed, exit 0 |
| Frontend Oxlint | Exit 0, 10 existing warnings |
| Ruff on `agents` and the three new test files | Passed |
| Complete backend default Ruff | **160 existing findings** |
| Complete backend Ruff F821/E9 | Passed |
| Scoped provider/parser Mypy | Passed for 2 source files with imported modules followed silently |
| Complete backend Mypy | **2 blocking errors**, further checking prevented |
| `pip check` | No broken requirements found |
| `git diff --check` | Passed |

The 195 new tests are included in both focused and broad counts.
Counts from those runs must not be added together. The broad run explicitly
excluded the blocked module. It does not establish a complete backend pass.
The 111 skipped tests remain unverified. No dependency or Windows security
policy was changed to work around the DLL restriction.

The broad run reused the existing baseline runner to isolate cached audit-log
writes and shorten oversized Windows test IDs. Mongo tests owned temporary
collections. Docker opt-in was disabled. Live Docker workers and live Ollama
generation were unverified in this implementation. Model scenarios used
synthetic responses, with real local HTTP transport for timeout checks.

### Remaining baseline diagnostics

Default Ruff findings retain the audited distribution of 84 F401, 27 F811,
24 F841, 19 E402, 2 E712, 2 F541, 1 E731 and 1 E741.

Full Mypy still reports the missing `domain.models.qa_ci_config` import in
`api/routes/qa_ci_provisioning.py` and duplicate module identity for
`services/transfer_service.py`. Removal of the unsupported provider fallback
eliminated the audited `langchain_community.llms` diagnostic. Mypy stops on the
remaining blockers, so further whole-repository type findings remain unknown.

Existing Pydantic configuration and naive-UTC deprecations remain. The API
regression tests exercise existing AIRun creation and add 72 occurrences of its
datetime warning. The editor diagnostics tool was unavailable, so verification
used executed tests, Ruff and Mypy.

## Compatibility and deferred risks

The task registry remains exactly `code_review`, `qa_analysis`, `devops_risk`,
`meeting_insights`, `cicd_analysis` and `hr_assistant`. The existing single-agent
graph, permission checks and HR forced routing/filtering remain operational.
Tests verify technical evidence is excluded from HR prompts.

The generic invocation response retains its nine existing keys, 200 response
with errors in the body, 403/503/422 behavior and optional persistence.
Valid model results can be saved as completed advisory runs. Malformed,
unsupported or unavailable results through this endpoint are saved as failed,
with null analysis/confidence and explicit error information. The internal
schema version stays inside the parser contract. Public request/response
schemas and deterministic scoring authority were preserved.

The following audited risks still require their own reviewed changes.

| Finding | Remaining risk |
|---|---|
| F01 | AI-run reads can lack private ownership/tenant enforcement, including the audited PM scope bypass |
| F02 | Invocation accepts caller-controlled project/evidence provenance and verification flags |
| F07 | Internal adapters can omit permissions, ignore node errors and persist a completed status despite failed analysis |
| F08 | The deep-report adapter can mix engine dimension units with legacy breakdown limits |

Strict model validation does not repair client evidence trust or every internal
persistence caller. In particular, F07 prevents an application-wide claim that
every failed AI analysis is stored with a failed status. No model-produced
verification flag is accepted by these specialist schemas. The generic API
tests verify failed persistence within their stated endpoint scope.

## Acceptance assessment and review request

| Acceptance area | Assessment |
|---|---|
| F03 actual Code/HR signature and provider construction | Met by real-factory tests |
| F04 finite sync/async transport settings and stalled-request behavior | Met within transport scope, with the elapsed-time and graph-cancellation limits above |
| F05 JSON protocol and supported legacy sections | Met by validation and regression tests |
| F06 strict output/failure contracts across six specialists | Met within specialist and generic-invocation scope |
| Single dispatch, public shape, HR boundary and permissions | Met by focused regressions |
| Scoring/algorithm/workflow independence | Runtime diff confined to eight agent files; existing available subsystem tests pass |
| Full existing backend verification | Pending resolution of the blocked Hypothesis test environment |

The implementation is ready for scoped code review. Full verification remains
conditional on the blocked backend module and the infrastructure limits above.
Review the parser bounds, legacy adapters and transport-timeout scope before
acceptance. Production activation and scoring policies were preserved.

Stop here for user review before further implementation.

## Reproduction commands

From `backend`, using its configured environment, run the focused regressions.
The plugin disablement below avoids the independently blocked Hypothesis
terminal hook in this Windows environment.

```powershell
$env:PYTEST_ADDOPTS='-p no:hypothesispytest'
.venv/Scripts/python.exe -m pytest tests/test_agent_stabilization.py tests/test_agent_provider_transport.py tests/test_agent_stabilization_api.py tests/test_ai_authorization.py -q --tb=short -p no:cacheprovider
```

For the explicitly reduced broad run, use the existing runner.

```powershell
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
$env:PYTEST_ADDOPTS='-p no:hypothesispytest --ignore=tests/test_qa_workflow_multi_language_bugfix.py'
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
```

For a complete rerun in an environment where Hypothesis loads, clear
`PYTEST_ADDOPTS` and use the same runner. The unmodified Phase 0 characterization
probe describes old defects and is historical audit evidence.
