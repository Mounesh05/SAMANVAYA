# Hypothesis recovery and full backend regression verification

Date: 2026-11-15. Verification only.

- Branch: `codex/pr-multi-agent-task5`.
- Unchanged HEAD: `4a2f9ca1b5b80f70668c19acc00504462b7ae351`.
- Interpreter: `M:\Samanvaya\backend\.venv\Scripts\python.exe`, verified against
  `sys.executable`; Python **3.12.10**.
- Hypothesis **6.170.14**, pytest **9.0.3**. No versions changed.

**The Hypothesis native-DLL blocker is resolved in this environment. The full
configured backend regression suite now passes with exit code 0.** Optional
Docker integrations remain skipped; this does not establish production rollout
readiness or live GitHub/Ollama performance.

## Executed results

| Check | Passed | Failed | Skipped | Errors | Exit | Time |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Hypothesis import | Successful | — | — | 0 | 0 | — |
| Previously blocked module collection | 11 collected | — | — | 0 | 0 | 0.39 s |
| Previously blocked module execution | 11 | 0 | 0 | 0 | 0 | 0.85 s |
| Full backend, established harness | 3,200 | 0 | 111 | 0 | 0 | 61.42 s |
| Task 5 + Task 2–4 focused regressions | 142 | 0 | 0 | 0 | 0 | 9.68 s |
| AI-run authorization/tenant isolation + HR designation permissions | 99 | 0 | 0 | 0 | 0 | 2.95 s |

Focused results include all **20 Task 5 evaluation/adversarial tests**, all **122
Task 2–4 workflow/API/durability tests**, and all **four real MongoDB integration
cases**. These cases are also included in the full suite; the counts above must
not be summed as unique coverage. MongoDB tests used the existing local test
configuration and their test-owned collections/cleanup.

Hypothesis imported from the selected environment's installed package. The module
execution header explicitly showed `hypothesis profile 'default'` and
`hypothesis-6.170.14` in the active plugin list. Neither the plugin nor the
collection-error gate was disabled. Test assertions, deadlines, examples and skip
conditions were not altered. Windows security settings were not inspected or
changed by this verification; the manual change was reported by the user.

## Full-suite comparison and remaining skips

The prior [Task 5 report](./2026-11-14-pr-multi-agent-evaluation-readiness.md)
recorded **3,189 passed, 111 skipped and one Hypothesis collection error**, exit 1.
The new result adds exactly the **11 previously uncollectable tests** and removes
the collection error. No executed test failed, so there is no new failure to
classify as a regression or pre-existing defect. The earlier Hypothesis timing
sensitivity did not reproduce; no timing policy was changed.

The full suite emitted **197 existing warnings**, principally Pydantic/datetime
deprecations and warnings about a model named `TestingEvidence` not being a pytest
test class. These are warnings, not collection errors. They remain unchanged from
the prior run.

A separate read-only collection inventory succeeded with **3,311 cases** and
identified exactly **111 active existing skip markers**, all Docker opt-in checks:

| Existing marker reason | Cases |
| --- | ---: |
| Trusted fixtures require Docker and both prebuilt images | 3 |
| Trusted syntax fixture requires Docker and Node image | 1 |
| Trusted unsupported-contract fixtures require Docker images | 12 |
| Trusted stateful fixtures require Docker images | 3 |
| Rebuilt pinned Docker workers; submitted source never runs on host | 20 |
| Isolated Linux Docker host and rebuilt independent-v1 workers | 4 |
| Docker and rebuilt pinned worker images | 56 |
| Approved isolated Linux Docker worker images | 9 |
| Running Linux Docker backend and built worker images | 3 |

The existing `SAMANVAYA_DOCKER_BENCHMARK_TESTS` opt-in remained unset. No previously
failing test was newly skipped, no integration skip was counted as a pass, and no
Docker worker or submitted developer source was executed for this verification.
Live GitHub/Ollama operation, model accuracy/latency/resource benefits, replica-set
failover and production capacity remain unverified.

## Commands and environment

Commands ran from the backend directory. Existing test fixtures set the test
MongoDB URI to `mongodb://localhost:27017` and database to `samanvaya_test`.
`SAMANVAYA_MONGO_TESTS=1` enabled the real MongoDB cases.

```powershell
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_DISABLE_PLUGIN_AUTOLOAD -ErrorAction SilentlyContinue
Remove-Item Env:SAMANVAYA_PR_EVALUATION_REPORT -ErrorAction SilentlyContinue
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
$env:SAMANVAYA_MONGO_TESTS = '1'

.venv/Scripts/python.exe -c "import sys, hypothesis; print(sys.executable); print(hypothesis.__version__)"
.venv/Scripts/python.exe -m pytest tests/test_qa_workflow_multi_language_bugfix.py --collect-only -q
.venv/Scripts/python.exe -m pytest tests/test_qa_workflow_multi_language_bugfix.py -v

.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py

.venv/Scripts/python.exe -m pytest tests/test_pr_multi_agent_evaluation.py tests/test_pr_workflow_api.py tests/test_pr_workflow_durability.py tests/test_pr_workflow_durability_mongo.py tests/test_pr_multi_agent.py -q --tb=short -rs -p no:cacheprovider
.venv/Scripts/python.exe -m pytest tests/test_ai_run_security.py tests/test_hr_designation_permissions.py -q --tb=short -rs -p no:cacheprovider
```

The full run used the unchanged established harness, including its existing audit
write isolation and Windows reporting-ID shortening. It did **not** use
`--continue-on-collection-errors` or disable the Hypothesis plugin. The existing
cache-provider setting is unrelated to Hypothesis and does not skip tests.
The original Task 5 measurement JSON was not regenerated.

## Acceptance and restrictions

- **Hypothesis environment blocker: RESOLVED**, demonstrated by import, collection,
  standalone execution and the full suite.
- **Full backend regression acceptance: ACHIEVED for the existing configured
  suite**, with the 111 explicitly optional Docker checks still unverified.
- **Multi-agent and authorization regression acceptance: PASSED** within the
  tested scope, including revoked access, ownership/project/tenant isolation,
  HR restrictions, provenance, idempotency, recovery and fencing.
- Both `PR_MULTI_AGENT_INTERNAL_ENABLED` and `PR_MULTI_AGENT_MANUAL_ENABLED` have
  default **False** and effective value **False**, checked directly after testing.
- No application source, tests, dependencies, evaluation artifacts, environment
  files or Windows security settings were modified. Only this new verification
  report was written; earlier reports remain historical records.
- No branch, commit, push, merge, deployment or production activation occurred.

The environment-related readiness gate from Task 5 is now satisfied. The remaining
live-model, integration and operational rollout gates are not resolved by a green
backend suite. Keep multi-agent production functionality disabled.
