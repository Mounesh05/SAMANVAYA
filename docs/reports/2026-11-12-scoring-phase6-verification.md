# Scoring Phase 6 integration verification

Date: 2026-11-12. Branch: `testing`. Base and pushed Phase 5 checkpoint:
`c8544337af8451ae4a46915f399959df877bc4ec`.

**Status: integration implemented and tested; empirical role calibration and
independent policy/release sign-off remain incomplete. Production scoring is
disabled. This is not a completed Phase 6 release certificate.**

## Implemented integration

The existing performance routes, signed artifact store, current-account access
checks and immutable assessment lifecycle are reused. No new scoring platform,
background infrastructure or model authority was introduced.

- Readiness reports all five engineering subject roles: Developer, QA, DevOps,
  Lead and PM. Missing calibration is explicit, with null scores and no
  finalizable result. CEO routine contribution stays zero; HR cannot rescore
  technical evidence. An unsigned release flag cannot enable scoring.
- Scoped technical administrators can propose calibration packets containing
  exact existing run, snapshot and source digests. Reads recheck source access.
  Packets remain `PROPOSED_UNVERIFIED`, with representativeness explicitly
  unestablished. Unknown period roles stay unknown. Approval fields and forged
  source references are rejected. Generic AI-run reads exclude these records.
- New discovery reads expose the current reviewer's eligible signed assignments
  and the subject's scoped assessment receipts. Full history, approved-revision
  replay and factual appeals use the existing protected lifecycle APIs.
- The performance UI distinguishes legacy, unknown, provisional, under-review,
  approved and disputed states. Explicit legacy numeric values remain readable;
  an appeal does not erase an earlier historical approval or present it as the
  current approved result. Missing values do not become zero scores or grades.
- The feedback UI accepts assigned unscored observations with explicit state,
  reason and conflict attestation. It supplies no default numeric rating and
  cannot choose arbitrary employees. Retired numerical write controls, fixed
  dimension maxima and AI-confidence authority were removed from these pages.
- Private drafts stay in memory and clear on account change/sign-out. Failed
  requests retain notes. Revision conflicts require reload, comparison and
  explicit adoption of the newer revision; notes are preserved. A late response
  clears only the submitted draft version and cannot erase a newer remounted
  draft. Replay results remain tied to their original assessment.
- Shared fields retain native selection and keyboard focus. Multiline notes
  have labels, error association and a fixed resize policy. Pending actions
  retain width. Scope errors have access-specific recovery messages.

The shared API interceptor now preserves sanitized HTTP status and string detail
for callers. It does not attach request configuration, authorization headers,
submitted notes or structured validation input. This fixes the real client
boundary where a legitimate initial review 404 previously became a generic error.
Authentication refresh behavior was preserved.

## Executed checks

| Check | Actual result |
|---|---|
| Pre-commit full backend suite, native Mongo opt-in enabled | **2,716 passed, 111 skipped, 78 warnings**; 98.17 seconds |
| New readiness, provenance, scoped discovery and API tests | **8 passed**, 4 warnings; 2.61 seconds; also included in the full suite |
| Pre-commit full frontend suite | **172 passed in 23 files**; 70.10 seconds |
| Real API-client and observation/appeal regressions | **10 passed in 2 files**; 2.85 seconds; also included in the full suite |
| Production frontend build | Passed |
| Frontend lint | **0 errors, 10 existing warnings** |
| New Python DTO/service/tests, Ruff F/E9 | Passed |
| Repository runtime-name/syntax checks, Ruff F821/E9 | Passed |
| New DTO/service scoped Mypy | Passed, 2 source files; imports followed silently |
| Whole-backend Mypy | **Did not pass**; existing import/module-layout errors prevented further checking |
| Strict scoped UI audit | **0 errors, 0 warnings** |
| Editor diagnostics, changed backend runtime and API client | No errors reported |

The whole-backend type-check blockers were missing
`langchain_community.llms`, missing `domain.models.qa_ci_config`, and duplicate
module discovery of `services/transfer_service.py`. Scoped Mypy does not certify
the full repository. The pinned Mypy 1.11.2 development tool was installed in the
existing environment; dependency manifests were unchanged.

The 111 backend skips are not passing evidence. Mongo opt-in was enabled and the
suite included the owned temporary concurrency collection. Docker benchmark
opt-in was disabled. No live worker, live Ollama, authenticated production
workflow or separate deployment host was validated. New service/API tests use
isolated database fixtures; no real employee assessment was changed.

The obsolete performance/feedback page tests were replaced, not skipped: they
expected retired default-number writes and excluded PM as a subject. Replacement
tests exercise seven role contexts, explicit empty/scope-error states, assigned
targets, no premature URL-selected queries, and absence of retired writes.

An independent review reproduced three concrete integration defects: stripped
HTTP statuses, late-save draft deletion and missing stale-appeal recovery. The
real-client status tests and observation remount race failed before their fixes
and passed afterward. Follow-up read-only review found no remaining concrete
issue in those fixes. This review does not establish empirical calibration.

## Browser evidence and limits

Actual components and shared styles were exercised in a temporary synthetic
preview on an isolated localhost origin. Desktop and 390-pixel layouts, native
keyboard selection, visible 2-pixel focus, required-field focus, non-resizable
notes, pending save width, success, access-error recovery, light theme and
reduced-motion preference were checked. No horizontal overflow or numeric rating
input was found in the checked narrow view. The 256-pixel save action retained
its width while pending.

The [narrow-screen capture](./2026-11-12-scoring-phase6-narrow.png) contains only
synthetic data. Google Fonts was unavailable in the isolated preview, so these
checks used system fallback fonts. A malformed desktop capture was discarded;
it is not presented as visual evidence. The temporary preview, synthetic session
and preview server were removed afterward; the existing app origin was untouched.
These component checks do not substitute for a signed-in end-to-end deployment
check or a complete accessibility audit.

See the [scoped audit](./2026-11-12-scoring-ui-audit.json),
[design context](../../DESIGN.md), [interaction contract](../../UX-CONTRACT.md)
and [implementation plan](../plans/2026-11-12-scoring-phase6.md).

## Reproduction

From `backend/` in the configured Python 3.12 environment:

```powershell
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
.venv/Scripts/python.exe -m pytest tests/test_performance_readiness.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check --select F821,E9 .
.venv/Scripts/python.exe -m mypy domain/models/performance_readiness.py domain/services/performance_readiness_service.py --follow-imports=silent --ignore-missing-imports --check-untyped-defs --no-incremental
```

From `frontend/`:

```powershell
npm test -- --run --maxWorkers=2 --testTimeout=30000
npm run build
npm run lint
```

Windows child-process restrictions required running tests/build outside the
restricted sandbox. The earlier frontend default-timeout limitation was not
claimed fixed.

## Remaining calibration boundary

The specification explicitly treats role dimensions, measurement rules, scale
anchors, weights, coverage thresholds and release approval as calibration
decisions. No authorized representative dataset or approved policy reference
was present in the inspected repository or supplied during this work. An
asynchronous request for that specific reference remains unanswered.

Developer calibration must be performed first against authorized representative
work, including gaming, duplication, coverage and low-activity/high-value cases;
then QA, DevOps, Lead and PM require their own role evidence. Genuine calibrated
deterministic measurement and workplace-source adapters, numerical shadow
comparisons, independent policy/release sign-off and deliberate deployment
verification remain outstanding. Unverified calibration packets and synthetic
test scores cannot fulfill those requirements. No production issuer or activation
shortcut was fabricated. The next required input is an approved calibration
policy and representative-work source reference, not a complete manual employee
algorithm specification.

## Step 1 integration checkpoint

The existing independent review and follow-up findings above were retained.
Fresh pre-commit backend/frontend suites, build, lint, Ruff runtime-name checks
and staged whitespace checks passed with the counts and limitations above.
CodeRabbit was unavailable: its CLI was missing, and the exact installer action,
after manual authorization, failed with `Unsupported operating system:
mingw64_nt-10.0-26300`. No CodeRabbit review or zero-issue claim is made. Running
it later requires a supported environment with its CLI installed and authenticated.

The Phase 6 integration checkpoint contains only its 39 runtime, regression,
design and verification files on `testing`. Production scoring remains disabled;
this checkpoint does not approve calibration or activate a release. Unrelated
editor settings, project/test notes and the empirical harness are excluded.
Secrets, environment configuration and live employee records were not modified.
Step 1 requests a local commit only; no push or deployment is included.
