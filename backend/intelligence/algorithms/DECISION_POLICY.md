# Deterministic decision policy v1

The existing benchmark execution and persistence flow accepts an optional
`decision_policy`. Policy-backed decisions use engine `deterministic-decision-v1`.
The independently testable, data-only components are `evaluate_constraints` and
`compare_workloads`; `evaluate_decision` combines them without I/O or execution.

Requests that omit the policy keep the existing `objective: "time"` default,
sorting/generic workers and aggregate recommendation semantics. Policy-backed
requests keep those legacy aggregates for descriptive compatibility, but
`decision` is authoritative (`decision_authoritative: true`). The UI and explanation
flow suppress legacy winner claims when a structured decision exists. Historical
records are not retroactively upgraded: reevaluation adds their first explicit
decision revision only when requested.

## Example policy

Add this object to a generic-function benchmark request. Dataset IDs refer to
that request's explicit `datasets[].id` values. For the sorting preset they are
`sort:<size>:<distribution>`, for example `sort:100:random`.

```json
{
  "decision_policy": {
    "id": "project-performance-requirements",
    "version": "1",
    "objective": "MINIMIZE_TIME",
    "required_dataset_ids": ["small", "large"],
    "constraints": [
      {
        "id": "expected-output",
        "type": "EXPECTED_OUTPUT",
        "classification": "MANDATORY",
        "evaluation_policy": "ALL_EXPECTED",
        "source_reference": "project:spec/expected-values"
      },
      {
        "id": "small-latency",
        "type": "MAX_LATENCY",
        "classification": "MANDATORY",
        "dataset_ids": ["small"],
        "threshold": 0.01,
        "unit": "seconds",
        "metric": "elapsed_invocation_seconds",
        "evaluation_policy": "MAX_OBSERVED_INVOCATION",
        "source_reference": "project:spec/latency"
      },
      {
        "id": "tracked-peak",
        "type": "MAX_MEMORY",
        "classification": "MANDATORY",
        "threshold": 1000000,
        "unit": "bytes",
        "metric": "memray_peak_tracked_allocations_bytes",
        "evaluation_policy": "OBSERVED_PEAK",
        "source_reference": "project:spec/tracked-allocations"
      },
      {
        "id": "coverage",
        "type": "DATASET_COVERAGE",
        "classification": "MANDATORY",
        "required_dataset_ids": ["small", "large"],
        "evaluation_policy": "ALL_REQUIRED",
        "source_reference": "project:spec/required-cases"
      }
    ],
    "unknown_requirements": [
      {"id": "rss-budget", "description": "No process RSS budget has been established"}
    ]
  }
}
```

Only the four named constraint types are supported. Empty `dataset_ids` applies
to all declared datasets. Empty policy `required_dataset_ids` means all declared
datasets are required for whole-task suitability. Coverage is evaluated over its
explicit required set. Missing required datasets are `UNVERIFIED`, not observed
failures. Resource failure on one dataset does not erase eligibility on another;
failure on a required dataset prevents task suitability. A correctness failure
on any declared expected-output case makes the candidate contract-wide ineligible.
No-oracle contracts cannot establish correctness-backed eligibility.

Each constraint retains its source reference, classification, applicability,
scope, threshold, metric, observed value and evidence reference where applicable.
Repeated upper bounds are cumulative checks, not conflicts. Preferential failures
do not disqualify or add ranking weights. `applicability: "NOT_APPLICABLE"` reports
`NOT_APPLICABLE`; `"UNRESOLVED"` records a conflict. An
`unresolved_override_of` relationship must reference another constraint in the
same policy, remains unresolved, and never disables that constraint. This is not
an inheritance, organizational approval, or arbitrary policy expression system.

The API uses the existing engineering-role and project/organization authorization.
Every revision records the authenticated submitter and project context on the
server as project-authorized provenance. Source references are attribution, not
verification of external policy ownership. Client `approved`, `provenance`,
authority or resolved-override flags are rejected as unknown fields. There is no
new ability to confer organizational authority.

## Measurements and ranking

New-policy runs select worker protocol `independent-v1` on the server; clients
cannot choose availability. Correctness, timing and memory are independent.
Each case reports `timing_status`, `timing_error`, `memory_status`, `memory_error`
and `measurement_version`, alongside existing measurement fields. Statuses are
`AVAILABLE`, `UNAVAILABLE` or `INVALID`. The runner rejects contradictory statuses,
sample counts, values and errors, including silent protocol downgrade. An optional
profiler/clock failure does not discard other valid measurements. Every actual
invocation is validated, including the separate memory invocation. Behavioral
failure is never converted to optional unavailability. Submitted source executes
only in the existing Docker workers.

Latency constraints use the maximum of **all configured valid repetitions** in
seconds, with inclusive `observed <= threshold` bounds. Incomplete or invalid
samples cannot pass. Container deadlines and memory limits remain sandbox safety
settings, never inferred acceptance requirements.

The approved memory acceptance/optimization metric is Python's
`memray_peak_tracked_allocations_bytes`, with input cloning and validation outside
the tracked invocation. It is not RSS or total RAM. An established `rss_peak_bytes`
constraint can be represented, but is always `UNVERIFIED` with the current workers.
Node's signed `node_heap_used_delta_bytes` remains supplementary; it cannot satisfy
peak-memory constraints or rank memory objectives. No profiler was added.

Policy objectives are `MINIMIZE_TIME`, `MINIMIZE_MEMORY`, or `TRADEOFF_ONLY`.
Omitted/null policy objectives mean tradeoffs only, independent of the legacy
request objective. Memory optimization requires explicit
`memory_metric: "memray_peak_tracked_allocations_bytes"`.

Timing policy defaults (`timing.version: "1"`):

| Field | Default | Meaning |
| --- | --- | --- |
| `minimum_samples` | 3 | At least 3 samples per candidate/dataset for comparison |
| `practical_difference_ratio` | 0.05 | Runner-up median must be strictly more than 5% above best |
| `maximum_variability_ratio` | 0.20 | `(maximum - minimum) / median` must be at most 20% |

The engine reports count, median, minimum, maximum and range/median variability.
Zero-duration, negative, nonfinite, invalid, unavailable and incomplete samples
never establish time superiority. Equality at the practical threshold is
inconclusive; equality at the variability threshold is allowed. Float-boundary
comparisons use `math.isclose(rel_tol=1e-12, abs_tol=1e-15)`. These policies do not
provide statistical confidence. Memory ranking requires a strictly lower observed
tracked peak; equal peaks are inconclusive, with no implicit timing tie-breaker.

All comparisons are per exact tested dataset, between eligible candidates in the
same run with compatible worker/image/runtime/tool/resource/method provenance.
The versioned `typed-json-sha256-v1` fingerprints preserve argument order, JSON
types (including bool/int/float distinctions), input values, validation, contract,
source implementations, execution context and policy identity. Labels/dimensions
alone never establish identity. Missing historical methodology provenance is not
upgraded to compatibility. There is no cross-run ranking or global optimum.

`ELIGIBILITY_ONLY` means one candidate is verified eligible without a comparable
eligible rival; it is not a speed/memory winner. All demonstrable failures produce
`NO_ELIGIBLE_IMPLEMENTATION`; failure plus unverified mandatory evidence produces
`INSUFFICIENT_EVIDENCE`. Unresolved requirements produce `REQUIREMENT_CONFLICT`.
Different datasets can have different winners. Unknown requirements stay metadata,
do not invent constraints or block valid timing, and prevent broader compliance
claims. Dataset findings and task suitability are distinct authoritative outputs.

## Reevaluation and persistence

`POST /api/algorithms/runs/{run_id}/reevaluate` accepts
`{"decision_policy": {"id": "new-policy", "version": "1", "constraints": []}}`.
It requires existing engineering/project authorization and a completed run, and
works even when benchmark execution is disabled. It never invokes the runner.

MongoDB atomically appends `decision_revisions`, increments an optimistic revision
counter, and sets `decision` to the appended revision. Concurrent submissions retry
against the current counter rather than replacing each other's history. Every
revision has a unique ID, sequence number, timestamp, engine/policy versions,
snapshot/fingerprints, immutable evidence references and server-established
provenance. Raw evidence, original request and earlier decisions remain preserved.
Evidence and execution-context fingerprint mismatch rejects reevaluation. There
is no retroactive claim about policies that were not applied previously. Revisions
remain in the existing run document; a 16 MB document budget rejects oversized
appends without removing prior revisions.

Ollama can only select validated deterministic fact IDs. Policy-backed prompts
exclude legacy winner facts. Invalid or unavailable model output falls back to the
deterministic result and never changes it.

## Verification and deployment

Focused pure/API/service/worker-instrumentation tests are in
[`test_deterministic_decision.py`](../../tests/test_deterministic_decision.py) and
[`test_decision_integration.py`](../../tests/test_decision_integration.py).
Execution tests are in [`test_decision_docker.py`](../../tests/test_decision_docker.py)
and remain opt-in via `SAMANVAYA_DOCKER_BENCHMARK_TESTS=1` on an isolated supported
Docker Linux environment. Rebuild **both** worker images using the commands in
the [worker setup guide](../../benchmark_worker/README.md) before new-policy runs;
old images lack `independent-v1` and are deliberately rejected.

No cross-run ranking, production workload weighting, RSS profiler, correctness
proof, purpose recognition, natural-language requirement discovery or policy
authority system is implemented. The next deployment milestone is to rebuild and
exercise the worker images and revision concurrency against real MongoDB in an
isolated integration environment before enabling policy-backed execution.

## Files changed for this milestone

- Policy/request schemas: [decision_policy.py](../../domain/schemas/decision_policy.py),
  [algorithm_benchmark.py](../../domain/schemas/algorithm_benchmark.py).
- Pure engine/protocol/controller: [decision.py](./decision.py),
  [measurements.py](./measurements.py), [runner.py](./runner.py).
- Workers: [python_worker.py](../../benchmark_worker/python_worker.py),
  [node_worker.cjs](../../benchmark_worker/node_worker.cjs).
- Service/API: [algorithm_benchmark_service.py](../../domain/services/algorithm_benchmark_service.py),
  [algorithms.py](../../api/routes/algorithms.py).
- Frontend: [algorithms.api.js](../../../frontend/src/api/algorithms.api.js),
  [AlgorithmComparisonPanel.jsx](../../../frontend/src/pages/code-quality/AlgorithmComparisonPanel.jsx),
  [DecisionResults.jsx](../../../frontend/src/pages/code-quality/DecisionResults.jsx).
- Tests: [test_deterministic_decision.py](../../tests/test_deterministic_decision.py),
  [test_decision_integration.py](../../tests/test_decision_integration.py),
  [test_decision_docker.py](../../tests/test_decision_docker.py),
  [algorithmComparison.test.jsx](../../../frontend/src/tests/algorithmComparison.test.jsx).
- Documentation: this guide and [worker README](../../benchmark_worker/README.md).

## Implementation verification (2026-11-10)

The combined backend run covered the three new decision test modules plus existing
algorithm evidence, generic function evidence, runner, function contracts, workers,
source structure, benchmark API and benchmark service suites: **1,038 passed,
80 Docker opt-in tests skipped, 4 existing Pydantic deprecation warnings**. The
decision unit/integration subset comprises **82 passing tests** (included in the
combined total). On Windows, two existing oversized parameter display IDs exceeded
the 32,767-character environment-variable limit. A runtime collection hook shortened
only those display IDs to hashes; all original test inputs/assertions were executed.
The initial sandbox also denied pytest/Vite helper access; final runs used approved
local execution. No tests were weakened or removed.

Frontend command `npm run test -- --run src/tests/algorithmComparison.test.jsx`:
**58 passed**. `npm run build`: **passed**. `node --check` on the worker: **passed**.
The new tests mock measurements, instrumentation, MongoDB and Ollama as appropriate.
No submitted candidate code was executed on the host. Actual Docker worker execution,
real MongoDB integration and unrelated product test suites were not run. Thus the
implementation has local regression verification; deployment integration remains
pending as described above.
