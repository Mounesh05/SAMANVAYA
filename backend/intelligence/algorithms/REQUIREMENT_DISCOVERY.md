# Phase 4: evidence-driven requirement discovery

Phase 4 reuses project configuration, project-scoped MongoDB evidence, Phase 2
function snapshots, Phase 3 approved contracts and Phase 1 deterministic policy
evaluation. It never executes developer code or requires Ollama. Benchmark
execution continues through the existing isolated workers.

## Existing source gaps

Quality thresholds and container resource limits are not algorithm acceptance
budgets. Tasks currently store titles but no acceptance criteria or approval.
Stories expose descriptions without requirement authority metadata. PR sync now
preserves descriptions, immutable head SHA and update time; code-review approval
does not approve requirements. Unavailable fields produce explicit limitations.

## Sources and authority

`POST /api/algorithms/requirements/discover` takes a project ID and optional exact
context references: `contract_ids`, `discovery_run_ids`, `function_ids`, `task_ids`,
`story_ids`, `pr_ids`, `benchmark_run_ids`, repository and source revision.
Project access and organization are checked on every endpoint. Referenced
records are loaded in that project; unrelated task text is never attached through
similarity. Task/story text and PR descriptions are quoted proposals. No threshold
is extracted from prose and enforced automatically.

Approved Phase 3 contracts establish their reviewed input schema and finite
functional requirements. Datasets establish observed inputs and dimensions,
never maximum production size or frequency. Historical benchmarks remain
observations tied to the preserved run. Phase 2 structures, call sites and purpose
hypotheses remain observations or suggestions, never functional approvals.

For connected repositories, `.samanvaya/requirements.json` is fetched at the
same immutable SHA as source discovery. It may contain:

```json
{
  "version": "1",
  "requirements": [{
    "id": "latency",
    "type": "MAX_LATENCY",
    "key": "latency",
    "value": 0.025,
    "unit": "seconds",
    "metric": "elapsed_invocation_seconds",
    "description": "Maximum observed invocation time on the approved workload",
    "scope": {"dataset_ids": ["reviewed-workload"]}
  }]
}
```

These values illustrate the format, not application defaults. Repository files
are untrusted proposals even if they contain approval claims. The parser accepts
only version and structured requirements, with bounded sizes. They are retained
in the existing function-discovery snapshot. Invalid documents produce diagnostics.

## Confirming one unresolved source

`POST /api/algorithms/requirements/sources` accepts `project_id`, `source_kind`
(`project_configuration` or `repository_configuration`), `source_reference`,
`source_revision`, and structured `requirements`. Repository configuration needs
an exact repository scope. The response includes a content fingerprint and
`PROPOSED` status. Approval/status fields are rejected in proposals.

`POST /api/algorithms/requirements/sources/{id}/approve` requires an independent
LEAD, PM, CEO or admin in the project organization, the exact reviewed fingerprint,
a review reference, rationale and explicit scope acknowledgement. This is the
authorization process establishing that the referenced source actually warrants
the declared requirement. Source contents are immutable through the API. Existing
project configuration stores server-maintained source references; ordinary config
writes cannot forge or erase them. Reviewed evidence is stored in
`algorithm_requirement_sources`, not a separate requirements agent/platform.

A new reviewed revision can explicitly `supersedes` one earlier source. Newer
timestamps alone never supersede requirements. Approved replacements are resolved
even if a crash interrupted the old record's status update. Concurrent approved
replacements, tampered approved content and unresolved overrides are conflicts.

## Policy preparation and limits

The production benchmark service automatically imports approved project sources
before creating jobs and before reevaluation. It persists the report with the run
and each decision revision. API requests may supply references, never a trusted
discovery report. Client IDs cannot shadow imported constraints. Reevaluation
re-reads current approved sources and preserves raw execution evidence.

Repository identity comes from the project's connected GitHub configuration.
Function IDs and revision labels must bind to stored discovery evidence matching
submitted source bytes and entrypoints. Without that binding, scoped requirements
remain unresolved; they cannot be evaded through invented reference labels.
An approved referenced functional contract must match the submitted contract.

Latency uses seconds and `elapsed_invocation_seconds`. Memory uses integer bytes
and an explicit recognized metric. RSS is never substituted for Memray tracked
allocation peak; absent compatible measurements remain unverified. Two applicable
upper bounds are both enforced (100 and 200 bytes imply at most 100 bytes).
Different explicit output requirements on overlapping workloads are conflicts.
Configuration-based input/output declarations without an approved functional
validator block eligibility pending resolution; no custom validator registry is
introduced. Dataset-scoped constraints retain missing datasets as unverified.
Approved `WORKLOAD` declarations use `value: {"required_dataset_ids": ["id"]}`
and populate mandatory dataset coverage. They do not establish production
frequencies. Approved contract inputs and expected outputs cannot be changed by
benchmark candidates, and required contract checks cannot be omitted.

Unknown production latency, peak-memory budgets and workload characteristics stay
unknown. They make overall suitability conditional without fabricating failures
or preventing valid measurements. Phase 1 ranking formulas remain unchanged.
Legacy aggregate recommendation output cannot bypass the deterministic decision
when discovered requirements are present. Phase 3 still controls replacement
compatibility independently.

The API bounds a project resolution to 32 source revisions, 32 declarations per
source, explicit context references and the existing 64 policy constraints.
Oversized policies are rejected rather than silently truncated. There is no model
training, RAG, autonomous task linking, requirement approval by Ollama, behavioral
proof, automatic equivalence declaration or automatic benchmark orchestration.
Reports are limited to 2 MB; the enclosing MongoDB document budget is checked
before insertion. Manual sorting memory limits and optimization objectives are
preserved when automatic policy preparation is used.

## Verification

Run `tests/test_requirement_discovery.py` and
`tests/test_requirement_discovery_api.py`, alongside the existing analyzer,
contract, compatibility and deterministic-decision suites. Frontend coverage is
in `src/tests/requirementDiscovery.test.jsx`. Live Docker regressions reuse the
Phase 1/3 tests; no new worker protocol or worker dependency is introduced.
