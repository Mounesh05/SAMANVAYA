# Scoring Phase 3: advisory claims and verification

Spec: supplied scoring architecture, Phase 3 and section 7. Preserve all uncommitted
Phase 1/2 work and unrelated files. No commit/push, measurement calibration, human
score consolidation, final assessment approval, historical rewrite or UI redesign.

1. Strict bounded proposals cite exact Phase 2 snapshot records/revisions. One
   canonical registry supplies dimensions and relevant source kinds. Deterministic
   validators check typed predicates; citation existence alone cannot validate prose.
2. Convert the period agent to advisory output only, with bounded prompt/output and
   execution time. Model failure returns unavailable/invalid advisory state while
   preserving deterministic evidence. No model score/weight/approval fields accepted.
3. Store signed snapshots, proposals and decisions in existing `ai_runs`, separated
   from employee scores. Hide these protected artifacts from generic AI-run routes.
   Add current-account/org/project-scoped interpretation and retrieval endpoints.
4. Qualified claim review uses explicit, server-signed technical-admin assignments
   with qualification evidence and expiry; role alone grants no validation authority.
   Independent reviews append signed, revision-linked records. Rejection never
   destroys the proposal. Positive review emits an attested typed fact, not points.
5. Retire the unsafe numerical period-evaluation entry point with explicit 409
   pending-policy responses; keep historical reads and PR-level 0–10 workflows.
   New canonical scoring awaits Phases 4–6 rather than inventing numbers or zeros.
6. Verify adversarial claims, unavailable Ollama, review forgery/conflicts, generic
   route privacy, existing regressions and the frontend build. Record exact results.

Baseline: `testing` at `28de5f93`, Phase 2 changes uncommitted; 2,585 backend tests
passed/111 skipped. No approved measurement/calibration policy exists.

## Execution results

- Initial predicate/agent suite: 29 cases observed RED, then GREEN. Canonical
  proposal parsing rejects authority fields and never constructs numeric scores.
- Initial service suite: 11 cases observed RED, then GREEN. Added adversarial
  cases and forced predecessor-read concurrency; final new slice is 47 passing.
- Reproduced and repaired false passing-execution inference from failed runs with
  zero failed cases, missing completed-output provenance, stale-source positive
  review and an error-body shape incompatible with the existing frontend handler.
- Full backend: 2,632 passed/111 skipped; new slice 47 passed. Explicit probes:
  14 passed/5 obsolete numeric probes retired with replacement regression tests.
- Frontend: 157 passed with the documented two-worker/30-second test budget;
  production build passed. No frontend source/configuration changes.
- Runtime-name/syntax lint, changed-slice F/E9, editor diagnostics and whitespace
  checks pass. No live model or Docker validation claimed.
- No numerical policy activation, historical rewrite, commit or push. See
  [verification](../../reports/2026-11-12-scoring-phase3-verification.md) for limits.
