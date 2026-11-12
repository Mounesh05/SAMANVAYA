# Scoring Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strict, versioned score contracts and one canonical dimension registry without activating an uncalibrated scoring policy or changing historical numbers.

**Architecture:** Follow the supplied specification's additive migration. Typed models live in the existing domain layer; registry and pure arithmetic live in intelligence. Existing period/API serializers attach explicit legacy metadata with null canonical scores. No new scoring platform, approval endpoint, evidence collector or database backfill.

**Tech Stack:** Existing Python 3.12, Pydantic 2.9.2, FastAPI, MongoDB repositories, pytest.

**Spec:** `C:/Users/Mounesh/Downloads/SAMANVAYA_SCORING_ARCHITECTURE_IMPLEMENTATION_SPEC.md`, Phase 1; [Phase 0 findings](../../reports/2026-11-12-scoring-phase0-audit.md).

## Global Constraints

- E, H, S are 0-100; final composition is 0.90 E + 0.10 H, applied once.
- Missing/unapproved evidence or policy never becomes zero, neutral or an approved score.
- Example role/rubric weights, coverage thresholds and grade bands remain unapproved.
- CEO and HR are not engineering subject profiles. No routine CEO numerical component is introduced.
- Legacy 60/30/10 arithmetic, LLM agent behavior and current stored numbers remain legacy until their owning migration phases.
- No live data migration, new approval authority, UI redesign, dependency changes, commits or push in this phase.
- Work in the current `testing` checkout; preserve Phase 0 artifacts and unrelated untracked user files.

## Review Focus

- Reject booleans, numeric strings, NaN/infinity and cross-family units at calculator/model boundaries (Task 1).
- Reject naive/empty periods, invalid revision ancestry and mutable nested snapshot structures (Task 1).
- Registry/schema/prompt-contract drift and unknown evidence/dimension identifiers must fail explicitly (Task 2).
- A draft role profile cannot yield an authoritative combined score, even with numeric input (Task 2).
- Legacy read serialization must preserve numbers and confidentiality while exposing null canonical values; no read-triggered writes (Task 3).

## Task 1: Units, identity and immutable calculation contracts

**Files:** Create `backend/domain/models/performance_scoring.py`, `backend/intelligence/performance_scoring.py`, `backend/tests/test_performance_scoring_contracts.py`.

**Interfaces:** `ScoreValue(unit, value)`; `VersionReference(id, version)`; `AssessmentIdentity`; `DimensionResult`; `CoverageSummary`; `CalculationSnapshot`; `ScoreCalculation`. `combine_scores(engineering: ScoreValue | NormalizedLegacyAI | None, human: ScoreValue | None) -> ScoreCalculation`; `normalize_legacy_ai_contribution(score: ScoreValue) -> NormalizedLegacyAI`; `snapshot_digest(snapshot: CalculationSnapshot) -> str`.

- [x] Write and run failing tests: E=86/H=80 gives 85.4, 77.4/90 explicitly converts to 86/100, missing input leaves S null, different units fail, invalid scalar inputs fail, Decimal rounding uses half-up once.
- [x] Implement immutable typed contracts with timezone-aware half-open periods, version references, revision identity, tuple-based observations and deterministic snapshot hashing. Arithmetic is explicitly non-authoritative and cannot approve a result.
- [x] Verify JSON round trips, strict numeric validation, date/revision denials and arithmetic invariants with focused tests.

## Task 2: Canonical registry and pending policy contracts

**Files:** Create `backend/intelligence/performance_registry.py`, extend contract tests.

**Interfaces:** `get_rubric_profile(role)`; `canonical_scoring_contract()`; `validate_dimension_results(results)`; `prepare_shadow_assessment(identity, dimensions)`. One `DimensionId` enum drives typed model validation, allowed evidence kinds and generated contract metadata. Developer dimensions are candidates with null weights; QA/DevOps/Lead/PM profiles remain unavailable pending calibration.

- [x] Write and run failing tests for registry alignment, unsupported dimensions/evidence kinds, duplicate dimensions, missing observations, unavailable role profiles, and attempts to turn a draft profile into a final score.
- [x] Implement the shared registry and structural assessment transition table. Transition adjacency is not authorization; no approval operation is exposed.
- [x] Verify all current role profiles remain non-finalizable and no numerical rubric weights/grade bands are invented.

## Task 3: Legacy-compatible metadata and API serialization

**Files:** Modify `backend/domain/models/developer_performance.py`, `backend/domain/schemas/hr_views.py`, `backend/domain/services/performance_service.py`, `backend/repositories/performance_repository.py`, and minimal serializers in `backend/api/routes/performance.py`; create `backend/tests/test_performance_scoring_compatibility.py` and phase documentation.

**Interfaces:** Add `scoring` metadata with schema/mode/status/methodology/units and nullable canonical E/H/S. `legacy_scoring_metadata(methodology_version=None)` never promotes legacy numeric inputs to canonical evidence. Existing response fields and score values retain their original meaning.

- [x] Write and run failing model/API tests: old rows read without backfill, old values unchanged, direct/HR/dashboard/trend/team serializers agree on legacy status, client numerical fields cannot approve results, read paths do not update stored rows.
- [x] Implement additive metadata and serialization only. Do not repair the Phase 0 formula/collector/security findings as unrelated work inside this task.
- [x] Run focused tests, the existing backend suite using the Phase 0 baseline runner, Phase 0 characterization probes and frontend checks. Run runtime lint, inspect the diff and perform one fresh read-only review.

## Execution ledger

- Baseline: `28de5f93`; Phase 0 backend 2,468 passed/111 skipped, frontend 157 passed. Docker stopped; no dependency installation required.
- Ruling: use the already supplied detailed design and explicit Phase 1 authorization; no new design-approval cycle is needed.
- Ruling: keep work in the current checkout so the uncommitted Phase 0 artifacts remain available; changes will be narrowly staged only if later requested.
- Ruling: implement inline with a single final independent review. Do not commit or push without a new request.
- Pre-flight: Tasks 1/2 share DimensionId/ScoreValue; the domain model owns identifiers and units, the registry owns allowed structural evidence kinds. Task 3 only consumes legacy metadata; it never invokes canonical arithmetic on legacy records.
- Task 1 complete: 33 contract cases observed RED (modules absent), then GREEN. Fixed the observed both-components-missing max() edge case before proceeding.
- Task 2 complete: 14 further cases observed RED; 47 contract/registry cases now pass. Canonical evidence-reference ordering is normalized for stable digests.
- Ruling: JSON snapshots explicitly reject Decimal values that cannot round-trip as JSON numbers without precision loss; arithmetic itself remains Decimal. This prevents silently unreplayable snapshots rather than truncating evidence values.
- Ruling: execution progress is recorded here rather than via POSIX orchestration scripts; no implementation commits or workspace changes are authorized by this phase request.
- Ruling: retain exact legacy conversion origins in a typed value, deriving normalized display only; repeating decimals otherwise move half-cent boundaries. The conversion helper's return type is therefore explicit rather than a lossy plain ScoreValue.
- Task 1 follow-up: RED→GREEN tests for recurring conversion, bounded precision, unknown coverage and a 200-digit rounding boundary. Unknown coverage is explicitly represented without a fabricated acceptance threshold.
- Task 3 implementation: 61 focused cases pass. Legacy serializers annotate detail/HR/current/history/trend/team responses; repository writes strip derived metadata. Existing numerical behavior remains unchanged.
- Ruling: legacy agent dimension drift remains explicitly characterized by Phase 0; only canonical contracts share the new registry. Rewiring the legacy numeric agent now would silently change historical semantics before evidence and claim-validation phases. Cost: existing legacy agent defects persist until their owning migration phases.
- Final: fixed Important review finding (calculation model accepted inconsistent units/results) — 13 negative direct/JSON/snapshot cases observed RED, then GREEN. Shared exact arithmetic now enforces formula and completeness during restoration. No Critical or Minor findings raised.
- Final: Ruling: unchanged legacy formula/manifest/authorization defects remain outside this additive patch — legacy semantics stay explicitly labeled and the broader cross-agent alignment exit is not claimed; cost: known defects persist.
- Final: Ruling: evidence validity, attribution and source existence without supplied source maps remain Phase 2 work — references do not establish eligibility; cost: no canonical assessment can be approved from these contracts alone.
- Final: Ruling: approval authorization, revision concurrency and historical restatement remain later migration work — adjacency and immutable contract shape are not workflow authority; cost: no new approval/persistence workflow is available.
- Final: Ruling: production rubric weights and coverage thresholds remain unapproved — preserve null canonical outcomes; cost: calibration is required before activation.
- Final: Ruling: independent reviewer performed bounded contract checks; implementer owns full regressions — do not present the full suite as independently reproduced; cost: one independent review, not two full executions.
- Task 3 complete: 74 focused tests; full backend 2,542 passed/111 skipped; 19 Phase 0 probes passed reproducing existing behavior; frontend 157 passed/build passed/lint 16 existing warnings; runtime Ruff and editor diagnostics clear. Initial sandbox access failures were resolved by running existing tests outside the sandbox, not by altering source.
- Final verification and decision costs: [Phase 1 report](../../reports/2026-11-12-scoring-phase1-verification.md). Current checkout preserved, no implementation commits/push or cleanup.
