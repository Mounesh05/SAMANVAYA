# Scoring Phase 2 verification

Date: 2026-11-12. Branch: `testing`. Base: `28de5f935d41ae12c3e055e29d17c8ab1603e9cc`.

## Delivered

Implemented the canonical evidence inspection path described in the
[implementation notes](../../backend/intelligence/PERFORMANCE_EVIDENCE.md) and
[plan](../superpowers/plans/2026-11-12-scoring-phase2.md), on top of the uncommitted
Phase 1 foundation. Existing employee scores and stored history are preserved.

The new read-only `POST /api/performance/evidence/preview` endpoint uses current
account, organization, project and subject checks. It returns allowlisted facts,
attribution limitations, source availability, per-dimension references and a frozen
snapshot/digest. It uses existing local collections and does not invoke Ollama,
execute code, fetch external sources or create database records.

Evidence anomalies fail safely: duplicate observations collapse; contradictory
revisions remain disputed; missing/invalid dates, deleted sources and wrong scope
are rejected; revision/head mismatches are stale; missing identity mapping and
unknown shared contribution remain unverified. Snapshot restoration validates
checksums/references/status and rejects fabricated coverage. QA's actual `FIXED`
state remains an observation requiring retest, not a proven regression repair.

## Phase status

| Phase | State |
|---|---|
| 0 — Audit/baseline | Completed; known legacy defects documented |
| 1 — Canonical contracts | Foundation implemented/tested; broad legacy agent alignment remains pending |
| 2 — Evidence validation | Canonical inspection/validation path implemented; calibrated numeric rules remain unavailable |
| 3 — AI claims/verification | Not implemented by this change |
| 4 — Human scoring/orchestration | Not implemented by this change |
| 5 — Approval/history/migration | Not implemented by this change |
| 6 — Calibration/release | Requires representative evidence and policy sign-off |

No approved employee measurement rules, coverage thresholds or historical role/
opportunity records were supplied. The production rule registry is empty and
immutable. Counts remain observations, every dimension remains `NOT_ASSESSED`,
and weighted coverage/E/H/S stay null. No new official rating or grade is activated.

## Validation

| Check | Result |
|---|---|
| New evidence cases | 43 passed |
| New evidence cases plus Phase 0 probes, after preserving legacy construction | 62 passed, 27 warnings |
| Final full backend suite | 2,585 passed, 111 skipped, 65 warnings; 113.85 seconds |
| Frontend production build | Passed |
| Frontend at original 10-second test timeout | 156 passed, one QA form test timed out in isolated two-worker runs |
| Frontend with an explicit 30-second runtime budget | 157 passed in 20 files; 34.23 seconds |
| New Python modules/tests, Ruff F/E9 | Passed |
| Repository runtime-name/syntax lint, Ruff F821/E9 | Passed |
| Editor diagnostics for edited Python files | No errors reported |
| Git whitespace check | Passed |

The full backend suite uses the Phase 0 isolation runner, with existing opt-in
Mongo tests enabled and Docker tests disabled. Skipped cases are not passing
evidence. No new live worker/container validation is claimed. Mypy was unavailable;
existing full-style-lint debt was not repaired.

An intermediate lazy-initialization change moved model construction inside an
existing two-second concurrent-feedback probe and caused a reproducible timeout.
The original constructor behavior was restored. The new preview is now a stateless
service operation that avoids constructing the scoring agent. The original race
probe passes again and still characterizes the pre-existing lost-update defect.

Frontend files are unchanged. Concurrent checks initially had multiple timing
failures; isolated two-worker runs consistently reduced this to a QA form typing
test exceeding its existing 10-second budget. No frontend source, mocks or timeout
configuration were edited to hide that result. All 157 cases passed when rerun
with `--testTimeout=30000`; this is conditional passing evidence, not a claim that
the original 10-second timeout failure was repaired.

## Reproduction

From `backend/`, using the configured Python 3.12 environment:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_performance_evidence.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest tests/test_performance_evidence.py tests/audits/scoring_architecture_phase0.py -q --tb=short -p no:cacheprovider
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m ruff check --select F821,E9 .
```

From `frontend/`:

```powershell
npm test -- --run --maxWorkers=2
npm test -- --run --maxWorkers=2 --testTimeout=30000
npm run build
```

## Files and limits

New contracts and helpers:
[performance_evidence.py](../../backend/domain/models/performance_evidence.py),
[validation](../../backend/intelligence/performance_evidence.py),
[local adapters](../../backend/intelligence/performance_evidence_collection.py),
[tests](../../backend/tests/test_performance_evidence.py).

Existing integration extended:
[collector](../../backend/intelligence/developer_data_aggregator.py),
[manifest](../../backend/domain/services/period_evidence.py),
[service](../../backend/domain/services/performance_service.py),
[API](../../backend/api/routes/performance.py),
[evidence kinds](../../backend/domain/models/performance_scoring.py),
[catalog](../../backend/intelligence/performance_registry.py).

- Local capture is bounded and not an atomic, live external-source attestation.
  Queries exceeding 200 records report `PARTIAL`; missing adapters/configuration
  and failed reads are not interpreted as no employee activity.
- No durable attributable commit/review/incident period adapter was added; these
  sources remain explicitly unavailable in this path.
- Current stored identity/membership enables scoped inspection, not a verified
  historical role, exclusive ownership, contribution allocation or work quality.
- Benchmarks and analyzer findings remain unverified for performance measurement
  until their contract, correctness, baseline, exemption and attribution checks
  have approved measurement rules.
- Snapshot digests provide integrity against an expected reference; they are not
  signatures granting authority. Persistence and approval are later-phase work.
- Existing legacy numeric scoring and its Phase 0 defects remain labeled legacy;
  the new path does not silently rewrite or activate those calculations.

All changes remain uncommitted; unrelated user files were preserved. No package
installation, schema backfill, UI redesign, commit or push was performed.
