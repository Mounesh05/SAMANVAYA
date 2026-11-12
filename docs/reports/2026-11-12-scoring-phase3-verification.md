# Scoring Phase 3 verification

Date: 2026-11-12. Branch: `testing`. Base: `28de5f935d41ae12c3e055e29d17c8ab1603e9cc`.

## Result

Implemented advisory period claims, predicate-level validation, protected signed
storage and independent qualified claim-review revisions. See the
[implementation notes](../../backend/intelligence/PERFORMANCE_CLAIMS.md) and
[plan](../superpowers/plans/2026-11-12-scoring-phase3.md).

The period agent no longer accepts numerical model scores. Its active prompt and
schema use the canonical dimension registry. Correct citations with false
predicates are rejected; matching predicates produce only narrow non-scoring facts.
Model narrative is never promoted to a validated engineering score.

New period numerical creation is explicitly gated: `/evaluate` and `/evaluate/bulk`
return HTTP 409 `POLICY_PENDING`, with a frontend-compatible string error detail.
The programmatic numerical service method is also retired. New advisory runs do
not write employee performance rows. Historical records, existing legacy feedback
calculations and PR-level 0–10 evidence remain readable/operational.

The new scoped interpretation, reviewer-assignment and review APIs store versioned,
server-HMAC-sealed artifacts in existing `ai_runs`. Dedicated current-account and
project/org/subject checks protect them; generic AI-run access excludes these types.
Qualification requires explicit technical-admin attestation, supporting project
artifacts and expiry. Subject/proposer/issuer self-review is denied. Reviews append
immutable revisions, recheck positive-review source freshness, and expose effective
decisions without destroying prior proposals or review history.

## Executed validation

| Check | Actual result |
|---|---|
| New Phase 3 tests | 47 passed, 4 warnings |
| Full backend suite, including new tests and Phases 1/2 regressions | 2,632 passed, 111 skipped, 65 warnings; 63.73 seconds |
| Explicit Phase 0 probes | 14 passed, 5 skipped, 24 warnings; 38.58 seconds |
| Frontend tests | 157 passed in 20 files with two workers and a 30-second command-line test budget; 44.71 seconds |
| Frontend production build | Passed |
| Changed/new Python slice, Ruff F/E9 | Passed |
| Repository runtime-name/syntax checks, Ruff F821/E9 | Passed |
| Editor diagnostics for edited runtime Python files | No errors reported |
| Git whitespace check | Passed |

The 111 full-suite skips are not passing evidence. Existing opt-in Mongo integration
tests were enabled with owned temporary collections. The new claim/HMAC/CAS tests
use isolated in-memory Mongo fixtures, including a barrier forcing concurrent
reviewers to read the same predecessor. No real employee records or live model
responses were used. Docker opt-in tests were disabled; no live worker validation
is claimed. Mypy was unavailable; full repository style-lint debt remains outside
this phase.

Frontend files/configuration are unchanged. The 30-second runtime budget is the
documented Phase 2 workaround for an existing default 10-second QA form timeout;
this run does not claim that the original timeout was fixed.

The five skipped characterization probes asserted obsolete numerical-parser,
model-grade-publication or outage-blocking behavior. They are explicitly marked
retired and replaced by desired-behavior tests in the new Phase 3 test modules.
Remaining legacy defects are still characterized by the other 14 probes. The
historical Phase 0 audit and contract snapshot were not rewritten.

Negative tests were observed failing before fixes for authority fields, malformed
output, false predicates, missing/mis-scoped citations, inconsistent run/test
status, model outage/time bounds, incomplete provenance, forged assignments,
review conflicts, changed sources and the existing frontend error-body contract.

## Reproduction

From `backend/` with the configured Python 3.12 environment:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_performance_claims.py tests/test_performance_claim_service.py -q --tb=short -p no:cacheprovider
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m pytest tests/audits/scoring_architecture_phase0.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check --select F821,E9 .
```

From `frontend/`: `npm test -- --run --maxWorkers=2 --testTimeout=30000` and
`npm run build`.

## Scope and remaining work

- Phases 4–6 remain: human aggregation/CEO policy, final approval/history/migration,
  role calibration and release sign-off. Canonical E/H/S and measurement eligibility
  remain unavailable; no weights or grade bands were invented.
- Specialized benchmark-comparability and defect-to-fix validators are not supplied
  by this generic claim validator. Those proposals remain under review; a reviewer
  flag cannot bypass the missing validation.
- Local snapshot facts are not live external-source attestations or proof of work
  quality. Qualification assignments record an authorized human attestation, not
  automatic competence inferred from title or artifact existence.
- HMAC sealing uses the current application secret. Key retention/migration is
  required on rotation before production historical-assessment activation.
- Signed claim reviews do not implement final employee assessment approval or
  guarantee fair employment outcomes. Existing legacy scoring-specific defects
  remain in their owning later-phase scope.
- Model artifact version is unknown; live Ollama inference was not exercised.
  Source, prompt/output hashes, parser/validator version and uncertainty remain
  explicit rather than fabricated.

New modules:
[contracts](../../backend/domain/models/performance_claims.py),
[validators](../../backend/intelligence/performance_claims.py),
[service](../../backend/domain/services/performance_claim_service.py),
[predicate/agent tests](../../backend/tests/test_performance_claims.py),
[service/API tests](../../backend/tests/test_performance_claim_service.py).

Existing integration changed:
[period agent](../../backend/agents/performance_agent.py),
[performance service](../../backend/domain/services/performance_service.py),
[API](../../backend/api/routes/performance.py),
[AI-run repository](../../backend/repositories/ai_run_repository.py), and explicit
characterization-probe retirement markers.

All prior phase work and unrelated user files were preserved. No packages,
credentials, stored historical assessments, frontend code, Git commits or remote
branches were changed. Source changes remain uncommitted.
