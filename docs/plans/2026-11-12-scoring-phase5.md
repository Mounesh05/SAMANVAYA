# Scoring Phase 5 implementation plan

The user authorized implementation of the supplied scoring specification,
sections 9–13 and Phase 5. Reuse signed `ai_runs` and canonical contracts.

- [x] Add immutable lifecycle/appeal/correction requests, explicit transitions,
  expected-predecessor checks, idempotent scoped creation and audit events.
- [x] Add independent scoped approver assignments. Approval requires replayable
  signed measurement/policy evidence; no client-supplied score or approval flag.
  Incomplete Phase 2/4 evidence cannot be promoted by workflow transitions.
- [x] Add inactive policy review governance, explicit effective dates and a
  calibration gate. Phase 6 still owns empirical calibration and release approval.
- [x] Retain signed history across configured key rotation without rewriting it.
- [x] Replace scoring-route read/appeal bypasses with current-account org/project
  checks and allowlisted summaries. Confidential HR detail is case-specific.
- [x] Preserve historical numbers and explicit legacy labels; prevent unsupported
  trend/ranking claims. Add read-only shadow discrepancy reports and audited,
  purpose-scoped redacted exports. Never overwrite old ratings during migration.
- [x] Run failing regressions first, focused/full backend and frontend checks,
  review the scoped boundaries and record actual results/remaining Phase 6 gates.

No new data platform, production rubric weights, grade bands, blanket CEO admin
privilege or numerical activation from unvalidated observations is introduced.
Production policy/measurement adapters may remain unavailable, explicitly gated;
synthetic signed test fixtures demonstrate positive approval/replay mechanics.
