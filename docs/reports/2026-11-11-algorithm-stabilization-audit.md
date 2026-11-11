# SAMANVAYA Phase 1–5 stabilization audit

Date: 2026-11-11. Branch: `testing`. Baseline commit: `7c62b4e9e979c1f6690ce22720d4f82608fb8a14`.

This report covers an audit and localized bug fixes, not a redesign. Production changes were preceded by failing regression tests. The original unrelated local notes/editor files were preserved. The stabilization changes have not been committed or pushed.

**Final verification status:** complete. The final full backend run passed **2,547 tests, with 0 failed and 0 skipped** (40 existing warnings). All **157 frontend tests** passed. Production build and lint exited successfully. The 18 defect groups below are fixed; verification limits and supplemental static diagnostics remain explicit.

## A. Confirmed bugs and fixes

The backend regression names below are in [test_algorithm_stabilization.py](../../backend/tests/test_algorithm_stabilization.py). UI regressions are in [prAlgorithmIntelligence.test.jsx](../../frontend/src/tests/prAlgorithmIntelligence.test.jsx). Severity reflects the demonstrated consequence: P0 can change trust, applicability or authoritative findings; P1 affects lifecycle, reporting, navigation or CI operation.

| ID / severity | Component | Confirmed bug and root cause | Localized fix | Regression evidence |
|---|---|---|---|---|
| S01 / P0 | Phase 4 → Phase 1 policy preparation | Every client constraint/unknown whose ID started with `discovered-` was discarded. A valid manual mandatory latency limit could disappear and leave candidates eligible. | Replace only concrete imported IDs from current/prior server reports. Preserve unrelated manual IDs and unknowns. | `test_manual_discovered_prefix_constraint_is_not_silently_discarded`; `test_user_unknown_requirement_with_discovered_prefix_remains_unknown` |
| S02 / P0 | Requirement applicability | Parsed bytes were checked, but supplied Git revision/path identity was accepted without server GitHub provenance. One bound candidate could also determine the scope for an unbound second candidate, excluding an applicable constraint. | Require existing exact-revision GitHub provenance and matching repository, revision, entrypoint and source hash. Establish excluding function/revision scope only when all candidates are bound. | `test_unverified_revision_label_cannot_exclude_an_approved_requirement`; `test_one_bound_candidate_cannot_establish_an_excluding_revision_for_unbound_candidate`; positive `test_trusted_single_candidate_revision_can_establish_requirement_scope` |
| S03 / P0 | Contract and requirement authority | Approved records were selected by project ID without checking the project's current organization. Moving a project could leave old-organization approvals effective. | Compare stored approval ownership with the current project organization; return conflicting/excluded evidence pending renewed review. No authorization role was relaxed. | `test_function_contract_approval_from_a_different_current_organization_is_not_resolved`; `test_requirement_approval_from_a_different_current_organization_is_not_enforced` |
| S04 / P0 | Phase 3 function bindings | A class/nested function named `solve` could bind the module-level worker entrypoint `solve` because only the short name and whole-file hash were checked. | Check the qualified identity against the supported module entrypoint before execution. | `test_nested_function_reference_cannot_bind_a_different_module_entrypoint` |
| S05 / P1 | Phase 2 ranges → Phase 5 changed functions | Whole-line slicing marked an unchanged same-line sibling as changed and omitted decorator-only changes. | Add optional end-column/declaration-start metadata and slice Python UTF-8 / TypeScript UTF-16 ranges correctly. Legacy snapshots retain their fallback. | `test_adjacent_function_change_does_not_mark_unchanged_sibling` (Python/JS/TS and Unicode cases); `test_decorator_change_is_a_changed_python_implementation` |
| S06 / P1 | Requirement supersession | After an interrupted predecessor update and another replacement, an earlier approved ancestor became active again. Superseded intermediate revisions were ignored when resolving the chain. | Use intact independently approved supersession history through intermediate superseded records. Preserve fork/conflict reporting and immutable contents. | `test_supersession_chain_does_not_reactivate_an_ancestor_after_partial_write` |
| S07 / P1 | Policy reevaluation | Retiring imported workload coverage removed its constraint but retained its old IDs in the policy's required dataset union. | Record the original explicit dataset scope in report provenance, refresh using the last decision's report, and retire imported scope while preserving manual requirements. | `test_reevaluation_retires_superseded_workload_coverage_without_removing_manual_checks` |
| S08 / P0 | PR sync and webhook side effects | A sync rejected as stale still attached old risk/model output to the current PR and could generate new recommendations/notifications from it. | Return current metadata with an explicit superseded outcome; stop stale analysis and webhook side effects. Update the existing sync response message. | `test_superseded_sync_does_not_attach_old_ai_results_to_current_pr`; `test_superseded_worker_event_does_not_generate_new_risk_recommendations` |
| S09 / P0 | PR finding currency | A superseded manifest could retain pending recommendations while the PR metadata still matched. Reevaluation could disqualify candidates while cached PR summaries/recommendations retained the earlier finding. | Invalidate superseded recommendations, check manifest and decision revisions on reads, derive PR finding status from the current project-scoped decision, and expose its reference. Preserve original snapshots as obsolete history. | `test_superseded_manifest_invalidates_recommendations_before_pr_metadata_updates`; `test_history_labels_superseded_manifest_as_historical_before_pr_catches_up`; `test_new_decision_revision_cannot_leave_old_pr_finding_authoritative` (two surfaces) |
| S10 / P1 | Job expiration | An expired queued job failed its claim predicate but stayed pending unless a later history read expired it. The PR cache could remain pending too. | Share a bounded, guarded expiration helper between execution and history reads, updating only the matching PR pointer. | `test_expired_queued_job_is_failed_when_claimed_without_a_history_read` |
| S11 / P1 | Partial static evidence | A completed comparison could hide parser errors/truncated discovery in the PR summary, which omitted the full discovery report. | Propagate incomplete base/head discovery through the existing partial-analysis flag and accurate UI wording. | `test_partial_discovery_is_visible_on_completed_pr_analysis` |
| S12 / P1 | Mixed execution outcomes | A successful comparison took priority over another worker failure, labeling the overall job completed. | Give infrastructure failure the appropriate parent status while retaining successful per-function findings and evidence. | `test_one_worker_failure_does_not_make_the_entire_pr_analysis_completed` |
| S13 / P1 | Workload-difference UI | Deltas were displayed for eligible candidates even when the decision reported incompatible methodologies, including tradeoff-only cross-runtime results. | Honor the engine's comparison status and matching nonempty methodology fingerprints before showing differences. | UI: `does not compute deltas when the decision reports incomparable methodologies`; `does not compare tradeoff-only measurements from different runtimes` |
| S14 / P1 | UI failure states | React Query cached success data remained displayed after an access-denied refetch, both for PR findings and comparison evidence. | Suppress stale success content when its authoritative request fails; retain the error state. | UI: `does not display cached successful findings after project access is refused`; `does not show a cached comparison after its evidence request is refused` |
| S15 / P1 | Evidence navigation | PR function evidence references were plain text with no route to their existing discovery snapshots. | Link to the existing authorized run-detail route for current/previous function evidence. | UI: `provides working navigation from a PR function to its existing discovery snapshots` |
| S16 / P1 | Recommendation HTTP serialization | Persisted recommendation reads included MongoDB `_id` / `ObjectId`, producing HTTP 500 in FastAPI JSON encoding. | Exclude Mongo-only fields at the repository read projection, consistent with the existing base repository. | `test_existing_recommendation_api_serializes_persisted_algorithm_findings` (actual ASGI HTTP response) |
| S17 / P1 | Existing QA workflow | Committed merge markers made the workflow invalid YAML. Its selected multi-language path also omitted installation of the existing pinned backend TypeScript parser required by Python-triggered JS/TS tests on a fresh checkout. | Resolve only conflicting workflow sections, retain the existing runner/guards/scans, and bootstrap the existing parser from its lockfile before tests. | `test_existing_qa_workflow_is_parseable_and_preserves_multilanguage_checks`; `test_qa_workflow_bootstraps_existing_static_parser_before_python_tests`; Bash syntax check |
| S18 / P0 | Legacy recommendation API boundary | Entity/item reads and PM/CEO actions on algorithm findings could bypass the strict project/organization scope already enforced by the algorithm APIs. | Reuse the existing algorithm guard for algorithm-generated recommendations on all read/action paths. Preserve existing ownership/role checks and ordinary recommendation behavior; return the actual forbidden outcome. | `test_legacy_recommendation_route_cannot_bypass_algorithm_organization_scope` (15 route/role cases); positive `test_authorized_existing_pm_recommendation_actions_remain_available` (three actions) |

These are defect groups, not a count of security vulnerabilities. The underlying evidence and actual impact were checked before assigning a fix. Other suspected issues were not called fixed merely because they were listed in the brief.

## B. Verified working behavior

- **Phase 1:** correctness-first eligibility; mandatory PASS/FAIL/UNVERIFIED semantics; optional measurement availability; unknown budgets remain conditional; workload-scoped comparisons; no universal winner; immutable raw evidence and appended decision history. Legacy aggregate output cannot override the policy decision.
- **Phase 2:** Python/JS/TS structural discovery remains static; patterns/tasks stay observed/inferred; arbitrary/custom functions remain analyzable; parser absence/errors, limits and legacy `not_analyzed` cases are covered. Source hashes identify parsed bytes. Updated range metadata is additive, not a new recognition system.
- **Phase 3:** approved finite reachability, shortest-path and traversal-order checks execute in isolated workers. Wrong DFS paths/order fail the approved validator. Explicit set/multiset/finite acceptable-output modes remain separate. Unsupported validators and incomplete evidence remain unverified.
- **Phase 4:** role/project/organization access, independent approvals, fingerprint checks, unrelated tasks, cumulative bounds, metric identity, source replacement and mandatory imports are covered. Natural-language/repository proposals do not approve requirements.
- **Phase 5:** opened/synchronize/reopened dispatch, disabled AI, low-risk PRs, exact revisions, deduplication, previous/current lookup, insufficient/unsupported cases, stale results, failure cleanup and project-mapped views are covered. Current decision revisions govern current PR interpretation.
- **Execution:** Linux Docker workers retain their existing non-root, network-disabled, read-only, CPU/memory/PID-limited configuration. No runner/security settings were weakened and no repository dependency installation was added to runtime analysis.
- **Actual Docker fault injection:** unavailable Memray result extraction retained usable timing and validated compatibility. Additional real timeout/cancellation checks confirmed owned containers were removed and benchmark leases released. Candidate code in these checks executed only inside the existing workers.
- **Existing behavior:** full project-management, authorization, code-quality, manual numeric sorting and generic-function regression tests ran. No new API or benchmark framework was introduced.
- **Browser:** actual React components were exercised with clearly labeled mocked API responses: success, loading, empty, access-denied with cached data, historical results and comparison details. Native Tab/Enter activated comparison details. At a 390 CSS-pixel viewport, document width was 384 pixels (no horizontal overflow). These browser fixtures are not live authenticated backend/GitHub verification.

## C. Test commands and results

### Full backend command

The following is the exact final test invocation from the backend directory. The small pytest plugin only shortens oversized display IDs on Windows; it does not change test inputs or assertions.

```powershell
$env:SAMANVAYA_DOCKER_BENCHMARK_TESTS='1'
$env:SAMANVAYA_MONGO_TESTS='1'
M:/Samanvaya/backend/.venv/Scripts/python.exe -c "import hashlib,pytest,sys; plugin=type('ShortParameterIds',(),{'pytest_itemcollected':lambda self,item:setattr(item,'_nodeid',item._nodeid if len(item._nodeid)<=220 else item._nodeid[:180]+'-short-'+hashlib.sha256(item._nodeid.encode()).hexdigest()[:12])})(); sys.exit(pytest.main(['-q','--tb=short'],plugins=[plugin]))"
```

| Verification | Actual result |
|---|---|
| Full backend baseline, same command without opt-in environment flags | 2,389 passed; 0 failed; 109 skipped; 40 warnings. |
| First Docker/Mongo-enabled attempt while Docker Desktop was stopped | 2,413 passed; 109 failed; 0 skipped. The 109 failures were Docker-dependent checks with the missing Linux engine pipe. They were not counted as passes. |
| Restored environment, full backend after runtime fixes | 2,522 passed; 0 failed; 0 skipped; 40 warnings. |
| Full backend after adding CI regressions | 2,524 passed; 0 failed; 0 skipped; 40 warnings. |
| Final full backend on final source tree | **2,547 passed; 0 failed; 0 skipped; 40 warnings; 195.23 seconds.** This includes 111 Docker-dependent checks and the real MongoDB concurrency case. Counts across invocations overlap and must not be summed. |
| Real container timeout/cancellation focused check | `SAMANVAYA_DOCKER_BENCHMARK_TESTS=1 … -m pytest tests/test_pr_algorithm_docker.py -q --tb=short -k real_pr_worker_stop`: 2 passed; 0 failed; 7 deselected. |
| Final frontend suite | `npm run test -- --run --maxWorkers=2`: 157 passed; 0 failed; 0 skipped, across 20 files. |
| Frontend lint | `npm run lint`: exit 0; 16 existing warning lines; 0 error lines. |
| Frontend production build | `npm run build`: exit 0; 2,042 modules transformed. |
| Focused editor diagnostics | No errors reported in the changed recommendation routes/repository, algorithm routes and PR result component; earlier core-service checks also reported no errors. This is not a claim about every editor warning in the repository. |
| Retained CI runner syntax | `& 'C:/Program Files/Git/bin/bash.exe' -n ci/run_tests.sh`: exit 0. |
| CI configuration regression | Included in the stabilization tests; YAML parsing, Python/Node setup, retained runner, parser bootstrap, PR upload guard and failure step pass. Before the fix, YAML parsing failed at the committed merge marker. |
| Whitespace/conflict check on changes | `git diff --check`: exit 0 (line-ending notices only). |
| Supplemental strict UI static audit | Exit 2; 88 diagnostics (24 unresolved ownership items; 64 static violations). See the raw [static audit](2026-11-11-ui-static-audit.json). None targeted the modified PR panel. These repository-wide design-contract/style diagnostics were not promoted to confirmed runtime bugs or used to justify an unrelated redesign. |

The initial Linux engine outage was resolved by starting the already-installed Docker Desktop (`docker desktop start`); `docker info --format '{{.OSType}}'` then returned `linux`. Existing pinned images were reused:

- Python: `sha256:4e518aaec4a220b4ea27f6c1a4898af7f576abea0f7b4459500f670f355f387c`.
- Node: `sha256:d658cc0e04da1ab1a79a5674a79cb45f414cd5bea00a2a201a354996ac553436`.

Host verification used the configured Python 3.12.10 environment. Real MongoDB deduplication used the existing opt-in test and its owned temporary collections; those collections were removed by its cleanup. No application project, contract or benchmark record was used as test data.

One final build invocation did not start because automatic permission approval timed out. An attempt in the normal workspace sandbox reproduced Vite's `spawn EPERM`; the ordinary subprocess-enabled retry of the same existing build script succeeded. No build configuration or security rule was changed to work around the environment restriction.

The supplemental static command was:

```powershell
M:/Samanvaya/backend/.venv/Scripts/python.exe 'C:/Users/Mounesh/.codex/plugins/cache/openai-curated-remote/frontend-design-premium/1.4.0/skills/frontend-design-premium/scripts/audit_project.py' M:/Samanvaya/frontend --mode strict --output M:/Samanvaya/frontend/.audit-static.json
```

Its output was retained with this report, rather than altering existing shared controls/theme contracts outside the stabilization scope. Browser fixtures used a temporary local Vite server and a separate headless Edge profile plus the integrated browser. The fixture HTML, screenshots and server were removed/stopped after verification; user authentication state was not modified.

## D. Remaining issues and verification limits

### Confirmed unresolved in-scope defects

None of the defects reproduced in this audit remains unresolved. This is not a guarantee that every possible defect has been discovered.

### Existing warnings and unverified risks

- The full backend run emits existing Pydantic deprecation, naive-datetime and test-collection warnings (40 total). The frontend linter reports 16 existing warnings. These did not fail their test/lint commands and were not rewritten as unrelated cleanup.
- The optional UI design/static audit is not clean: its 88 diagnostics concern existing ownership declarations, controls/forms and scrollbar rules elsewhere. They were not validated as 88 application bugs. Full premium/accessibility compliance is not claimed.
- Existing worker evidence is not tamper-proof against deliberately malicious submissions. The audit preserved that limitation and existing trust boundaries; it did not introduce a new trusted oracle or claim mathematical equivalence.
- For older reports that never recorded the original manual dataset scope, that intent cannot be reconstructed safely. Historical explicit required IDs are conservatively retained. Newly prepared/revised reports record the manual scope so subsequent supersession can retire imported coverage without dropping manual checks.
- Local/unattested historical function snapshots remain readable but cannot establish an excluding authoritative revision scope. Missing trustworthy scope now remains unresolved rather than bypassing a constraint.

### Environment/deployment verification not performed

- A real GitHub webhook delivered to a deployed, signed endpoint was not exercised. Webhook dispatch/HMAC boundaries were verified through the existing route/service tests; external delivery is unverified.
- No separate production/isolated deployment host was certified. Docker tests ran on the existing local Windows/Linux Docker backend.
- A hosted GitHub Actions run was not triggered. The workflow syntax and retained runner/bootstrap guards were verified locally.
- The actual long-running application backend was not restarted or deployed. Browser checks used mocked fixture responses and do not certify live authenticated production navigation.

## E. Files changed and why

| File | Why necessary |
|---|---|
| [.github/workflows/samanvaya-qa.yml](../../.github/workflows/samanvaya-qa.yml) | Repair confirmed invalid merge artifacts and missing existing parser bootstrap while retaining the QA runner/guards. |
| [api/routes/algorithms.py](../../backend/api/routes/algorithms.py) | Share correct expiration; label superseded history; derive current finding/revision from the authorized benchmark. |
| [api/routes/github.py](../../backend/api/routes/github.py) | Describe the stale-sync outcome accurately through the existing response. |
| [api/routes/recommendations.py](../../backend/api/routes/recommendations.py) | Apply the existing algorithm project/org guard consistently to legacy recommendation read/action paths and preserve actual authorization errors. Ordinary recommendation role rules are unchanged. |
| [benchmark_worker/function_discovery.cjs](../../backend/benchmark_worker/function_discovery.cjs) | Emit the compiler's actual end-column metadata; no candidate execution change. |
| [algorithm_benchmark_service.py](../../backend/domain/services/algorithm_benchmark_service.py) | Use the preceding decision's requirement provenance when preparing a new policy revision. |
| [behavioral_compatibility_service.py](../../backend/domain/services/behavioral_compatibility_service.py) | Reject nested/class identity substitution for the worker's module entrypoint. |
| [function_contract_service.py](../../backend/domain/services/function_contract_service.py) | Validate current project-organization applicability. |
| [github_sync_service.py](../../backend/domain/services/github_sync_service.py) | Stop stale fetched analysis from being attached to current metadata. |
| [pr_algorithm_intelligence_service.py](../../backend/domain/services/pr_algorithm_intelligence_service.py) | Correct source slices, expiration/cache lifecycle, supersession invalidation, partial/failure status and recommendation decision references. |
| [requirement_discovery_service.py](../../backend/domain/services/requirement_discovery_service.py) | Preserve supersession history, current organization, attested complete candidate scope and original manual workload scope. |
| [webhook_event_processor.py](../../backend/domain/services/webhook_event_processor.py) | Stop recommendation/notification side effects for a superseded sync. |
| [discovery/python_extractor.py](../../backend/intelligence/algorithms/discovery/python_extractor.py) | Record exact end columns and decorator declaration start. |
| [discovery/service.py](../../backend/intelligence/algorithms/discovery/service.py) | Carry optional position metadata into existing discovery evidence. |
| [algorithms/requirements.py](../../backend/intelligence/algorithms/requirements.py) | Replace imported policy IDs by provenance rather than deleting a client ID prefix; recognize valid supersession history. |
| [evidence/function_purpose.py](../../backend/intelligence/evidence/function_purpose.py) | Add optional, backward-compatible positions required by the demonstrated range defect. |
| [recommendation_repository.py](../../backend/repositories/recommendation_repository.py) | Invalidate stale manifest/decision findings and project-safe evidence references; exclude Mongo-only fields from response data. |
| [test_algorithm_stabilization.py](../../backend/tests/test_algorithm_stabilization.py) | New red/green regressions for the confirmed defects plus positive scope/Unicode cases. |
| [test_pr_algorithm_docker.py](../../backend/tests/test_pr_algorithm_docker.py) | Actual optional-memory fault, timeout and cancellation verification in isolated containers. |
| [PRAlgorithmIntelligencePanel.jsx](../../frontend/src/pages/code-quality/PRAlgorithmIntelligencePanel.jsx) | Honor comparison methodology/errors/current revision; repair existing evidence links and partial wording. Layout/visual tokens are preserved. |
| [prAlgorithmIntelligence.test.jsx](../../frontend/src/tests/prAlgorithmIntelligence.test.jsx) | Five new UI regression cases; realistic methodology/status data in existing comparison tests. |
| [Audit execution plan](../superpowers/plans/2026-11-11-algorithm-stabilization.md) | Track the requested reproduction-first audit and verification scope. |
| [Supplemental static audit](2026-11-11-ui-static-audit.json) | Retain the raw, non-passing supplemental check transparently rather than hiding or treating heuristic diagnostics as proven defects. |
| This report | Requested findings, evidence, exact commands, limits and file rationale. |

Only optional range fields and requirement/manual-scope provenance were added to existing evidence to repair demonstrated compatibility defects. No collection/index migration, new API, new recognition system, new benchmarking framework, RAG or model training was added. Existing access roles, independent approval requirements, worker sandbox configuration and manual benchmark modes were preserved.
