# Scoring Phase 4 verification

Date: 2026-11-12. Branch: `testing`. Base:
`fff79b0a0d7fc239c7d1c601dcecefa24bd01156` (Phases 0–3 checkpoint,
committed and pushed before Phase 4 work).

## Result

Implemented the Phase 4 human-feedback mechanics and conservative production
gates. See the [implementation notes](../../backend/intelligence/PERFORMANCE_HUMAN.md)
and [plan](../superpowers/plans/2026-11-12-scoring-phase4.md).

Ordinary and HR composition now delegate to one policy/eligibility-driven human
aggregator and the existing canonical 90/10 math. Synthetic approved fixtures
demonstrate E=86, H=80, S=85.40 through both entry points. Intermediate H is not
rounded. Explicit four-point and five-point anchors are supported, without
automatically migrating either legacy scale. Exact weight checks also reject
over-one sums that the default Decimal precision would round to one.

Missing reviewers, dimensions, observation, eligibility, independently validated
evidence or engineering measurements prevent completion. N/O, N/A and under-review
states retain reasons and null ratings; no automatic denominator change occurs.
CEO has zero routine numerical contribution and cannot occupy a reviewer role.
HR observations are restricted to workplace dimensions; technical dimensions
cannot be rescored through contextual feedback.

New current-account/project/org/period checks protect signed reviewer assignments,
private observation intake, inactive policy proposals and redacted completeness
responses in existing `ai_runs`. Requesters cannot provide approval, validation,
evaluator identity or engineering/final-score fields in a review body. Subject,
issuer and reviewer conflicts are rejected. Identity/authority changes and expiry
are checked on use. Identical assignment/review retries return existing receipts;
different requests conflict without overwriting history. Natural Mongo primary
keys prevent same-role duplicate influence and concurrent duplicate records.

Legacy numerical feedback, mutable HR drafts/submissions and policy activation
return explicit 409 responses. Their programmatic methods are retired as well.
They cannot initialize fake engineering scores/grades, fill N/O with threes,
double-weight old AI contributions, reuse prior composite scores, or mutate
historical assessments. Existing reads retain historical values. Policy reads
do not seed unapproved weights or fabricate policy history.

## Executed verification

| Check | Actual result |
|---|---|
| New Phase 4 contracts/intake plus Phase 3 claims regressions | 91 passed, 4 warnings; 4.65 seconds |
| Full backend suite after the independent-review fix | 2,678 passed, 111 skipped, 59 warnings; 42.74 seconds |
| Explicit Phase 0 audit probes/replacements | 14 passed, 5 skipped |
| Frontend regression tests | 157 passed in 20 files; 21.56 seconds |
| Frontend production build | Passed |
| Changed Python slice, Ruff F/E9 | Passed |
| Repository runtime-name/syntax checks, Ruff F821/E9 | Passed |
| Editor diagnostics on new/changed runtime slice | No errors reported |
| Git whitespace check | Passed |

Tests first reproduced missing contracts/intake, unsafe legacy paths, false
subset completeness, comment-length-as-proof, Decimal weight rounding, fake
policy history and non-idempotent assignment recovery. Desired-behavior tests
then passed. An independent read-only review identified the assignment-retry
recovery issue; new sequential/concurrent/conflicting-request regressions
reproduced it before the fix. The reviewer rechecked that fix with no remaining
finding in that block.

The 111 full-suite skips and five retired Phase 3 characterization probes are
not passing evidence. Existing Mongo opt-in tests were enabled with owned
temporary collections; the new HMAC/eligibility/idempotency tests use isolated
in-memory Mongo fixtures. No real employee assessment was changed. Docker
benchmark opt-in tests were disabled. No live worker, Ollama, deployment or
production policy activation is certified here.

Frontend source/configuration is unchanged. Tests used the documented two-worker,
30-second command-line budget from previous phases, not the original default
10-second budget. This does not claim the earlier QA form timeout was fixed.
Mypy remains unavailable; full repository style-lint debt is outside this phase.

## Reproduction

From `backend/` using the configured Python 3.12 environment:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_performance_human.py tests/test_performance_human_service.py tests/test_performance_claims.py tests/test_performance_claim_service.py -q --tb=short -p no:cacheprovider
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m pytest tests/audits/scoring_architecture_phase0.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check --select F821,E9 .
```

From `frontend/`: `npm test -- --run --maxWorkers=2 --testTimeout=30000`,
then `npm run build`.

## Deliberate limits and next phase

No production approved human policy, validated E adapter or independently
validated workplace-source adapter exists yet. Observation intake is explicitly
`RECORDED_UNVERIFIED`, and production completeness remains `POLICY_PENDING` with
H/S null. The pure engine's synthetic approved inputs are tests of mechanics,
not employee-rating calibration or policy approval. Actual source references
and direct-observation/conflict attestations do not independently prove behavior.

Phases 5–6 remain: approval/revision/appeal and policy governance, historical read
migration/redaction, assignment substitution and waiver rules, key retention on
secret rotation, role calibration and release verification. In particular, the
previously audited cross-org legacy outcome/HR-read authorization gap remains
outstanding for Phase 5; new scoped human APIs do not fix old historical read
routes implicitly. No claim of all-phases completion or production rollout
readiness is made.

Unrelated untracked user files were preserved. No packages, credentials or live
historical employee records were modified.
