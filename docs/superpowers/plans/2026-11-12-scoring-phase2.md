# Scoring Phase 2 plan

Scope: implement the evidence validation/attribution/coverage phase of the supplied
scoring specification, preserving the uncommitted Phase 1 foundation and unrelated
user files. No commit/push, policy calibration, AI-claim migration, final scoring,
new external integration, historical rewrite or UI redesign.

## Implementation

1. Add frozen normalized evidence/snapshot contracts and deterministic validation:
   scoped identity, UTC half-open periods, revision/digest, attribution uncertainty,
   availability, deduplication, conflicts, head mismatch, safe facts, opportunity
   unknowns and null coverage/scores when calibration is absent.
2. Reuse the existing developer collector and period-manifest module through an
   additive canonical path. Read existing project/task/story/PR/QA/code-quality/
   benchmark collections with bounded projections. Do not infer personal ownership
   from trigger identity or project membership; preserve missing mappings/links.
3. Expose a read-only evidence preview through the existing performance service/API.
   Reload account state and enforce organization, project, subject and engineering
   evidence access before collection. Test actual HTTP paths and no-write behavior.
4. Run focused adversarial tests, Phase 1 regressions, the full isolated backend
   runner, runtime lint and editor diagnostics; document exact results and limits.

## Decisions

- Existing numeric scorers stay explicitly legacy until their owning migration
  phases. Counts in the canonical path are observations, never points or quality.
- No approved measurement rules or coverage thresholds exist. The production
  registry stays empty and non-finalizable; deterministic factual measurements
  (e.g. test outcomes) are retained without manufacturing a performance score.
- Current membership establishes permission to inspect, not historical role or
  contribution. Role/opportunity history remains unknown without approved records.
- Preview returns a frozen self-contained snapshot/digest without storage writes;
  lifecycle persistence/approval remains Phase 5. Source changes can be compared
  against an earlier snapshot without rewriting it.
- No durable exact commit/review/incident snapshots were found in the inspected
  period collector path; report unavailable adapters rather than fabricating them
  or fetching arbitrary external data.

## Progress

- Baseline: `testing` at `28de5f93`, with Phase 1 changes uncommitted. Phase 1 full
  backend: 2,542 passed/111 skipped. Python 3.12.10 selected and configured.
- Initial 32 cases observed RED before implementation. The pure validator's first
  25 cases passed, then collection/service/HTTP cases were integrated.
- Added and reproduced negative cases for model initialization during preview,
  inconsistent PR head facts, foreign-source dedup poisoning, snapshot restoration,
  unavailable optional sources and unrelated CI configuration; repaired each.
- Preserved unknown contribution shares rather than marking current Mongo rows
  exclusively owned. This is an intentional conservative result, not missing data
  converted to a negative employee score.
- Source inspection found QA's actual uppercase state enum. A failing native-shape
  test showed `FIXED` was lost; the adapter now preserves `fixed` as an observation
  requiring retest rather than proof of a validated fix.
- Current implementation: 43 evidence tests pass; Phase 1 focused regressions
  passed alongside the new tests before the final QA shape case. Final full-suite
  verification is in progress; no commits or source/history rewrites performed.
- Regression finding: lazy model initialization changed the two-second legacy
  feedback probe's timing. Restored the original constructor and made the new
  preview stateless. All 43 evidence tests plus 19 characterization probes pass
  together (62 cases); existing legacy defects remain characterized, not repaired.
- Frontend source is unchanged; an existing QA form typing test exceeded its
  10-second budget even in an isolated two-worker run. Report the default failure
  separately from any diagnostic run with a longer command-line runtime budget.
- Final backend suite passed on the final production tree: 2,585 passed,
  111 skipped, 65 warnings (113.85 seconds). Runtime lint/editor diagnostics and
  whitespace checks pass; frontend production build passed.
- Frontend diagnostic run: all 157 tests passed with two workers and an explicit
  30-second command-line test budget (34.23 seconds). Default 10-second failures
  remain reported; no frontend code/configuration was changed.
- Completed this phase's scoped implementation and verification. See
  [verification report](../../reports/2026-11-12-scoring-phase2-verification.md).
  Approved measurement/calibration and Phases 3–6 remain pending. No commit/push.
