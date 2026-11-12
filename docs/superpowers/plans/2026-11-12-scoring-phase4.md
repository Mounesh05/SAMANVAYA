# Human feedback and canonical composition implementation plan

**Goal:** One policy-driven human aggregator for ordinary and HR reviews, with
CEO routine numerical contribution fixed at zero and incomplete reviews blocked.

**Architecture:** Reuse frozen scoring contracts, canonical Decimal composition,
current-account scope checks and signed artifacts in existing `ai_runs`. Keep
historical records readable. Retire unsafe legacy numeric write paths rather
than implicitly migrating their unapproved weights or rating scales.

**Spec:** User-supplied scoring architecture implementation specification,
sections 8, 10, 14 (Phase 4), 15. The user authorized continuing implementation.
Execution stays in the existing checkout and preserves unrelated untracked files.

## Constraints

- E/H/S use 0–100; S is rounded once after 0.90E + 0.10H.
- No model scores, legacy 0–90 double weighting, fabricated neutral ratings,
  CEO scoring, available-reviewer reweighting, or automatic policy approval.
- Reviewer identity comes from current accounts and a signed exact-period
  assignment. No self-review, same-role duplicate influence, cross-org ratings,
  technical HR dimensions or requester-selected evaluator identity.
- Observed ratings require a direct-observation attestation and traceable source
  references. References/attestations are not independently verified facts.
- Missing approved anchors, mandatory roles, waivers, evidence validation or
  engineering measurements keep canonical scores incomplete. Activation,
  appeals, reassignment and calibration remain in Phases 5–6.

## Tasks

- [x] Write failing tests for policy validation, role/dimension eligibility,
  observation states, missing reviews, CEO exclusion, exact shared math and
  retirement of legacy writes.
- [x] Add `performance_human` contracts and a pure aggregator. Require all
  explicitly weighted roles/dimensions, exact sum-to-one weights, approved
  anchors and eligible evidence; do not round intermediate H.
- [x] Extract the existing signed artifact storage helper without changing its
  format; protect human assignments/reviews from generic AI-run access.
- [x] Add scoped assignment/review intake and a redacted completeness API. Store
  immutable, idempotent reviews; recheck eligibility on every use. Expose no
  production activation or caller-supplied E/policy-approval/validation flags.
- [x] Route ordinary and HR orchestration through the same engine. Disable
  legacy numeric feedback/submission/policy activation with explicit 409 errors;
  preserve historical reads and make policy reads side-effect-free.
- [x] Replace obsolete defect-characterization assertions with desired-behavior
  regressions, run focused and full backend checks and frontend regressions,
  review the diff, and record actual results and limitations.

## Review focus

Forged approval, current-role revocation, HR raw-evidence exposure, incomplete
denominators, duplicate role slots, idempotent retry, and tampered signed records
must be exercised explicitly. No production calibration values are supplied by
this phase; synthetic approved fixtures test arithmetic only.
