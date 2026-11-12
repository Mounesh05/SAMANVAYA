# Scoring Phase 3: advisory interpretation and claim verification

The period agent produces bounded structured proposals, never employee points.
The canonical Phase 1 registry supplies dimension IDs and relevant source kinds;
the Phase 2 snapshot supplies exact source/content digests. No new platform,
model training, external integration or scoring policy is introduced.

## APIs

| Operation | Behavior |
|---|---|
| `POST /api/performance/interpretations` | Accepts the Phase 2 employee/project/aware-period request; collects authorized evidence, invokes Ollama if possible and stores an immutable interpretation run |
| `GET /api/performance/interpretations/{run_id}` | Returns the original run, signed review revisions and effective decisions under current account/project/org access |
| `POST /api/performance/claim-reviewers` | A current Lead/PM technical administrator explicitly attests an independent reviewer's qualifications for named dimensions/claim types and an expiry |
| `POST /api/performance/interpretations/{run_id}/claims/{claim_id}/reviews` | An independently assigned qualified reviewer appends a validation/rejection revision bound to exact snapshot/proposal/history digests |

The retired numerical `/evaluate` and `/evaluate/bulk` endpoints retain their
request shapes and return HTTP 409 with a string `detail`, top-level
`status="POLICY_PENDING"` and the interpretation endpoint. They do not create
employee ratings or fake zeros. The string error detail remains compatible with
the existing frontend handler. Historical reads, historical feedback semantics
and the separate PR-level 0–10 evaluation remain unchanged.

## What validation means

Supported proposals are recorded status, recorded test outcome, possible
regression fix, possible benchmark improvement, possible architecture tradeoff,
possible mentoring contribution and possible substantive review. This catalog
describes claim predicates, not an algorithm whitelist or approved job rubric.

- Every citation must match an exact in-snapshot source/content digest. Every
  source must be relevant to both the canonical dimension and the claim type.
- Stale, disputed, rejected, missing or contradictory evidence cannot validate a
  claim. Incomplete attribution remains under review.
- Deterministic validators check the actual recorded status or test outcome and
  counts. A failed run with zero reported failed cases is not declared a passing
  execution. Skipped cases remain separate from executed tests.
- Only the narrow typed predicate becomes a validated fact. Model prose remains
  unverified advisory content even when that predicate matches the snapshot.
- Benchmark improvements and defect-to-fix claims require specialized correctness,
  comparability and causal-link validators. Those are not invented from a citation,
  a successful benchmark status, a disappeared scanner warning or a reviewer flag.
- Qualitative interpretations require an independent qualified review. Current
  role/title alone is insufficient; a signed explicit qualification assignment is
  required. Qualification references must resolve to existing project artifacts.
  Their existence is not automatic proof of competence: the issuing technical
  administrator records an explicit human attestation and justification.

No fact grants points. `score_effect` is null, `is_performance_credit` is false,
`facts_for_measurement` is empty, and canonical E/H/S remain null. Approved
measurement rules and final-assessment prerequisites belong to later phases.

## Review and storage boundaries

Snapshots, proposals, validator decisions, qualification assignments and review
revisions use the existing `ai_runs` collection. Protected performance artifact
types are excluded from generic AI-run retrieval/list/history helpers. Access
uses the dedicated service's current-account/org/project/subject checks, including
a permission recheck after model execution.

Artifacts are versioned and HMAC-SHA256 sealed by the server using the existing
application secret. This authenticates the server's record of an authenticated
review action; it is not a personal public-key signature or an independent
competency certification. Copying client approval fields or changing a stored
payload/signature does not establish review authority.

Reviewer, subject, proposer and assignment issuer conflict checks apply. The
assignment's issuer must still be an active technical administrator; assignments
expire. Positive review rechecks that cited local sources still exist unchanged.
Contradicted predicates cannot be overridden, and the generic review path cannot
approve benchmark/regression claims needing specialized validators.

Reviews append revisions with a predecessor digest. A unique Mongo primary key
per run/claim/revision rejects concurrent writers. Rejection preserves the original
proposal and prior reviews; retrieval applies the latest review to effective
decisions. This is claim review history, not final assessment approval or appeal
governance. Phase 5 still owns those broader workflows.

The HMAC key must be retained or migrated deliberately when rotating the
application secret. Old documents remain stored, but verification fails closed
under a different key. Key-retention/rotation migration is required before a
production immutable-assessment rollout; this phase does not claim that lifecycle.

## Resource bounds and failure behavior

The model receives only the Phase 2 typed allowlist, without employee names,
emails, source prose/code, HR records or qualification/review comments. Source
contents remain untrusted data. The prompt schema forbids score, weight, grade,
authorization and approval fields.

Bounds: 16 claims, eight citations per claim, 2,000 characters per interpretation,
64 KB prompt/output budgets, 2,048 predicted tokens and a 20-second model call.
Duplicate JSON keys, nonfinite values, fenced/non-JSON responses and unknown
authority fields fail validation. Model/provider failure or resource limits
produce an unavailable/invalid advisory state with the deterministic snapshot
preserved. Invalid raw output is not stored as executable or trusted content;
its digest is retained when available.

Model ID, unknown artifact version, prompt version/hash, output hash and validator
method are explicit. Live Ollama behavior is not certified by mocked tests. No
stored narrative or model confidence can change a numerical assessment.
