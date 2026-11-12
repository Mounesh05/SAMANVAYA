# Assessment lifecycle, historical migration and policy governance

Phase 5 builds on the existing evidence, claim, human-feedback and canonical
calculation contracts. It does not add a scoring model or calibrate a rubric.

## Immutable workflow

The [lifecycle service](../domain/services/performance_lifecycle_service.py)
stores signed events in existing `ai_runs`. A deterministic assessment identity
binds organization, employee, project and the exact half-open period. Repeated
creation for the same snapshot returns its original receipt. A different
snapshot for an existing period requires an explicit correction.

Each event contains its revision, predecessor digest, frozen evidence, action,
reason, current actor and idempotency digest. State change and audit metadata
are one insert, rather than two writes that can partially commit. Mongo's
natural primary key permits only one successor at each revision. Conflicting
writers receive 409; identical retries recover their original receipts. History
reads verify the signed predecessor chain. No application delete/edit API is
provided. This protects application workflows, not deletion by a database
administrator who controls storage and backups.

| Action | From | To | Additional gate |
|---|---|---|---|
| COLLECT | DRAFT | EVIDENCE_COLLECTING | Scoped technical administrator, independent of subject |
| VALIDATE | EVIDENCE_COLLECTING | EVIDENCE_VALIDATED | Trusted exact-snapshot measurement and calibrated release |
| ELIGIBLE | EVIDENCE_VALIDATED | SCORING_ELIGIBLE | Same frozen applicable measurement |
| CALCULATE | SCORING_ELIGIBLE | PROVISIONAL | Replayable complete E/H/S |
| REVIEW | PROVISIONAL | UNDER_REVIEW | Independent assigned qualified reviewer |
| APPROVE | UNDER_REVIEW | APPROVED | Independent reviewer and freshly rechecked measurement eligibility |
| REJECT | UNDER_REVIEW or DISPUTED | REJECTED | Independent assigned reviewer |
| CANCEL | Unapproved active states | CANCELLED | Scoped administrator |
| Appeal | Existing assessment | DISPUTED | Current scoped subject |
| CORRECT | DISPUTED, REJECTED, APPROVED or INSUFFICIENT_EVIDENCE | DRAFT | Explicit replacement snapshot in the exact original scope |

Subjects cannot manage their own workflow even if they later become admins.
Approvers cannot be subjects, initiators, assignment issuers or contributors to
the human measurement. Current account, organization/project, issuer authority,
qualification/source attestation and assignment expiry are checked. Role/title
alone is insufficient. No delegated appeal authority is inferred from `is_admin`.

Corrections reset measurement eligibility and preserve every old event. Prior
APPROVED events remain historical approval events; the separate current header
reports a dispute or restatement and does not present an old score as currently
approved. Executive/HR views contain approved historical summaries and current
workflow status, without unapproved scores or raw observations. Own historical
summary rights survive a role change within the same organization.

## Measurement and policy authority

[Internal adapter contracts](../domain/models/performance_lifecycle.py) require
server-signed `performance_measurement` and `performance_scoring_release`
artifacts. There is no public API that issues these artifacts or accepts E/H/S,
calibration authority or an approval Boolean. Protected kinds are excluded from
generic AI-run visibility. Ordinary unsigned AI-run documents cannot establish
their authority.

A measurement must match exact evidence/scope, role/rubric/method/policy versions,
an independently reviewed policy draft, explicit effective dates, engineering
coverage and complete human reviews. The shared human engine recomputes H and
the canonical formula from frozen typed inputs. Signed human observation records
must match the declared resolved inputs. Current reviewer eligibility and the
latest human revision are checked for new approval. Measurements cannot be
switched midway through review.

Human corrections append signed revisions with expected predecessor digests;
they never overwrite the original rating. A corrected observation invalidates a
stale measurement for new approval. Historical replay uses the inputs that were
frozen at that historical revision, rather than silently substituting a newer
review, policy or account role.

Policy proposals are inspectable in scope. An independent scoped technical
reviewer can seal a review and a future effective date. This yields
`REVIEWED_INACTIVE`, not numerical activation. Past-period policy activation is
not inferred. Phase 6 must provide the actual calibrated release/measurement
issuer and its empirical validation; neither a governance review nor a model
response is that evidence. The positive approval/replay tests use explicitly
synthetic trusted adapter fixtures. No production adapter or rubric was invented.

## Historical read migration and shadow mode

[The access service](../domain/services/performance_access_service.py) now owns
all existing performance detail, trend, dashboard, team, HR-case, policy-history,
completeness and legacy appeal routes. It reloads current accounts rather than
trusting token role/admin claims. Current subject organization and the recorded
project must resolve in the same org; explicit conflicting org metadata is
rejected. Unresolved historical provenance is withheld, not guessed or backfilled.

HR and CEO get allowlisted historical numerical summaries, with explicit
`LEGACY_READ_ONLY` / `LEGACY_UNVERIFIABLE` metadata. Historical compatibility is
not a new approval. They receive no raw engineering narrative or confidential
HR observations. Engineering detail excludes confidential HR assessments and
feedback. Legacy HR case detail is restricted to its current authorized HR
author in the exact subject scope; an executive/admin flag is not case access.

Historical numbers, grades and declared methodology versions are preserved.
Legacy trends are `not_comparable` with methodology/coverage/period caveats;
team lists are ordered by identity, not unverifiable cross-role score rankings.
Unscoped/foreign legacy policies are withheld. Policy history does not manufacture
default weights or convert old `is_active` flags into canonical approval.

Legacy appeals are protected immutable artifacts bound to the exact historical
record digest. The old row and its score/status are not mutated. Read/export
access is audited. Exports require an explicit purpose and contain only scoped
allowlisted summaries plus an export digest, not raw HR/code/credential content.

The shadow endpoint reports the legacy number and known methodology differences,
missing snapshots/coverage/calibration, and placeholder anomalies. Without valid
canonical inputs, canonical score and difference stay null. It does not reverse
engineer a new score from a historical final number. Representative numerical
discrepancy calibration remains part of Phase 6.

## Key retention and rollback

New artifact envelopes carry `signing_key_id` and schema `performance-artifact-v2`.
The operator may configure secret `PERFORMANCE_SIGNING_KEYS` as a JSON key-id to
key-material map and `PERFORMANCE_SIGNING_KEY_ID` as its active ID. Without this
map, `application-secret` uses the existing application secret for compatibility.
Before rotating, retain its old material under `application-secret`, supply a
new active ID/material, and keep prior verification keys for retained history.
Keys are deployment secrets, never response fields or logged policy metadata.

For pre-Phase-5 v1 artifacts, retain the old original application secret in
`PERFORMANCE_LEGACY_SIGNING_KEY` before rotating the session secret. v1 records
are verified unchanged; they are not re-signed or rewritten as v2. Missing/wrong
verification keys fail closed. Tests verify both retention paths and unchanged
historical bytes/documents. No live secret or environment file is modified here.

Rollback keeps legacy numbers readable through the **scoped** historical API
while withholding canonical publication. It never deletes new revisioned
artifacts or re-enables unsafe numerical legacy writes. An older application
that cannot verify v2 artifacts must not be used as a verifier of new approvals.
Back up retained verification keys and collections before deployment changes.

## API additions

Under `/api/performance`: `POST /assessments`,
`GET /assessments/{id}/history`, `POST /assessments/{id}/actions`,
`POST /assessments/{id}/appeals`, `POST /assessments/{id}/approvers`,
`GET /assessments/{id}/revisions/{revision}/replay`,
`POST /human-reviews/{assignment_id}/revisions`,
`GET /human/policy-drafts/{id}`, `POST /human/policy-drafts/{id}/reviews`,
`POST /developer/{id}/export`, `GET /developer/{id}/shadow`.

Frontend lifecycle controls, legacy/status labeling and release calibration are
Phase 6 integration work; current frontend regression tests do not certify
those new screens. Existing presentation fallbacks (for example the performance
page's default displayed confidence) must be removed before release sign-off.
