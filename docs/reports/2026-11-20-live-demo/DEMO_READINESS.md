# SAMANVAYA local prototype demonstration readiness

Verified on 20 November 2026 against local `testing`, HEAD `5835ede65cabec52610deb349aaf89d4f6c36020`, with the uncommitted demo repairs listed below. This is an academic prototype verification, not production certification. Authenticated UI/API verification now includes a durable real-Ollama partial PR advisory report, genuine Ruff quality findings and trusted Python/JavaScript/TypeScript Docker benchmarks. Two-specialist collaboration remains unavailable because no registered exact-revision QA submission exists.

## Runtime and access

- Backend: Python 3.12.10 virtual environment, one Uvicorn worker on `127.0.0.1:8000`, without reload. Frontend: Vite on `127.0.0.1:5173`. Both were restarted as hidden local processes; no public exposure.
- MongoDB: existing `samanvaya_test`. GitHub credentials remain server-side. Docker Linux engine and both pinned worker images were reachable during the live verification; authenticated benchmark availability changed from false under reload to true after the supported single-worker restart. No TaskFlow code was executed.
- Ollama: existing `qwen2.5-coder:3b`; the installed service was restarted after it became unavailable. Actual successful responses are retained in the evidence files. Availability alone is not proof of response-contract compatibility.
- Local flags before: backend internal false, backend manual false, frontend manual false. All three are now true only in ignored local environment files. Tracked defaults remain false. The development backend's process-only `GITHUB_POLL_INTERVAL_SECONDS=0` prevents background PR synchronization.
- Isolated demo: frontend `127.0.0.1:5174`, backend `127.0.0.1:8001`, database `samanvaya_demo_verified_20261120`. Only necessary exact demo account/project/repository records were copied; normal credentials and permissions are unchanged. The first failed attempt remains in separate database `samanvaya_demo_validation_20261120`. Repository provenance requires a unique project mapping per database, so a second mapping was deliberately not created in populated `samanvaya_test`.
- Normal Developer and Lead UI logins succeeded. The Developer sees TaskFlow through the clearly labeled authorized-project fallback because no GitHub identity mapping exists. Lead dashboard shows five team members and one open review item. Normal activated API logins: Lead 200 for manual project choices; Developer and HR 403. No foreign-organization account was created or impersonated; cross-organization isolation is covered by focused existing tests, not newly claimed as a live foreign-account test.

## Feature results

| Component | Actual execution and evidence | Status |
|---|---|---|
| GitHub Actions CI | Authenticated Pull Requests screen shows `Actions: success` and `Other check providers unavailable`. Current GitHub read APIs match stored exact-head run/job identities and outcomes. | LIVE VERIFIED |
| PR analysis and visibility | Developer project view displays four PRs, one open and three merged; Lead review queue returns PR #4. Correct author, repository and pinned revisions are displayed. | LIVE VERIFIED |
| Algorithm report retrieval and manual sorting | Historical PR #4 panel retains 18 changed candidates and zero automatic comparisons. Separate trusted sorting presets completed for Python, JavaScript and TypeScript in Docker; 96 candidate/case correctness checks passed, with no superiority recommendation. | LIVE VERIFIED |
| Current algorithm extraction | Read-only exact-SHA parse identifies heap operations, sorting, FIFO graph traversal, LIFO graph exploration and conservative cycle-search structure. No source execution. | TEST/CLI VERIFIED |
| Code Quality historical UI | `RUN-87391CFA0F85` explicitly says discovery finished, quality not run; quality/risk/coverage are unavailable. No fabricated 100/A. | LIVE VERIFIED |
| New measured source findings | Authorized QA API run `RUN-A5FC26DF5598` in the isolated database produced Ruff F401 line 1 and F821 line 4, visible through the real details UI. Nested TypeScript TS2322 was independently CLI verified. | LIVE VERIFIED |
| Manual multi-agent execution | Actual isolated manual UI run finalized a durable `PARTIAL_SINGLE_SPECIALIST_ADVISORY` report: Code succeeded using Ollama, QA skipped, all three uncited claims unsupported. Duplicate submission returned the existing job. This is not two-specialist collaboration. | LIVE VERIFIED |
| Employee AI evaluation | Lead form and provider health were inspected; no official employee assessment was generated. | BLOCKED |
| Synthetic AI suggestions | Unsaved QA request ran through the normal authorized API and LangGraph with history `[qa_agent]`; later CI log UI ran the real CI specialist and persisted a private advisory result. | LIVE VERIFIED |

## CI evidence and PR identity

TaskFlow PR #4: author `Mounesh05`, base `f9e996fecf517a9985fbfd920112a1173b369b59`, head `8ad02ac50587c6bb668dc480ae68efdc9f411b68`, open, review pending. Mergeability is not approval. Historical stored CI retrieval timestamp: `2026-11-19T13:10:18.794000+00:00`; fresh comparison timestamp: `2026-11-20T11:29:12.930364+00:00`.

| TaskFlow CI run | Attempt / event | Backend job | Frontend job | Reported outcome |
|---|---|---|---|---|
| 44521347474 | 1 / pull_request | 135550472089 | 135550472483 | Both jobs and workflow completed/success |
| 44521183772 | 1 / push | 135549897403 | 135549896560 | Both jobs and workflow completed/success |

Both runs match the exact head SHA. Fresh Checks request still returns 403. The application keeps global `ci_status` null, scope `github_actions_only`, evidence partial, and non-Actions providers unavailable. The UI presents only the summary; attempts, job IDs and timestamps require the API/evidence JSON. No failing, pending or cancelled live run was manufactured for this demonstration.

See [current GitHub/source evidence](./github-and-current-discovery.json) and [stored/live comparison](./ci-evidence-comparison.json).

## Algorithm and quality limits

The historical UI still shows BFS/DFS as generic collection search. The current extractor, run separately at the same SHA, identifies `fifo_graph_traversal` and `lifo_graph_exploration`. Heap purpose remains unknown; sorting is inferred collection ordering; traversal is inferred graph traversal; cycle detection remains conservative collection search. These are structural inferences, not shortest-path proof or behavioral equivalence. No approved contract or previous lexical implementation exists for the 18 new candidates, so Unsupported is expected. The bounded two-file current parse did not establish callers or approved assertion authority; absent links remain unknown.

Trusted Python fixture: `import os` at line 1 and `return missing_symbol + sum(values)` at line 4. Ruff found both issues; one file was analyzed. Mypy and static complexity/test-discovery paths ran. Bandit, dependency manifest, Lizard and coverage were unavailable; coverage remained null with `missing-data`. No tests were executed to generate coverage. The trusted TypeScript fixture used a nested configuration and `const value: number = "wrong";`, producing TS2322. A complete ESLint/security/dependency audit was not established. See [Python evidence](./trusted-quality-evidence.json) and [TypeScript evidence](./trusted-typescript-evidence.json).

## Real model outputs and repairs

The unsaved QA request supplied synthetic 62% coverage, an 8-point decrease, two added tests and three untested files. Ollama recommended negative-input/boundary tests and reviewing untested files. This was caller-supplied unverified data, not measured TaskFlow coverage. The model's inference about overall reliability and its numerical confidence are advisory, not independent proof. See [QA response](./qa-advisory-response.json).

The CI demonstration initially failed strict validation. Captured raw output used `urgency: "Medium"`, outside the existing lowercase enum. The PR specialist echoed input state, a schema, or unstructured claims. The full bounded response schema caused an Ollama grammar error. Final fixes explicitly require lowercase CI urgency, delimit PR input/output, and derive a grammar-compatible generation shape from the existing reply schema. Only unsupported generation bounds/annotations are omitted; enums and object shape remain, and the original bounded Pydantic parser still rejects malformed, oversized or forged-authority replies. No output is substituted, normalized or promoted to evidence. The first failed durable report remains immutable.

The CI screen also concealed failed AI status behind its deterministic result. It now displays failed/unavailable status and request errors, clears stale results when submitting, and labels successful model interpretations advisory. No deterministic formulas or thresholds changed.

The repaired live CI UI returned HTTP 200, `ai_status: completed`, no AI errors, in approximately 8.1 seconds. Private run `dddd2038-3fee-4cde-8018-6cade60d73d6` is owned by `DEMO_LEAD`, unscoped to a project, tagged `ai-run-access-v1`, caller evidence UNVERIFIED, interpretation ADVISORY. The model suggested checking spelling, declaring `missingValue`, and reviewing imports. Its typo explanation is a hypothesis; the log establishes only unresolved-name compilation failure. The deterministic LOW(10) log risk is not a statement that this build passed. See [actual repaired response](./cicd-ui-response-after.json).

Changed production files: [CI specialist](../../../backend/agents/cicd_agent.py), [PR specialist prompt and generation compatibility](../../../backend/agents/pr_multi_agent.py), [CI UI](../../../frontend/src/pages/cicd-logs/CicdLogsPage.jsx). Added focused [provider tests](../../../backend/tests/test_demo_provider_contracts.py) and [UI tests](../../../frontend/src/pages/cicd-logs/CicdLogsPage.test.jsx); updated the existing [PR model transport tests](../../../backend/tests/test_pr_multi_agent.py) to consume delimited input and assert unchanged authority boundaries. No automatic commit, merge or push.

Verification: three UI regressions failed before repair and passed afterward; provider regressions reproduced the missing output-contract instructions before correction. Final combined focused backend suite: **356 passed, 1 opt-in test skipped**, exit 0. Separate opt-in real-Mongo execution: **4 passed**, including the previously skipped API case, atomic claims, lease expiry, process restart, fencing and immutable publication. Focused CI/Actions/manual-panel frontend: **20 passed**. Scoped Ruff, Mypy, frontend lint, whitespace checks and production build passed. Mypy notes that untyped bodies are not fully checked. An earlier restricted sandbox attempt produced two JS/TS failures and one temporary-directory permission error; the approved host rerun passed, without assertions weakened or tests skipped to conceal failures. No full suite was repeated.

## Manual activation and rollback

Flags are read at backend startup and by Vite. The actual GitHub screen exposes Manual PR analysis. The workflow uses the separate sequential Code then QA LangGraph, current-account authorization, exact revision/evidence resolution and MongoDB leases/fencing. It cannot convert agent agreement into proof. No automatic webhook caller was found. Polling remains disabled on both development backends.

After the user's authorization, one manual run was submitted in each isolated database. The first finalized an honest failure (`INVALID_MODEL_OUTPUT`) and is preserved in [first failed job](./first-durable-job-failed.json). The corrected run finalized with Code SUCCEEDED and QA SKIPPED (`NO_QA_EVIDENCE`). Job identity is `90487b7d2b0de7be03c7fb2f5010ea4b21e20e3ddb2a488ea4b04892d11ba415`; it is deterministic and therefore identical across the two independent databases. Always specify the database/port with the ID. Snapshot: `db9c334d8cd8d9a20706bc0d6747125211972377ec7b3c9d5d8c6185bb6d1f1c`. Transitions: resolve_evidence → code_analysis → qa_analysis → reconcile → finalize. Final report: durable v2, `PARTIAL_SINGLE_SPECIALIST_ADVISORY`, `SINGLE_SPECIALIST`, model `qwen2.5-coder:3b`. All three claims lacked references and were reconciled UNSUPPORTED. The server snapshot separately retains two exact-source references and structural observations. See [actual durable report](./verified-durable-report.json).

Duplicate submission returned the same FINALIZED job and snapshot rather than rerunning inference; repeated report reads were byte-identical. No QA counts were copied, fabricated or derived from test-function names. There is no registered QA configuration or exact-head submission, so a genuine two-specialist live assessment cannot currently be claimed. Permission tests deny Developer/HR; original TaskFlow collections are unchanged by final count/document-hash comparison in [final fingerprints](./original-data-after.json).

Final live authorization checks used normal Developer and HR logins: manual project selection returned 403 and access to the Lead-owned report returned 404 for both. Both backend health endpoints returned healthy with database and Ollama connected. See [access and health evidence](./final-access-health.json). The report UI explicitly shows the single-specialist partial outcome and all three unsupported claims in [durable report screenshot](./12-durable-partial-report.png).

The first isolated quality API attempt lacked the venv tool PATH and retained an AST-only partial result. The corrected launch prepends the existing backend venv Scripts directory; `RUN-A5FC26DF5598` then executed Ruff and Mypy and displayed two real findings, one analyzed file, quality 98/A and risk 22 under the unchanged deterministic policy. These scores are partial metrics, not correctness guarantees; the fixture contains a real undefined name. Coverage remains unmeasured. No historical run was rewritten. See [live quality screenshot](./11-live-quality-findings.png).

Trusted sorting runs: Python `ALG-F7391488D3424011`, JavaScript `ALG-84AEE79D65254F02`, TypeScript `ALG-88B4A36EC13C46A1`. Each used two self-contained synthetic numeric sort functions, sizes 0/1/16/64, four distributions, one repetition and seed 42. All 32 candidate/case checks per language passed. Python reports Memray tracked allocations; Node heap deltas are not peak memory. Each recommendation remains insufficient_evidence because mandatory requirement compliance was not established. Single-sample timings are not a robust performance ranking. These are manual preset runs, not automatic TaskFlow replacement comparisons. Full API records: [Python](./python-benchmark.json), [JavaScript](./javascript-benchmark.json), [TypeScript](./typescript-benchmark.json).

The actual Code Quality → Advanced tools → Load project history UI retrieved the Python run and displayed its conditional decision and measurement tables. See [benchmark screenshot](./13-live-benchmark-history.png). The optional explanation endpoint returned generated status and a saved-decision citation. Its model selects permitted fact IDs; returned explanation wording is assembled from deterministic facts, not unrestricted model claims. See [explanation evidence](./benchmark-explanation.json).

Rollback: restore `PR_MULTI_AGENT_INTERNAL_ENABLED=false` and `PR_MULTI_AGENT_MANUAL_ENABLED=false` in the existing ignored backend environment file, and `VITE_PR_MULTI_AGENT_MANUAL_ENABLED=false` in the existing ignored frontend local environment file. Restart only the local backend and frontend without reload. Keep polling at zero during read-only verification; ordinary startup without the process override restores the configured interval of 180 seconds. No production scoring policy was activated.

## Seven-minute demonstration

1. **0:00–0:45 — Developer dashboard:** normal login; show assigned TaskFlow work and honest missing evaluation. Personal PRs are empty without an explicit GitHub link.
2. **0:45–2:00 — `/pull-requests`:** show authorized-project fallback, four PRs, PR #4 Actions success and unavailable third-party checks. Use evidence JSON for exact head/run/job IDs. Do not click Sync PR.
3. **2:00–3:00 — PR #4 Algorithm findings:** show 18 candidates, zero comparisons, observed patterns, missing previous implementation and contract. Explain the separately captured current BFS/DFS extraction without rewriting the historical run.
4. **3:00–4:00 — Code Quality:** on the main demo, show historical discovery-only `RUN-87391CFA0F85`; on isolated port 5174 open `/code-quality/runs/RUN-A5FC26DF5598` to show genuine Ruff findings and partial tool availability.
5. **4:00–5:30 — Lead `/cicd-logs`:** paste the clearly synthetic unresolved-name log and run Diagnose Log with AI. Explain deterministic risk versus model advice. If the provider fails, the screen must show the failure; use the recorded authentic response rather than claim a new success.
6. **5:30–6:30 — Isolated Lead `/github/sync`:** expand Open a previous analysis, enter the durable job ID above, then Open analysis. Show Code succeeded, QA skipped, partial advisory and unsupported claims. Submitting the same request returns the existing immutable report; it does not rerun the model.
7. **6:30–7:00 — `/evaluation`:** show the existing form only; do not create an employee assessment. Explain that demonstrated AI advice is not an approved performance score.

Screenshots: [PR and Actions](./01-pr-visibility-actions.png), [historical algorithms](./02-historical-algorithm-report.png), [honest quality scope](./03-discovery-only-quality.png), [repaired error visibility](./07-cicd-error-visible-after-fix.png), [manual panel enabled](./08-manual-panel-enabled.png), [real CI AI success](./09-cicd-live-success-after-fix.png), [Lead dashboard](./10-lead-dashboard.png).

## Remaining demonstration gates

Two-specialist collaboration lacks registered exact-revision QA evidence. Employee assessment is intentionally not run. Automatic TaskFlow replacement comparison remains unavailable without a previous implementation and approved applicable contract. Optional quality tools/coverage and third-party Checks evidence remain unavailable. Model output remains variable, and uncited claims remain unsupported. TaskFlow Phase 2 is incomplete; no original TaskFlow code, PR, workflow or historical analysis record was modified. Exact reproduction and startup commands are in [REPRODUCING_STEPS.md](./REPRODUCING_STEPS.md).
