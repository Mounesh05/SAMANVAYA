# Scoring Phase 5 verification

Date: 2026-11-12. Branch: `testing`. Base:
`eaf10b55e2fe6a1bbd4a5cf85706090ee0ba2bd3`.

## Implemented result

Implemented immutable assessment workflow, independent approval checks, subject
appeals, human observation corrections, historical read migration, scoped
redaction/export/shadow inspection, and retained-key signature verification.
See [implementation notes](../../backend/intelligence/PERFORMANCE_LIFECYCLE.md)
and the [plan](../plans/2026-11-12-scoring-phase5.md).

The implementation reuses existing signed `ai_runs`, Phase 2 snapshots, Phase 4
human aggregation and canonical calculation. Every workflow successor records
its predecessor, actor, action, reason and idempotency digest. Revision primary
keys arbitrate concurrent writers; history is appended rather than overwritten.
State changes and their audit metadata are a single insert. Different snapshots
for the same scoped period require explicit correction. An approved historical
calculation can be replayed from its frozen policy/measurement artifacts.

Ordinary requests cannot supply scores, release authority or an approval flag.
Approval requires a current independent assigned technical reviewer and a
trusted exact-snapshot measurement/calibrated-release artifact. Subjects cannot
manage their own assessments after gaining admin access. Reviewers cannot
approve their own numerical contributions or the assessments they initiated.
Changed human observations block stale measurements; measurement artifacts cannot
be substituted midway through review. An appeal stops a score being displayed
as currently approved while retaining the historical approval event.

All existing scoring read routes now reload current accounts and enforce org,
project and subject scope. The audited cross-org legacy read bypass is denied,
including stale admin/CEO claims. HR/CEO historical views are allowlisted and
explicitly legacy; confidential HR cases require case-specific author access.
Cases with neither a linked historical scope nor explicit org provenance are
withheld. Historical numeric values are unchanged, and unverified trend/ranking
claims are removed. Legacy appeals append artifacts without modifying the old
assessment row. Purpose-scoped redacted exports and reads are audited.

Policy review records an independent review and explicit future effective date,
remaining `REVIEWED_INACTIVE`. Existing unscoped policy history is withheld; an
old active flag cannot establish canonical approval. Shadow reports retain null
canonical scores/differences when historical evidence and calibration are absent.

New HMAC envelopes identify retained verification keys. Original v1 artifacts
remain verifiable with explicit legacy-key retention; no historical artifact is
re-signed or backfilled. Missing keys fail closed. No live key or environment
file was read for modification or changed.

## Executed verification

| Check | Actual result |
|---|---|
| Final full backend suite | **2,708 passed, 111 skipped, 78 warnings**; 32.65 seconds |
| Native Mongo revision arbitration | **1 passed**, also included in the final full suite; one UUID collection owned and cleaned up by the test |
| Explicit Phase 0 probes and desired-behavior replacements | **14 passed, 5 skipped**, 16 warnings; 5.68 seconds |
| Frontend existing regression suite | **157 passed in 20 files**; 24.16 seconds |
| Frontend production build | Passed |
| Changed Python slice, Ruff F/E9 | Passed |
| Repository runtime-name/syntax checks, Ruff F821/E9 | Passed |
| Editor diagnostics for the changed runtime boundary | No errors reported |
| Git whitespace check | Passed |

The 111 suite skips and five retired Phase 3 probes are not passing evidence.
Mongo opt-in tests were enabled; Docker benchmark opt-in tests were disabled.
There was no live Docker worker, Ollama, browser workflow or deployment validation.
New unit/service/API tests use isolated in-memory Mongo fixtures, plus the owned
native-Mongo concurrency collection. No real employee assessment was changed.

The new regressions first failed for missing lifecycle/read/key contracts,
cross-org legacy access, missing replay, disputed-score publication, measurement
substitution, absent human correction history, unscoped policy history, admin
self-management and unresolved HR-case provenance. Their implemented behavior
then passed. Concurrent conflicting transitions are forced to read the same
predecessor in unit tests and are also checked against Mongo primary-key behavior.

The first broad regression run exposed nine old route tests depending on mocks
of the previous unscoped read service or missing current-account/project metadata.
They were replaced with scoped in-memory fixtures and assertions that preserve
legitimate historical reads. They were not skipped. Async fixture consumers now
use the repository's AnyIO pattern. Existing backend warnings remain; no claim
of a warning-free suite or whole-repository type/style cleanliness is made.
Pylance MCP tools were unavailable; runtime tests, Ruff and editor diagnostics
supplied the verification. Mypy was not run.

## Reproduction

From `backend/` using the configured Python 3.12 environment:

```powershell
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m pytest tests/test_performance_lifecycle.py tests/test_performance_lifecycle_mongo.py tests/test_performance_access.py tests/test_performance_signing_rotation.py tests/test_performance_human_service.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest tests/audits/scoring_architecture_phase0.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check --select F821,E9 .
```

Frontend: `npm test -- --run --maxWorkers=2 --testTimeout=30000`, then
`npm run build`. The 30-second command-line budget is the previously documented
workaround; this does not claim the old default-timeout issue was fixed.

## Remaining Phase 6 boundaries

- No empirical role calibration, production measurement/release issuer or
  independently validated workplace-source adapter was invented. Existing local
  snapshots and human submissions cannot become approved scores by changing
  workflow status. Positive approval/replay tests use clearly synthetic signed
  adapter fixtures and reproduce their frozen E=86/H=80/S=85.40 calculation.
- The internal adapter contract is a trust boundary, not a public declaration of
  calibration quality. Phase 6 must supply and validate the actual deterministic
  issuer, applicable role/coverage rules and empirical release evidence.
- Frontend source is unchanged. New lifecycle controls and explicit legacy/
  partial/approved presentation still need Phase 6 integration. Existing page
  fallbacks, including the performance page's default displayed confidence, are
  not certified as correct by the passing legacy frontend suite.
- Representative numerical shadow comparisons remain incomplete until valid
  canonical measurements exist. Unknown differences remain null; no historical
  number has been retroactively declared corrected.
- Appeal delegation, waivers, reviewer substitution, retention windows and other
  unresolved organization policy choices remain unavailable rather than invented.
  Key retention settings must be deliberately configured before secret rotation.

The work remains uncommitted. Unrelated user files were preserved. No Git remote,
packages, credentials or production employee records were modified by Phase 5.
