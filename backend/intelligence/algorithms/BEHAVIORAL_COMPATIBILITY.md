# Phase 3: behavioral compatibility within an approved finite scope

This extends Phase 1's generic contracts, expected-output workers, MongoDB jobs,
correctness evidence and deterministic decision engine. Phase 2 function identities,
source revisions, call sites, static tests and task hypotheses provide context only.
The benchmark framework and existing sorting/generic interfaces remain intact.

## Contract authority and lifecycle

`POST /api/algorithms/contracts` creates a **PROPOSED** immutable contract version.
It reuses the generic `contract` and `datasets` schema and adds explicit required
check IDs, requirement/source references and a finite scope description. Optional
Phase 2 function bindings associate requirements with snapshots, not with proven
correct implementations. Names and inferred purposes never approve a contract.

An independent authorized project LEAD, PM, CEO or administrator reviews the
expected values, requirements and coverage scope and explicitly approves the
returned content fingerprint using
`POST /api/algorithms/contracts/{contract_id}/approve`. Self-approval, organization
mismatches, stale fingerprints, repeated approvals and client-supplied approval
metadata are rejected. No generated model text or candidate-supplied validator
establishes authority. This is a recorded project review, not mathematical proof
that requirements or expected values are universally sufficient.

Approved content cannot be edited through these APIs. Changes need a new contract
version. Multiple referenced contracts must resolve to the same immutable scope;
missing or conflicting references cannot be silently discarded.

The new catalog uses `algorithm_function_contracts`. Comparisons continue to use
`algorithm_benchmark_runs`, including its project-level lease, concurrency limits,
history, cancellation handling and evidence preservation.

### Proposal shape

```json
{
  "project_id": "YOUR_PROJECT_ID",
  "contract": {
    "kind": "function", "name": "reachable-node-collection", "version": "1",
    "input_schema": {"type": "array"},
    "output_schema": {"type": "array", "items": {"type": "string"}},
    "correctness": "expected", "mutation": "forbidden",
    "comparison": {"mode": "unordered_set", "version": "1"}
  },
  "datasets": [
    {"id": "branch", "args": [{"s": ["a", "b"], "a": ["b"], "b": []}, "s"], "expected": ["s", "a", "b"]},
    {"id": "isolated", "args": [{"s": []}, "s"], "expected": ["s"]}
  ],
  "required_dataset_ids": ["branch", "isolated"],
  "requirements": [{
    "id": "reachable-membership", "description": "Return reachable nodes; traversal order is outside this scope",
    "source_reference": "REPLACE_WITH_YOUR_REQUIREMENT_REFERENCE",
    "dataset_ids": ["branch", "isolated"]
  }],
  "scope_description": "Only the independently reviewed supplied graph cases; no untested-input guarantee",
  "validator_requirement": "expected_output",
  "function_bindings": []
}
```

Approval requires `expected_fingerprint`, `source_reference`, `rationale` and an
explicit boolean `scope_reviewed: true`. The reviewer must be a different
authenticated person from the proposer. These example cases are illustrative;
the project reviewer is responsible for the real required checks and scope.

## Narrow validation adapters

The generic contract's optional `comparison` descriptor is versioned data only:

| Mode | Comparison |
|---|---|
| `exact` (default) | Existing typed JSON equality; arrays keep their order |
| `unordered_set` | Explicit top-level collection membership; duplicates/order ignored |
| `unordered_multiset` | Explicit top-level order independence while preserving multiplicity |
| `one_of` | Exact match to one of 1–16 approved `acceptable_outputs` per dataset |

Nested array order remains significant in every mode. Boolean values remain
distinct from numbers. Set modes require an explicit array output schema. Only
`unordered_set` permits native Python set/frozenset and JavaScript Set outputs to
be adapted into JSON arrays inside the workers. Other iterables and arbitrary
normalizers are not accepted. Schema and mutation checks still apply.

For `one_of`, retain the usual `expected` value as one of the approved alternatives
and add `acceptable_outputs` to the dataset. This can enumerate multiple valid
shortest paths for a reviewed graph without introducing a graph oracle or
declaring all permutations valid. The caller cannot supply executable validators.

An approved scope can explicitly require `numerical_tolerance`, `property_oracle`
or `stability_oracle`. Those validators are unavailable in this milestone: its
result is **UNVERIFIED**, execution is skipped and no substitute validator is
invented. Stability can still be checked on explicitly approved expected-output
fixtures with exact order; that is a finite check, not a universal stability proof.

## Relationships, execution and results

- `GET /api/algorithms/compatibility/relationships` takes `project_id`,
  `previous_run_id` and `current_run_id`. It returns at most 50 **PROVISIONAL**
  relationships from saved Phase 2 snapshots: lexical identity across recorded
  revisions, call sites, static test context, task hypotheses and approved
  contract bindings. A SHA label alone does not establish Git ancestry or age.
- `POST /api/algorithms/compatibility/runs` accepts `project_id`, `previous`,
  `current` and `contract_ids`. Each implementation has the existing name/source/
  entrypoint fields plus its `language` and optional `function_reference`
  (`run_id`, `function_id`). Referenced Phase 2 source hashes, languages and
  entrypoints must match. Previous/current labels alone establish no chronology.
- Optional `dataset_ids` restricts execution for diagnostics. Omitted required
  checks remain missing and cannot yield compatibility, even if all selected
  checks pass. `repetitions`, resource limits and an optional Phase 1 policy use
  the existing bounded interfaces. The default policy is tradeoffs only.
- Both implementations receive identical approved inputs, output rules and
  expected values. Same-language pairs use the same existing worker path;
  Python/JS/TS mixed pairs use those existing language-specific workers. Developer
  source is executed only in hardened, network-disabled Docker containers.
- Every completed invocation is validated, including warmups, timed invocations
  and the memory invocation. Worker evidence includes `functional-validation-v1`,
  completed validation counts and a distinction between a data-contract violation
  and unavailable/incomplete execution evidence. Old worker flags are insufficient.

| Result | Meaning |
|---|---|
| `COMPATIBLE_WITHIN_TESTED_CONTRACT` | Both implementations pass every required available check in the approved scope |
| `INCOMPATIBLE` | A relevant approved validation check demonstrates a behavioral violation |
| `UNVERIFIED` | Proposed/conflicting authority, missing checks, unsupported validator, source mismatch or incomplete execution prevents a conclusion |
| `CONTRACT_MISSING` | No trustworthy comparison contract was resolved |

Results include previous/current identities, contract/approval snapshots, required
checks, requirement sources, pass/fail/unverified checks, exact evidence references,
input fingerprints, an execution-evidence binding and remaining unverified behavior.
Useful static observations are retained even if validation cannot proceed.

## Phase 1 prerequisites

Compatibility requests pass an explicit source/contract/evidence-bound eligibility
input into Phase 1. Its correctness normalization blocks ranking whenever that
prerequisite is absent, mismatched, incompatible or unverified. Relevant known
violations remain failures; infrastructure failures are not promoted to behavioral
proof. Raw measurements are preserved, and policy reevaluation cannot waive an
unapproved or incomplete functional scope. The ranking formulas, constraints,
timing thresholds, memory metrics and deterministic policy are unchanged.

Passing compatibility permits Phase 1 to evaluate its normal measurement and
methodology prerequisites; it does not guarantee a performance winner. In
particular, different runtimes can remain methodologically incomparable. Existing
manual sorting/generic runs retain their current caller-declared measurement
semantics; they do not acquire replacement certification automatically.

## UI and deployment

Code Quality contains **Behavioral compatibility** for proposals, explicit review,
provisional relationships and validation submission. Benchmark results show the
compatibility section; discovered functions offer read-only compatibility history
with `GET /api/algorithms/compatibility/functions/{function_id}/history`.
Every endpoint uses existing engineering roles and project/organization access.

Rebuild the existing two worker images after this validator update, then restart
the backend. Benchmark opt-in and the established Windows single-worker startup
requirements remain unchanged. No new execution platform is needed.

```powershell
docker build -f backend/benchmark_worker/Dockerfile.python -t samanvaya-benchmark-python:1 backend/benchmark_worker
docker build -f backend/benchmark_worker/Dockerfile.node -t samanvaya-benchmark-node:1 backend/benchmark_worker
```

Focused tests are `test_behavioral_compatibility.py`,
`test_behavioral_compatibility_api.py`, and the opt-in
`test_behavioral_compatibility_docker.py`. Docker tests cover actual Python/JS/TS
reachability, shortest-path counterexamples, traversal-order violations, finite
acceptable paths, native sets, mixed-language cases and missing required checks.
Host tests never execute submitted candidate functions.

No universal equivalence, unrestricted generated tests, complex oracle registry,
training, RAG, automatic candidate replacement or automatic benchmarking of every
discovered function is introduced. Existing worker evidence remains subject to
its documented non-tamper-proof harness limitation against malicious submissions.
