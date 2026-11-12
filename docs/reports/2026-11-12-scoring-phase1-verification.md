# Scoring Phase 1 verification

Date: 2026-11-12. Branch: `testing`. Base: `28de5f935d41ae12c3e055e29d17c8ab1603e9cc`.

## Result and scope

Implemented the additive canonical scoring foundation described in the
[implementation notes](../../backend/intelligence/PERFORMANCE_SCORING.md) and
[execution plan](../superpowers/plans/2026-11-12-scoring-phase1.md).

The foundation provides strict score units, one canonical dimension catalog,
nullable scores/coverage, pending role profiles, UTC identity/revision contracts,
frozen replayable snapshots and deterministic 90/10 arithmetic. Existing API
serializers attach conservative legacy metadata without changing historical
numbers or writing a backfill. No new employee scoring policy is activated.

The new canonical schema, catalog and generated advisory contract metadata agree.
Actual legacy agent/model/prompt alignment remains deferred to the evidence and
advisory-claim migration. Therefore this report does not claim that the broad
cross-agent alignment exit criterion or the entire scoring redesign is complete.
The [Phase 0 defects](2026-11-12-scoring-phase0-audit.md), including legacy
arithmetic and scoring-specific authorization gaps, remain known limitations.

## Executed verification

| Check | Result |
|---|---|
| New contract and compatibility tests | 74 passed, 28 warnings |
| Full backend suite, including those 74 cases | 2,542 passed, 111 skipped, 65 warnings; 40.85 seconds |
| Phase 0 characterization probes | 19 passed, 27 warnings; reproduce existing defects, not fixes |
| Frontend tests | 157 passed in 20 files |
| Frontend production build | Passed |
| Frontend lint | Exit 0, 16 existing warnings |
| New Python sources/tests, Ruff F/E9 | Passed |
| Repository runtime-name/syntax checks, Ruff F821/E9 | Passed |
| Editor diagnostics for edited Python files | No errors reported |
| Git whitespace check | Passed |

The backend suite used the Phase 0 runner, which isolates cached audit writes and
shortens oversized reporting IDs for Windows. Existing opt-in MongoDB tests were
enabled; owned temporary collections are cleaned by their tests. Docker opt-in
tests remained disabled because the Linux engine was stopped. Skips are not
passing evidence. Mypy was unavailable; full default Ruff debt was not repaired.

Initial sandbox execution encountered Windows access-denied errors in temporary
files and parser subprocesses. Vite also failed to spawn a helper. Those runs
were not counted as passing evidence. The full backend suite and frontend
tests/build subsequently passed outside the sandbox, without changing source to
hide environmental failures.

Reproduce from `backend/` using the configured Python 3.12 environment:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_performance_scoring_contracts.py tests/test_performance_scoring_compatibility.py -q --tb=short -p no:cacheprovider
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m pytest tests/audits/scoring_architecture_phase0.py -q -s --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check --select F821,E9 .
```

From `frontend/`: `npm test -- --run`, `npm run build`, `npm run lint`.

## Independent review and remediation

One fresh, read-only reviewer identified one Important finding: direct or JSON
`ScoreCalculation` construction accepted wrong units and inconsistent results,
which could then be digested in a snapshot. Thirteen negative cases were run and
failed before the fix. Shared exact arithmetic now validates field-specific
units, required contributions, result/formula agreement and completeness at the
model boundary as well as the calculator boundary. All 74 focused cases and the
full backend suite passed after the fix. No Critical or Minor findings were raised.

## Decisions and their limits

- Reused the supplied detailed design and explicit Phase 1 instruction rather
  than repeating design approval. Cost if wrong: a design preference must be
  revised in a later patch; no external publication occurred.
- Kept the current checkout to preserve Phase 0 artifacts and unrelated user
  work. Cost: the patch shares the working tree and must be staged selectively.
- Implemented inline with one final independent review; no commit/push or
  worktree cleanup. Cost: integration and durable Git history remain pending.
- Used the execution plan as the ledger rather than POSIX orchestration scripts.
  Cost: progress bookkeeping is manual and retained with the plan.
- Rejected snapshot numbers that cannot round-trip through JSON without loss.
  Cost: some high-precision arithmetic inputs cannot be persisted as snapshots.
- Preserved exact legacy conversion origins instead of returning a lossy plain
  score. Cost: conversion consumers must use the typed origin-bearing value.
- Kept legacy numerical execution separate from the canonical foundation.
  Cost: existing legacy agent/model/prompt drift and other Phase 0 defects remain;
  canonical contracts must not be described as a repaired production scorer.
- Deferred actual evidence validity, attribution and source existence to Phase 2.
  Cost: structural references alone cannot establish an eligible assessment.
- Deferred approval authorization, revision concurrency and historical restatement
  to their owning migration phases. Cost: the transition table is adjacency only,
  and snapshots are contracts rather than a persisted approval workflow.
- Left rubric weights, coverage thresholds and grade bands unapproved. Cost:
  canonical employee outcomes remain unavailable until calibration and approval.
- The independent review was bounded; full regression verification was performed
  separately by the implementer. Cost: the full regression run is not an
  independently reproduced review result.

All source changes remain uncommitted. No database migration, package installation,
UI redesign or external publication was performed.
