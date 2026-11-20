# Reproducing the local prototype verification

Use the existing demo accounts through the normal login screen. Credentials remain in the private local credentials directory; do not paste them into terminals, reports or screenshots. The Lead can inspect manual PR analysis and benchmarks; the QA account can start Code Quality runs.

## Existing running environments

| Purpose | Frontend | Backend | Database |
|---|---|---|---|
| Original TaskFlow data and historical reports | http://127.0.0.1:5173 | http://127.0.0.1:8000 | samanvaya_test |
| Verified disposable live execution | http://127.0.0.1:5174 | http://127.0.0.1:8001 | samanvaya_demo_verified_20261120 |
| Preserved first failed attempt | Not running | Not running | samanvaya_demo_validation_20261120 |

The disposable databases contain minimal copies of authorized demo accounts and the exact project/repository mapping. They do not create a second mapping in the original database. The final verified and first failed jobs share a deterministic ID across separate databases; do not confuse their results.

## Restart the isolated app when needed

Do not run a second server on an occupied port. Stop only the instance you intend to restart. In a PowerShell terminal:

```powershell
Set-Location M:\Samanvaya\backend
$env:DB_NAME='samanvaya_demo_verified_20261120'
$env:GITHUB_POLL_INTERVAL_SECONDS='0'
$env:PR_MULTI_AGENT_INTERNAL_ENABLED='true'
$env:PR_MULTI_AGENT_MANUAL_ENABLED='true'
$env:PATH="M:\Samanvaya\backend\.venv\Scripts;$env:PATH"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

In another PowerShell terminal:

```powershell
Set-Location M:\Samanvaya\frontend
$env:VITE_PROXY_TARGET='http://127.0.0.1:8001'
$env:VITE_PR_MULTI_AGENT_MANUAL_ENABLED='true'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort
```

Use the existing Docker Desktop Linux engine and installed Ollama model `qwen2.5-coder:3b`. If Ollama is not running, start the installed Ollama application. Do not reinstall dependencies or download a different model to reproduce this result. Do not use Uvicorn reload or multiple workers on Windows for these subprocess-based analyzers.

## 1. GitHub Actions and original PR visibility

1. Open port 5173 and sign in as the existing Developer account.
2. Open Pull Requests. TaskFlow should show four PRs, one open and three merged, with an explanation that the GitHub account is not linked.
3. PR #4 should show `Actions: success` and `Other check providers unavailable`, open status and pending review. Do not click Sync PR or Configure QA Automatically.
4. Verify exact head `8ad02ac50587c6bb668dc480ae68efdc9f411b68` against [CI evidence](./ci-evidence-comparison.json). Runs 44521347474 and 44521183772 each contain successful Backend Tests and Frontend Tests jobs, attempt 1. Checks returns 403; it is not a global CI pass.
5. Open Algorithm findings for PR #4. Expect 18 candidates, zero validated comparisons and Unsupported because no previous implementation or approved applicable contract exists.

## 2. Measured Code Quality findings

1. On port 5174 sign in as Lead and open `/code-quality/runs/RUN-A5FC26DF5598`.
2. Expect one analyzed Python file and two Ruff findings: unused `os` at line 1 (F401), undefined `missing_symbol` at line 4 (F821).
3. Expect Ruff and Mypy in executed tools, and explicit skipped tools/coverage. The unchanged deterministic policy reports 98/A and LOW(22), but the report is partial and contains a genuine defect; the score is not a correctness guarantee.
4. For a fresh API run, sign in as QA and POST `/api/code-quality/analyze` with the trusted fixture path recorded in [local-quality-fixture.json](./local-quality-fixture.json), `repository_id: PRJ-A7E48B66`, `changed_files: ["sample.py"]`, `analysis_level: deep`, `use_ai: false`, and `pr_context.repo_path` set to that exact existing path. Poll the returned run ID. No fixture code or tests are executed.
5. If the temporary fixture was removed, recreate only this trusted file in a new temporary directory, then use that directory:

```python
import os

def total(values):
    return missing_symbol + sum(values)
```

Before the runtime PATH correction, the same API used only AST fallbacks and produced zero findings with a partial score. After prepending the venv Scripts path, Ruff detects both issues. Do not use the earlier AST-only run as the genuine lint demonstration.

## 3. Real CI/CD AI diagnosis

1. Sign in as Lead and open `/cicd-logs`.
2. Replace the example with this clearly synthetic log:

```text
SYNTHETIC DEMO
error TS2304: Cannot find name missingValue.
Build exited with code 1.
```

3. Select Build Log and click Diagnose Log with AI.
4. The verified live request returned `ai_status: completed`, a diagnosis and three suggestions. Existing successful run: `dddd2038-3fee-4cde-8018-6cade60d73d6` in the original demo database. Each new request is nondeterministic; inspect its actual status rather than expecting identical wording.
5. Before repair, Ollama returned capitalized `Medium`, which violated the lowercase urgency enum. The screen also hid invalid/unavailable AI status behind its deterministic LOW(10) result. The prompt now explicitly requests lowercase urgency; the UI now shows errors and labels success advisory. The parser was not relaxed.
6. To inspect the recorded failure, use [raw provider response](./cicd-raw-provider-response.txt) and [before-response JSON](./cicd-ui-response.json). An unavailable provider must show an alert, not a fabricated diagnosis. A completed provider response must show an advisory label. Do not stop Ollama during another person's work merely to demonstrate failure.

## 4. Durable manual PR workflow

1. Sign in as Lead on port 5174, then open `/github/sync`.
2. Expand Open a previous analysis; enter:

```text
90487b7d2b0de7be03c7fb2f5010ea4b21e20e3ddb2a488ea4b04892d11ba415
```

3. Click Open analysis. Expect Advisory report ready, `PARTIAL_SINGLE_SPECIALIST_ADVISORY`, Code succeeded, QA skipped (`NO_QA_EVIDENCE`) and three unsupported claims.
4. The report is real Ollama output, durable v2, for the exact PR revision and snapshot. Its sequence is resolve_evidence → code_analysis → qa_analysis → reconcile → finalize. It is not a completed two-specialist assessment. Missing evidence references remain unsupported even when statements resemble the source.
5. Selecting TaskFlow and PR 4, then Start advisory analysis, returns the existing FINALIZED job. This demonstrates idempotency and does not rerun inference. Repeated report reads were byte-identical.
6. The first attempt remains FAILED in `samanvaya_demo_validation_20261120`; it is not overwritten by the corrected result. Reproducing a fresh model run requires a separate disposable database/project identity, not deleting or editing the immutable report. Do not submit against populated TaskFlow to force a fresh result.
7. Before the final fix, the actual model returned an observation object or a list of claim strings instead of the required reply wrapper. The correction adds explicit input/output boundaries and a provider-compatible generation shape. The original strict parser, evidence references, unsupported-claim reconciliation and score prohibition remain in force.
8. Developer and HR normal accounts are denied access to manual interpretation. Current permissions and ownership are checked on reads; do not share another account's bearer token.

## 5. Python, JavaScript and TypeScript Docker benchmarks

1. On isolated port 5174 open Code Quality → Advanced tools.
2. Enter Benchmark project ID `PRJ-A7E48B66` and click Load project history.
3. Open Python `ALG-F7391488D3424011`, JavaScript `ALG-84AEE79D65254F02`, or TypeScript `ALG-88B4A36EC13C46A1`.
4. Each contains two trusted synthetic sorting functions, 16 cases per candidate, sizes 0/1/16/64, random/sorted/reversed/duplicates distributions, one repetition and seed 42. All 96 candidate/case checks across three languages passed.
5. The saved API requests and measurements are in [Python](./python-benchmark.json), [JavaScript](./javascript-benchmark.json), and [TypeScript](./typescript-benchmark.json). To rerun, use exactly the recorded request or fill its candidate source and entrypoint fields in the UI, then submit the sorting preset. No new contract approval is needed for the existing numeric-sort preset; do not execute TaskFlow functions or approve a generic contract.
6. Explain the result honestly: the decision is conditional and the aggregate recommendation is insufficient_evidence. One timing sample does not establish superiority. Python reports Memray tracked allocations; Node heap delta is not peak memory.
7. Request explanation is optional. The verified endpoint returned a citation to the saved decision. Ollama selected allowed deterministic fact IDs; final text came from those facts rather than unrestricted generated performance claims. See [explanation response](./benchmark-explanation.json).

## Validation and rollback

- Final focused backend: 356 passed, 1 opt-in skip. Separate real-Mongo: 4 passed, including the skipped API case. The final supported-host run supersedes an explicitly recorded restricted-sandbox permission failure; no tests were weakened.
- Frontend: 20 focused tests passed; production build and scoped lint passed. Scoped Ruff and Mypy passed; Mypy notes untyped-body limits.
- Original TaskFlow collection fingerprints all matched [the baseline](./original-data-baseline.json): [final comparison](./original-data-after.json).
- Restore the three local manual flags to false and restart the local services to disable the panel/worker. Stop the isolated 8001/5174 processes when finished. The temporary databases are preserved as evidence; do not drop either without a separate deliberate decision.
- Verification performed no merge, deployment, employee assessment, production scoring activation, GitHub write, QA evidence fabrication or TaskFlow code execution. The user subsequently authorized a separate Git checkpoint and push of the reviewed fixes, tests and reports; local environment files and credentials remain excluded.
