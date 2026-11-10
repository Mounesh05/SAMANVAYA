# Docker numeric sorting benchmarks (v1)

Versioned deterministic decisions are opt-in through `decision_policy`. See the
[policy schema, defaults, independent measurements and reevaluation guide](../intelligence/algorithms/DECISION_POLICY.md).
Rebuild both worker images before using policy-backed runs.

`intelligence.algorithms.runner` exposes `DockerBenchmarkRunner`,
`BenchmarkUnavailable`, and `BenchmarkFailure`. The controller has no application
configuration or third-party imports. Candidate source is **never executed on the
host**. It is passed over stdin to a fixed image, one fresh container per candidate.
Python/Node harnesses execute source in a child process **inside that container**.
No host filesystem mounts, Docker socket mounts, or runtime image pulls are used.

## Build (from repository root)

Linux containers are required (on Windows, use Docker Desktop's Linux engine).
Builds require network access to download the base images and dependencies:

```sh
docker build -f backend/benchmark_worker/Dockerfile.python -t samanvaya-benchmark-python:1 backend/benchmark_worker
docker build -f backend/benchmark_worker/Dockerfile.node -t samanvaya-benchmark-node:1 backend/benchmark_worker
```

Base image versions and direct worker dependencies are pinned. Base tags are not
immutable digests and transitive Python dependencies are not fully locked; rebuilds
are not bit-for-bit reproducible. Maintain these images as trusted local artifacts,
scan/update their dependencies, and restrict who can replace the fixed image tags.
The backend does not need pyperf, Memray, Node, or TypeScript installed on its host.

## Application setup (including Windows)

Execution is **disabled by default**. The existing quality/security analyzers do
not need Docker and remain available when these comparisons are disabled.

1. Provision Docker yourself on a dedicated benchmark machine/VM. On Windows,
   Docker Desktop must use **Linux containers**, with a working WSL 2 or supported
   Hyper-V backend. Installing the Python `memray` package on Windows is not a
   substitute for this backend. This feature does not install or configure system
   software, download a model, or provision paid services.
2. In a new terminal, run `docker version` and `docker info --format '{{.OSType}}'`.
   The first command must show a reachable server; the second must print `linux`.
   If the command is missing, fix PATH/restart the terminal. If the daemon or WSL
   fails, repair Docker Desktop's backend before enabling execution. Do not switch
   to a host-execution fallback.
3. Build **both** images with the commands above. Builds use the network; benchmark
   containers do not. The application never pulls images while running submissions.
4. Use the application's existing backend environment and MongoDB settings:
   `MONGO_URI`, `DB_NAME`, and the required `SECRET_KEY`. The feature stores evidence
   in `algorithm_benchmark_runs` in that database; it needs no second database or
   vector service. Use MongoDB **4.2 or newer** for atomic feedback updates. The
   database user must be able to create the collection/indexes and read/write it.
5. Set `ALGORITHM_BENCHMARK_ENABLED=true` in `backend/.env` or the backend process
   environment, then restart the backend. On PowerShell, a process-only override
   is `$env:ALGORITHM_BENCHMARK_ENABLED = "true"`.
6. For a native Windows benchmark backend, run from `backend` with
   `python -m uvicorn main:app --host 127.0.0.1 --port 8000` using its configured
   environment. Avoid `--reload`, multiple `--workers`, and the development
   `start.py` launcher for this process: Windows reload/worker modes can select an
   event loop without asyncio subprocess support. Keep the existing frontend/API
   configuration and authentication flow.
7. Sign in with project access, open **Code Quality**, expand the sorting comparison
   panel, and check availability. Submit 2–5 named functions for one language and
   an existing project ID. Read-only authorized users may inspect history;
   engineering roles (DEVELOPER, LEAD, PM, CEO, QA, DEVOPS) or administrators may
   submit comparisons, feedback, and explanation requests. All project operations
   require matching organization metadata and the shared project-access policy.

Docker daemon access is powerful. Do not expose an unauthenticated Docker TCP
socket or mount it in a submitted worker. If the backend itself is containerized,
provision its daemon access deliberately; this guide does not install a privileged
Docker-in-Docker service. Docker limits are per candidate, not a complete host
resource reservation. An isolated host/VM is still required for untrusted code.

### Authenticated asynchronous HTTP API

All routes use the application's existing authentication dependency:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/algorithms/availability` | Opt-in state, local worker images, actionable setup errors |
| POST | `/api/algorithms/runs` | Validate request and return HTTP 202 with `run_id`, `status` |
| GET | `/api/algorithms/runs/{run_id}` | Poll status; retrieve measurements, recommendation, provenance |
| GET | `/api/algorithms/projects/{project_id}/history?limit=10` | Project history, without candidate source bodies |
| POST | `/api/algorithms/runs/{run_id}/feedback` | Record accepted/rejected decision and reason |
| POST | `/api/algorithms/runs/{run_id}/explanation` | Optional evidence-only model selection with deterministic fallback |

Example run request (the API requires 2–5 candidates; the lower-level runner below
also permits single-candidate diagnostics):

```json
{
  "project_id": "your-existing-project-id",
  "language": "python",
  "candidates": [
    {"name": "returned", "entrypoint": "sort", "source": "def sort(values): return sorted(values)"},
    {"name": "inplace", "entrypoint": "sort", "source": "def sort(values): values.sort()"}
  ],
  "sizes": [0, 1, 100, 1000],
  "distributions": ["random", "sorted", "reversed", "duplicates"],
  "repetitions": 5,
  "seed": 42,
  "objective": "time",
  "memory_limit_bytes": null
}
```

Poll until `completed`, `failed`, or `unavailable`; `pending` and `running` are
nonterminal. Schema/unsupported requests return 422, inaccessible projects return
403/404, a second active project job returns 409, and disabled submission returns
503. Completion does **not** imply a winner: inspect recommendation status and
case correctness. Python supports `objective: "memory"` and an optional positive
`memory_limit_bytes` up to 536870912 for **tracked allocations**, not total RAM.
JS/TS rejects memory objectives/limits rather than interpreting heap delta as peak
memory. Feedback is `{"decision":"accepted","reason":"Reviewed the measured cases"}`
(or `rejected`) and requires a completed comparison. No endpoint rewrites source.

### Evidence, retrieval, and model boundary

Only current candidates passing **every** requested case, invocation, measurement,
and supported constraint are eligible. Timing rank is the equal-weight geometric
mean of per-case medians; a difference within 5% is inconclusive, not a statistical
significance result. Python memory rank uses the maximum per-case tracked peak.
Selecting the only passing candidate is explicitly a validity decision, not a
speed comparison. Numeric probes currently use finite **integer** datasets;
passing them does not establish arbitrary floating-point/NaN behavior, stability,
custom comparator support, or general-purpose Big-O complexity.

MongoDB retains raw samples, sources, source hashes, tool/image/runtime details,
request parameters, deterministic recommendation, citations, and user decisions.
There is no automatic retention/purge policy: protect source access, back up the
collection according to existing policy, and plan storage retention. The first
submission creates unique run and active-project indexes plus a history index.
Legacy projects/users need valid matching `org_id` values; missing organization
metadata is denied rather than silently granted access.

Retrieval selects at most five older completed runs from the **same project,
protocol, and workload**. Their references, decisions, source hashes, and recorded
environment-match flag are historical context only, never inputs to the fresh
ranking. Follow a referenced run to inspect its full environment. Environment
matches compare the recorded provenance, not proof of identical hardware, host
load, or unchanged source. Host CPU model/clock and scheduling conditions are not
fully captured; repeat controlled measurements before making close decisions.

Recommendations work without Ollama or any LLM. Only an explicit explanation
request contacts the configured `OLLAMA_BASE_URL` / `OLLAMA_MODEL`; no model is
downloaded automatically. That request sends evidence fact text (including
candidate labels/results and historical references), but **not source code or
user-written feedback**, to that configured service. Use a trusted local endpoint
or review remote-service privacy/cost implications. The model can select only
existing fact IDs; rendered explanations use stored facts and citations, never
model-authored numerical/prose claims. Unavailable/invalid model responses return
a deterministic evidence explanation and do not change the ranking.

### Job lifecycle and operating limits

This first slice uses FastAPI `BackgroundTasks`, **not a durable task queue**.
MongoDB stores the job and evidence; backend restart does not resume a submission.
A ten-minute lease covers queueing/execution. Expired active jobs are marked failed
on subsequent create/get/history/execute activity; there is no periodic reaper.
One active job is allowed per project via a Mongo unique partial index. At most two
jobs run concurrently **per backend process**; this is not a cluster-wide capacity
limit. Deploy a single controlled benchmark process or provision a durable queue,
global admission limits, and operational monitoring before scaling this service.
Set the opt-in flag false and restart to disable new submissions; saved evidence
remains readable. Existing in-flight work is not a durable/restart-safe workload.

## Runner API

```python
from intelligence.algorithms.runner import DockerBenchmarkRunner

runner = DockerBenchmarkRunner(timeout_seconds=120, max_output_bytes=2_000_000)
status = await runner.availability()
result = await runner.run({
    "language": "python",
    "candidates": [
        {"name": "builtin", "source": "def sort(values): return sorted(values)", "entrypoint": "sort"}
    ],
    "sizes": [0, 100, 1000],
    "distributions": ["random", "sorted", "reversed", "duplicates"],
    "repetitions": 3,
    "seed": 42,
})
```

Languages: `python`, `javascript`, `typescript`. A source must define the named,
synchronous function taking one numeric list/array. Return a sorted list/array,
or Python `None` / JavaScript `undefined` after sorting in place. JavaScript
`null`, promises, generators, nonnumeric elements, and sparse arrays are invalid.
JS/TS top-level function declarations and CommonJS exports are supported; TS
`export function` works via CommonJS transpilation. Imports must be available in
the image; there is no dependency installation per candidate. TS uses pinned
`transpileModule` with error diagnostics: syntax/options errors are reported, but
this is **not** whole-program semantic type checking.

Controller guards: 1–5 uniquely named candidates; 1–16 distinct sizes in 0–10000;
1–4 distinct known distributions; 1–10 repetitions; unsigned 32-bit seed; source
1–200000 UTF-8 bytes per candidate; names up to 200 characters; simple identifier
entrypoints. Invalid input raises `ValueError` before invoking Docker.

`availability()` checks the daemon and **both** fixed local image names:

```text
{available: bool,
 environment: {docker_version: str, images: {image_name: image_id}} | {},
 error: str | None}
```

It returns `available: false` with an actionable reason if unavailable.
`run()` checks only the image required by its language and raises
`BenchmarkUnavailable` when the Docker CLI/daemon or image is missing (including
the build command). There is no user-selectable image. Timeouts, nonzero worker
exits, output overflow, or malformed protocol/results raise `BenchmarkFailure`.
Cancellation propagates `asyncio.CancelledError` after cleanup.

### Exact successful result schema

All keys shown below are always present. JSON `null` corresponds to Python `None`.
Candidate results follow request order; cases follow sizes then distributions.

```text
{
  environment: {
    docker_version: str,
    images: {fixed_image_name: image_id},
    isolation: "docker",
    network: "none",
    cpus: 1,
    memory_limit_bytes: 536870912,
    pids_limit: 64,
    timeout_seconds: number,
    timing_method: "warmups_then_repeated_samples_not_calibrated",
    seed: int,
    language: "python" | "javascript" | "typescript",
    workers: [{
      candidate: str,
      runtime: str,
      platform: str,
      warmups: 2,
      input_generator: "lcg32-v1"
    }]
  },
  results: [{
    candidate: str,
    cases: [{
      size: int,
      distribution: "random" | "sorted" | "reversed" | "duplicates",
      correct: bool,
      timings_seconds: [float],
      memory_bytes: int | null,
      memory_metric: "memray_peak_tracked_allocations_bytes" | "node_heap_used_delta_bytes",
      error: str | null
    }],
    error: str | null
  }],
  tools: {
    // Python:
    pyperf: str, memray: str, timing: str, memory: "memray_peak_tracked_allocations_bytes"
    // OR JS/TS (TypeScript is installed in the shared Node image):
    node: str, typescript: str, timing: str, memory: "node_heap_used_delta_bytes"
  }
}
```

A load/compile/entrypoint error sets candidate `error` and `cases: []`.
A wrong result or exception sets case `correct: false` and case `error`;
other cases/candidates continue. Partial successful sample timings may remain.
A successful case has exactly `repetitions` timings, non-null memory, and no error.
`correct` means all warmups, timed runs, and the separate memory run validated;
it is false as well if memory instrumentation fails (see the case error).

## Measurement semantics

* Identical inputs across languages and candidates use `lcg32-v1`: unsigned
  `state = (1664525 * state + 1013904223) mod 2**32`, starting at the supplied
  seed for each case. Random values are `state % 20001 - 10000`; duplicate-heavy
  values are `state % 8`. Sorted/reversed use the same random multiset. Input
  copies and correctness checks are excluded from timing. Every invocation is
  validated against the expected sorted sequence (both order and multiset).
* Python: two warmups, then one `pyperf.perf_counter` duration per repetition.
  These are **uncalibrated repeated samples**, not `pyperf.Runner` calibrated
  benchmarks. In a separate call, Memray tracks the function invocation with
  `trace_python_allocators=True` and `native_traces=True`. A `FileReader` sums
  `size` of `get_high_watermark_allocation_records()` for peak simultaneously
  live **tracked allocation bytes**. Memray observes native allocation APIs and
  Python allocators; `native_traces` adds native stack information, not an RSS
  measurement. This is not process RSS, total allocations, exclusively native
  memory, or peak memory of all child processes. Pre-existing input allocations
  are excluded; allocator caches and allocations outside intercepted APIs are
  subject to Memray's normal limitations. Tracking overhead is not timed.
* Node: two warmups and repeated `performance.now()` durations, in seconds.
  Separate memory invocation records `process.memoryUsage().heapUsed` after
  minus before. An exposed GC is requested **before** the measurement, not after.
  This is a **signed, noisy heap-used delta**, potentially negative due to GC;
  it excludes external/native/ArrayBuffer memory and is neither a peak nor total
  allocation count. Do not compare it directly to Memray's metric.
* Containers share the host's CPU/kernel and scheduling noise. Comparisons are
  exploratory, not stable statistical performance claims or cross-runtime memory
  equivalence. No adaptive iteration calibration is performed.

## Isolation, budgets, and trust limits

Each container has network disabled, all capabilities dropped, no-new-privileges,
UID/GID 65532, read-only root, `/tmp` bounded at 64 MiB with
`noexec,nosuid,nodev`, 512 MiB memory with no additional swap, one CPU, 64 PIDs,
128 file descriptors, Docker's default seccomp policy, and an init process.
Container logs are disabled; no ports or host paths are exposed. CLI calls use
`asyncio.create_subprocess_exec`, never a shell. Stdin and both output pipes are
handled concurrently; combined stdout/stderr is bounded per Docker CLI invocation
(default 2 MB). Worker supervisors bound input at 1.3 MB and result files at 2 MB.
Candidate stdout/stderr is discarded, preventing normal prints from corrupting
JSON or filling host memory/disk. Each candidate gets a unique container name.
The controller issues `docker rm --force` in `finally`, including timeout,
protocol failures, and cancellation, even though `--rm` is also set.

The controller timeout is a **shared total deadline**, including availability and
all candidates, not 120 seconds per candidate. Child harnesses additionally have
an independent 115-second upper bound. Cleanup gets up to five extra seconds per
in-flight removal, so wall-clock return can exceed the configured work deadline.
Cleanup is best-effort: daemon failure can prevent removal; operators should
monitor containers with the `samanvaya-benchmark-` prefix. No host shutdown hook or
persistent janitor is installed by this subsystem.

**The harness is not tamper-proof.** Candidate execution shares its child process,
UID, and writable temporary filesystem with measurement code. The parent
supervisor only isolates ordinary stdout/stderr via a result file. A malicious
candidate can introspect/patch the harness, alter files, interfere with its parent,
forge structurally valid results, or deliberately game timings/correctness.
Protocol/schema checks cannot authenticate measurements. Node `vm` is used only
for a lexical namespace, **not** a security sandbox. Docker hardening constrains
host exposure but is not a proof against container/kernel vulnerabilities. Use
an isolated benchmark host/VM with no sensitive workloads, and treat submissions
and results as untrusted; do not use results as an adversarial grading authority.

## Validation

From `backend` (the existing test environment must have its test dependencies):

```sh
python -m pytest tests/test_algorithm_runner.py tests/test_algorithm_benchmark_api.py tests/test_algorithm_benchmark_service.py tests/test_algorithm_evidence.py -q
python -m compileall -q intelligence/algorithms/runner.py benchmark_worker/python_worker.py tests/test_algorithm_runner.py
node --check benchmark_worker/node_worker.cjs
```

Default tests mock every Docker subprocess, validate hardening/cleanup/bounds and
protocol failures, and test only pure input generation on the host. They **never
execute candidate source on the host**. Opt-in integration tests execute only
trusted, checked-in sort fixtures **in Docker**. Build both images first, then:

```sh
SAMANVAYA_DOCKER_BENCHMARK_TESTS=1 python -m pytest tests/test_algorithm_runner.py -q
```

For PowerShell, set `$env:SAMANVAYA_DOCKER_BENCHMARK_TESTS = "1"` first. Opt-in tests
fail (rather than silently skip) if Docker/images are unavailable. They cover
returned and in-place sorting, all distributions, empty/single-element inputs,
incorrect multiset handling, noisy candidate output, TS syntax diagnostics, and
unsupported async/generator/nonnumeric/return-value contracts. These tests are
skipped unless explicitly enabled; mocked controller tests do not establish that
Memray or the built container images work on this machine.

From `frontend`, run the UI tests and production build separately:

```sh
npm run test -- --run src/tests/algorithmComparison.test.jsx
npm run build
```

Real MongoDB connectivity/persistence and live application-to-Docker execution
must additionally be smoke-tested in the deployment environment. The focused
service/API tests use in-memory Mongo substitutes and mocked benchmark runners.
