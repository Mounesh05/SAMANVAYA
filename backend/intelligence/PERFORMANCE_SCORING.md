# Scoring Phase 1: canonical contracts

This phase adds a versioned foundation for the scoring migration. It does not
activate a new employee assessment policy or change historical calculations.

## Components

- [Domain contracts](../domain/models/performance_scoring.py): declared score
  units, nullable coverage, UTC half-open periods, revision ancestry, immutable
  snapshots, draft rubrics and explicit missing-dimension states.
- [Canonical catalog](performance_registry.py): one dimension enum shared by
  schema validation, evidence-kind mappings and generated advisory contract
  metadata. Unknown identifiers and duplicate dimensions fail validation.
- [Pure composition](performance_scoring.py): decimal half-up composition of
  `0.90 * E + 0.10 * H`, once, with separate contributions. Missing E or H leaves
  the combined result null. Arithmetic outputs are always non-authoritative.

All canonical scores use a declared 0–100 period unit. PR scores remain 0–10;
legacy AI values remain 0–90 contributions. Conversion requires an explicit
legacy unit and retains its original value. A repeating normalized display is
derived; exact composition uses the original contribution to avoid moving a
rounding boundary. No production read path automatically converts legacy AI
output into validated engineering evidence.

Numbers reject booleans, strings, nonfinite values and unsupported precision.
Snapshots reject numbers that cannot round-trip through JSON without precision
loss. Digests cover canonical JSON, including identity, references and versions;
references alone do not prove evidence validity or authorization.

## Pending policy and approval

Developer dimensions are candidates with null weights and measurement rules.
QA, DevOps, Lead and PM profiles are explicitly unavailable pending calibration.
HR and CEO are not engineering subject profiles. Coverage thresholds, reviewer
weights and grade bands are not invented. Shadow assessment E/H/S remain null,
and every profile is non-finalizable.

The transition table checks state adjacency only. It does not grant permission,
approve an assessment, validate an evidence snapshot or implement a workflow.
No approval endpoint or new persistence collection is introduced.

## Legacy response migration

Existing detail, HR, dashboard, trend and team responses gain additive `scoring`
metadata. Their existing scores and grades retain their old meaning. Metadata
identifies them as `LEGACY_READ_ONLY` / `LEGACY_UNVERIFIABLE`, declares units,
preserves declared legacy methodology versions and exposes null canonical
scores, approval, snapshot and policy. Coverage remains unknown.

Metadata is recomputed from trusted record fields, not accepted as an input
approval claim. Reads do not backfill documents. Repository create/update paths
exclude this derived response annotation from storage.

The old agent, legacy dimension weights and human scoring continue under their
existing semantics. Their known registry/manifest, arithmetic and authorization
defects are recorded in the [Phase 0 audit](../../docs/reports/2026-11-12-scoring-phase0-audit.md).
They are not silently treated as canonical. Generated canonical contract
metadata is ready for the later advisory-claim migration; it is not a second
active scoring policy or a replacement prompt wired into the legacy agent.

## Validation and next phases

Contract tests cover units, arithmetic, rounding, missing inputs, unknown
coverage, revision/period validation, immutable replay and registry consistency.
Compatibility tests exercise real model/service/API serializers against an
isolated in-memory database and check that reads preserve stored documents.

Phase 2 will establish validated evidence, attribution and coverage. Later
phases own advisory claim validation, human scoring, independent approval and
historical migration. Those prerequisites are required before canonical
assessment publication.
