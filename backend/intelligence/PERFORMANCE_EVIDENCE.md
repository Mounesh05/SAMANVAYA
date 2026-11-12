# Scoring Phase 2: evidence inspection

Phase 2 adds a deterministic evidence path to the existing performance architecture.
It collects observations and explains eligibility limits. It does not activate a
new employee rating policy or replace legacy historical calculations.

## Entry point

`POST /api/performance/evidence/preview` accepts only:

```json
{
  "employee_id": "EMP-1",
  "project_id": "PROJECT-1",
  "period_start": "2026-07-01T00:00:00Z",
  "period_end": "2026-10-01T00:00:00Z"
}
```

The existing [performance service](../domain/services/performance_service.py)
reloads the actor from MongoDB and checks active account status, engineering
permission, matching organization, project membership and subject scope. Ordinary
contributors inspect their own evidence. Assigned Lead/PM accounts may inspect
subjects in the same authorized project. HR/CEO roles and stale token admin/role
claims do not grant raw engineering-evidence access. Missing historical project
membership is not reconstructed from a current role or token.

The result contains a frozen snapshot and SHA-256 digest. This operation performs
no storage writes, external requests, code execution or Ollama initialization.
Snapshot persistence, approval and revision concurrency remain Phase 5 work.

## Collection and provenance

The existing [developer collector](developer_data_aggregator.py) and
[period manifest module](../domain/services/period_evidence.py) expose the new path.
[Local adapters](performance_evidence_collection.py) read existing collections:

| Source | Attribution and limitations |
|---|---|
| Tasks/stories | Exact project and assignee; completion/update timestamps; assignment does not establish exclusive contribution |
| QA defects | Exact project and assignee; preserve native QA status; `FIXED` is not proof of a validated regression repair |
| Synced PRs | Exact configured repository and stored GitHub login mapping; head SHA and merge/create time; no email/name guessing |
| CI test runs | Matching project/repository configuration and an attributable PR link; preserve passed/failed/skipped counts |
| Code-quality runs | Exact project and attributable PR revision; findings still require baseline, ownership and exemption review |
| Benchmark runs | Explicit PR automation/revision link; contract, correctness, workload and environment still require review |

Trigger identity is never treated as ownership of code or test outcomes. Project
membership alone does not attribute project runs to an individual. Cross-org rows,
unrelated authors and unrelated runs are excluded before response construction.
Legacy documents without an org field can inherit scope only through the exact
authorized parent project, and record that basis explicitly.

The current period path has no durable attributable commit/review/incident adapter.
Those sources are reported as `NOT_CONFIGURED`; this does not assert that the
entire application lacks those integrations. Missing repository/account mapping,
failed reads, empty observed collections and truncated reads remain distinguishable.
Each local query is bounded to 200 records; truncation means `PARTIAL`, never full
coverage. No exception details, descriptions, diffs, logs or medical/HR prose are
copied into the snapshot. Only typed allowlisted facts are retained.

## Validation and interpretation

[Contracts](../domain/models/performance_evidence.py) and
[validation](performance_evidence.py) enforce:

- Aware UTC half-open periods `[start, end)`; missing, invalid, future and
  out-of-period observations cannot become verified facts.
- Stable source identities derived from organization/project/repository/kind and
  native ID, content digests, source revisions and capture time. Identical repeats
  collapse. Contradictory observations remain visible and under review.
- Local PR-head mismatches become stale; deleted/disputed sources remain flagged.
  Snapshot comparison reports changed, missing, added and unchanged observations
  without rewriting the earlier snapshot.
- Missing identity mapping or uncertain shared contribution remains unverified.
  No contribution share is inferred or assigned. Stored account mapping is not
  independent proof of GitHub account ownership.
- Test counts are strict native nonnegative integers and must reconcile. Skipped
  tests are retained separately; missing execution is not a passing test.
- Restored snapshots reject inconsistent inner digests, unknown evidence references,
  wrong aggregate status and invented coverage. A digest is an integrity checksum,
  not an authorization signature or proof that an upstream claim is true.

`VERIFIED_SNAPSHOT` means that the recorded local facts passed these structural,
scope, revision, period and attribution checks. It does **not** mean verified work
quality, a correct functional implementation, a valid employment assessment or live
external-source freshness. Collection is a bounded local capture, not an atomic
transaction across all integrations.

## Measurement and coverage

There is no approved calibration for employee measurement or coverage thresholds.
The production measurement-rule registry therefore remains empty and immutable.
Raw counts, changed lines, story points, source authority flags and LLM scores
cannot register a rule or award points. Verified facts are associated with the
Phase 1 catalog's relevant dimensions for inspection; that catalog is not a
calibrated rubric for each job role.

Every dimension remains `NOT_ASSESSED`, with null score and explicit unknown
opportunity context. Role-at-period history is unknown. Weighted engineering
coverage, E/H/S and finalizability remain null/false. More records, inflated story
points or repeated PRs cannot produce a numerical performance benefit.

Phase 3 will consume these safe observations for advisory claims. Later phases
own human aggregation, approvals and calibration. The original count-threshold
manifest and contribution calculators remain explicitly legacy until their
owning migration steps; this preview does not silently repair or activate them.
