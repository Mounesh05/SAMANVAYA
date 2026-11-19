# Analyzer stabilization and Code Quality verification — 2026-11-19

## Scope and Git state

Initial branch: `fix/github-actions-ci-evidence`. Initial and final HEAD:
`143d0ba689afec5cefa3729f707fdc3c09b6f7bd`.
Implementation branch: `fix/analyzer-stabilization`, created at that HEAD.
No commit, staging, push, merge, deployment or feature activation was performed.
No `AGENTS.md` was found. The initial index was empty; it remains empty.

The initial tracked diff was six files, 63 insertions / 42 deletions: the existing
PR-visibility work in developer/lead routes, GitHub normalizer, PR repository,
PullRequestsPage and developerPages tests. These changes were preserved, along
with their untracked tests/report. Existing untracked `.vscode/`, audit/context
documents, `docs/audits/`, `docs/multi_agent_baseline.md` and
`empirical_harness.py` were preserved. The final working tree is deliberately
dirty: these earlier changes plus the 15 files listed below. No secrets or local
demo data are included in this implementation.

The populated `samanvaya_test` database was read only. No broad backend suite,
database cleanup, contract approval, comparison job or TaskFlow execution ran.
TaskFlow Phase 2 remains incomplete; no work belonging to the pending TS/QA
contributors was implemented.

## Confirmed defects and repairs

### Python adjacency and lexical connections

[Python extraction](../../backend/intelligence/algorithms/discovery/python_extractor.py)
previously recognized only subscript adjacency. It now observes `.get(node, [])`
and an unshadowed `reversed(...)` wrapper as well. Traversal inference additionally
requires a connected queue/stack, a preceding removal in the same while body,
the removed-node key, adjacency-loop neighbor, and append inside that loop.
Rebindings, unrelated receivers, unknown aliases, shadowed wrappers/constructors,
ambiguous stores and removal ordering remain uncertain. The
[pattern rule](../../backend/intelligence/algorithms/discovery/rules.py) consumes
that connection evidence. No algorithm-name/comment matching was added.

[Context linking](../../backend/intelligence/algorithms/discovery/service.py)
now derives possible import roots from actual package markers rather than
assuming repository-relative paths are import paths. This handles layouts such
as `backend/app` importing as `app`, without hardcoding `backend` or `src`.
Duplicate targets stay unresolved. Function-local import shadowing is excluded;
repository identity and language-family boundaries are retained. Namespace
packages without markers, dynamic import paths and runtime monkeypatching remain
unsupported. Links are lexical candidates; assertions are static observations,
not executed tests, approved requirements or correctness proof.

### Exact-revision static verification

Read-only Contents API retrieval at
`8ad02ac50587c6bb668dc480ae68efdc9f411b68` fetched the package marker, Python
implementation and tests. Only static parsing ran, with no persistence.

| Function | Previous stored patterns relevant here | New static result | Caller / assertion refs |
|---|---|---|---|
| `schedule_with_heap` | Priority queue operations | Preserved; purpose still unknown | 4 / 2 |
| `schedule_with_repeated_sort` | Sorting operations | Preserved; collection ordering | 1 / 1 |
| `bfs_dependencies` | Visited tracking, generic search | Adds FIFO graph traversal; inferred graph traversal | 2 / 2 |
| `dfs_dependencies` | Visited tracking, generic search | Adds LIFO graph exploration; inferred graph traversal | 2 / 2 |
| `has_dependency_cycle` | Generic collection search | Preserved; no new cycle rule invented | 4 / 4 |

Implementation SHA-256:
`e948c9feb3dce5b73550cd05c32d8833e67aace1dd6010eaef0aefc44f9d31f5`.
Test-source SHA-256:
`911d1a447a2c1f947e996d61b3e9bba5f764819f2a865f58f11fa17379b6d417`.
The package marker was empty. All verified-contract fields remained null.
Tests, lambdas and context functions remain in discovery snapshots.
No shortest-path, equivalence or benchmark claim follows from these results.

### Windows TypeScript extraction

An isolated trusted FastAPI probe ran using the configured Python 3.12.10
interpreter and Uvicorn with `--workers 1`, no reload and lifespan disabled. It
did not load the SAMANVAYA application or access its database. TS named functions,
arrow functions and TSX extraction succeeded: three functions, typed parameters,
a resolved lexical call, exact fixture revision and SHA-256 provenance; no
diagnostics. The probe was stopped afterward.

A separate disposable process using WindowsSelectorEventLoopPolicy reproduced
`NotImplementedError` and an unavailable discovery result. This explains the
earlier reload-loop failure; the supported single-worker setup works without an
extractor architecture change. The documented launch remains:
`backend/.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`
from an appropriately configured local environment, without reload/multiworker.
The [Docker runner](../../backend/intelligence/algorithms/runner.py) now reports
unsupported subprocess loops as unavailable instead of leaking that exception.

### Code Quality run and evidence boundaries

Stored run `RUN-87391CFA0F85` has `analysis_level=purpose_discovery`, status
completed, Python language and null quality/risk scores. It contains discovery
evidence, not quality-tool measurements. The missing scores were not lost during
API projection or rendering: they were never computed for this snapshot.
The historical partial discovery snapshot was not rewritten.

The UI's zero-findings/clean-code message was incorrect. The
[API](../../backend/api/routes/code_quality.py) now projects explicit discovery
scope for historical records without modifying them. New quality runs persist
tool availability, analysis quality, file count, exact revision and test metadata.
No-file evidence bypasses QualityEngine/RiskEngine and baseline updates; unknown
coverage is no longer written to the baseline as zero. Engine formulas, weights
and thresholds are unchanged.

[CodeQualityService](../../backend/domain/services/code_quality_service.py)
previously defaulted a missing worktree to `.` even when GitHub source strings
were supplied. It now refuses to analyze the server's unrelated working directory
and rejects unavailable/outside-root selected files. Connected source-only runs
remain explicitly discovery-only: there is no safe general remote checkout/tool
execution implementation added here. This is a remaining quality-coverage gap,
not evidence that the remote project is clean.

[Python tooling](../../backend/intelligence/analyzers/python/analyzer.py) now
labels AST test counting accurately, rejects malformed Bandit evidence, preserves
unknown coverage when totals are absent, and requires a dependency manifest.
Safety fallback is scoped to that manifest instead of the host environment.
Existing dependency-tool tests received real temporary manifests; their original
success/failure assertions were retained.

[TypeScript tooling](../../backend/intelligence/analyzers/javascript/analyzer.py)
now resolves the nearest tsconfig for changed files, including a nested frontend
project, runs in that project directory and restores repository-relative finding
paths. Global compiler/config errors become findings; unrecognized output and
missing config/manifests are explicit limitations. A trusted nested fixture run
with the installed pinned compiler returned exit 2 and the expected TS2322.
No project dependencies were installed and no TaskFlow package/config scripts ran.

The [detail page](../../frontend/src/pages/code-quality/RunDetailPage.jsx) and
[history page](../../frontend/src/pages/code-quality/CodeQualityPage.jsx) distinguish
discovery completion, partial quality analysis, unavailable scores and retrieval
failures. Empty findings no longer certify clean code. Detail findings use the
actual backend file/line/message fields with legacy fallbacks. Existing visual
components and tokens were retained.

## Actual tool availability and limitations

| Capability | Verified behavior / availability |
|---|---|
| Python Ruff / Flake8 | Ruff 0.6.9 installed in venv, absent from original PATH; trusted fixture with venv PATH produced F401. Flake8 not installed. |
| Python Mypy | 1.11.2 installed in venv; trusted fixture adapter executed it. Scoped source type check passed. |
| Python Bandit | Not installed; missing-tool evidence retained. Malformed-output failure covered by mock regression. |
| Python dependency audit | pip-audit 2.10.1 installed, Safety absent. No live dependency audit claimed; missing manifest skips explicitly. |
| Secrets / duplication / architecture | Existing static implementations inspected; no target-code execution. Covered by existing analyzer regressions; no complete TaskFlow quality assessment claimed. |
| Complexity | Lizard/Radon absent. Trusted Python fixture used AST fallback. JS/TS complexity remains unavailable without a supported tool. |
| Python tests / coverage | AST counting only, accurately labeled; trusted fixture counted one test. No test execution or coverage generated. PATH has a coverage command but this venv has no coverage distribution and the command produced no usable report. Coverage remains null. |
| JS/TS ESLint | Not available on original PATH; existing project-local resolution retained. No live ESLint assessment of TaskFlow claimed. |
| JS/TS compiler | Pinned parser/compiler is installed under benchmark_worker; static extraction and direct trusted-fixture type error verified. Adapter nested-root routing covered with controlled output. |
| npm audit | npm available; existing collector validates report shape. No live TaskFlow audit/installation ran; missing root manifest is explicit. Nested package-audit discovery remains limited. |
| JS/TS test framework / coverage | Existing config/package-script inspection is static; it neither runs tests nor collects coverage. Missing coverage remains unknown. |

The server environment must expose its chosen venv tools on PATH to use their
CLI adapters. Nothing was installed or changed in the development environment.

## Docker verification

`docker version`, `docker info --format '{{.OSType}}'`, `docker ps`, and inspection
of both approved image tags were attempted, including outside the restricted
filesystem/pipe sandbox. CLI 29.9.3 uses context `desktop-linux`, but every daemon
request fails: `//./pipe/dockerDesktopLinuxEngine` does not exist. A reachable
Linux server, image presence/IDs and live execution therefore remain unverified.
Images were not assumed missing, built or pulled while the daemon was unreachable.

Runner inspection confirms fixed image tags, `--pull=never`, network none,
read-only root, non-root UID/GID 65532, all capabilities dropped, no-new-privileges,
64 MB noexec/nosuid/nodev tmpfs, default 512 MB memory/swap, one CPU, 64 PIDs,
finite timeout/output bounds, schema validation and forced cleanup. This is source
verification only, not live isolation verification. No TaskFlow benchmark ran.

## Test results

Configured interpreter: `M:/Samanvaya/backend/.venv/Scripts/python.exe`, Python 3.12.10.

- Final focused backend: **456 passed, 19 skipped, 0 failed**, exit 0, 11.79 s.
  Modules: analyzer_stabilization, function_discovery, function_discovery_integration,
  code_intelligence_analyzers, quality_engine, risk_engine, algorithm_runner,
  algorithm_benchmark_service and internal_agent_adapters. All skipped cases are
  opt-in Docker runner fixtures: 3 sorting, 1 syntax, 12 unsupported contracts,
  3 stateful cases. No live database integration was enabled.
- Full frontend: **378 passed, 57 files passed**, exit 0, 80.07 s, using
  `npx vitest run --maxWorkers=2`. The first default run spawned 57 workers and
  ended at 358 passed / 20 failed (timeouts/loading states); rerunning with bounded
  concurrency passed without assertions, timeout settings or source fixes to
  those unrelated tests. Existing jsdom navigation warning remains.
- Focused frontend earlier: **84 passed**, including new scope-state tests.
- Production frontend build: passed. Scoped oxlint: passed.
- Scoped Mypy: **8 source files passed**, exit 0, with `--follow-imports=skip
  --ignore-missing-imports`; this is not a whole-project type-check claim.
- Scoped Ruff for implementation/new tests passes with existing E402 ignored.
  Unfiltered checks expose four existing service E402s and twelve existing
  findings in the old analyzer test module. `git show HEAD:...` independently
  reproduced these baseline findings; unrelated lint cleanup was not performed.
- Premium UI static audit: five pre-existing violations in FeedbackPage
  (two validation-owner and three textarea-resize rules); no touched-page finding.
  Browser screenshot/interactive visual QA was not performed. Component state
  tests and production build passed.
- `git diff --check`: passed. No full backend-suite pass is claimed.

## Changed files for this task

1. [Python extractor](../../backend/intelligence/algorithms/discovery/python_extractor.py)
2. [Pattern rules](../../backend/intelligence/algorithms/discovery/rules.py)
3. [Discovery linking](../../backend/intelligence/algorithms/discovery/service.py)
4. [Docker runner](../../backend/intelligence/algorithms/runner.py)
5. [Python quality adapter](../../backend/intelligence/analyzers/python/analyzer.py)
6. [JS/TS quality adapter](../../backend/intelligence/analyzers/javascript/analyzer.py)
7. [Code Quality service](../../backend/domain/services/code_quality_service.py)
8. [Code Quality API](../../backend/api/routes/code_quality.py)
9. [New stabilization tests](../../backend/tests/test_analyzer_stabilization.py)
10. [Discovery integration tests](../../backend/tests/test_function_discovery_integration.py)
11. [Existing analyzer regression fixture setup](../../backend/tests/test_code_intelligence_analyzers.py)
12. [Code Quality history](../../frontend/src/pages/code-quality/CodeQualityPage.jsx)
13. [Run detail](../../frontend/src/pages/code-quality/RunDetailPage.jsx)
14. [Scope UI tests](../../frontend/src/tests/codeQualityScope.test.jsx)
15. This report.

## Readiness verdict

| Subsystem | Verdict | Boundary |
|---|---|---|
| Static discovery | READY for controlled inspection | Exact-revision Python result and Windows TS/TSX extraction verified; aliases/dynamic behavior/bounds still limit conclusions. |
| Python Code Quality | PARTIALLY READY | Trusted local worktree/static fallbacks verified; remote source-only runs have no quality-tool assessment, and several optional tools are absent. |
| JS/TS Code Quality | PARTIALLY READY | Nested TS config routing repaired; parser/compiler verified; complete ESLint/dependency/coverage evidence unavailable. |
| Docker | BLOCKED | Linux daemon pipe unavailable; approved images and live workers unverified. |
| Automatic validated comparison | BLOCKED for this experiment | New functions have no previous implementation, no approved applicable contract, and Docker is unavailable. Better patterns/assertion links do not satisfy those prerequisites. |

No scoring formulas, authorization policies, GitHub synchronization/Actions
behavior, multi-agent activation or TaskFlow repository content were changed.
Review this working-tree slice separately from the earlier PR-visibility work.

## Checkpoint review and Docker diagnosis — subsequent verification

The 15-file slice above was reviewed against HEAD
`143d0ba689afec5cefa3729f707fdc3c09b6f7bd`. No blocking regression was found.
The earlier PR-visibility diff remains separate; GitHub Actions compatibility is
already in the parent commit. No environment, credential or demo-data files are
part of the checkpoint. No additional application changes were made during this
review. Engine formulas and authorization policies remain unchanged.

Fresh focused verification: **456 backend passed / 19 skipped / 0 failed**
(16.21 seconds), and **84 frontend passed / 0 failed** (four files, 22.20 seconds).
Scoped Mypy passed for eight source files; scoped Ruff passed with the previously
documented baseline E402 exclusion. The full suites/build results above belong
to the earlier implementation verification and were not rerun for this checkpoint.

Docker access now differs by execution environment:

- Restricted agent terminal: `docker version`, `docker info`, and `docker ps`
  report **permission denied** on `dockerDesktopLinuxEngine`.
- Approved execution outside the agent sandbox: those server operations succeed.
  Docker Engine 29.9.3 reports Linux x86_64, kernel
  `6.18.58.1-microsoft-standard-WSL2`; no containers are running.
- The active context is correctly `desktop-linux`, pointing to
  `npipe:////./pipe/dockerDesktopLinuxEngine`; no DOCKER environment override was
  present. Docker Desktop/backend processes and the WSL service are running.
- Both expected images are available as Linux amd64:
  `samanvaya-benchmark-python:1` =
  `sha256:4e518aaec4a220b4ea27f6c1a4898af7f576abea0f7b4459500f670f355f387c`;
  `samanvaya-benchmark-node:1` =
  `sha256:d658cc0e04da1ab1a79a5674a79cb45f414cd5bea00a2a201a354996ac553436`.

The current failure is an agent sandbox pipe-access restriction, not evidence
of a broken Linux daemon, incorrect context or a user-account permission failure.
This does not retrospectively establish why the pipe was absent during the
earlier verification. Docker/WSL settings were not changed and nothing was
installed, pulled, built or executed in a container during this diagnosis.

The 19 skipped cases in test_algorithm_runner were inspected: they use trusted
local sorting/syntax/unsupported-contract/stateful fixtures, the fixed worker
images and the existing isolated runner. Their infrastructure prerequisites are
now present. They can be run through approved execution outside the sandbox,
with the Docker-test opt-in scoped to that process. They remain **not executed**
in this checkpoint review; image availability is not a claim that they pass.
TaskFlow code, benchmark contracts and multi-agent flags were untouched.

Only this reviewed slice is authorized for the local checkpoint. The resulting
commit SHA and the remaining unrelated working-tree files are reported separately
after committing; this review does not authorize a push or merge.
