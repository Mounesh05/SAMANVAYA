# Human observation intake and canonical composition

Phase 4 uses one [pure human aggregator](performance_human.py). Both ordinary
and HR service composition entry points delegate to it, then reuse the existing
canonical `combine_scores`. Inputs and E/H/S are on the 0–100 scale. H is not
rounded before `S = round_half_up(0.90E + 0.10H, 2)`. Neither composition nor a
complete arithmetic result establishes final assessment approval.

## Policy and eligibility

[Contracts](../domain/models/performance_human.py) require explicit reviewer
weights, dimension weights and anchored scores. Weights sum exactly to one,
including beyond the default Decimal precision. Both four-point and five-point
rating scales can be declared explicitly; no legacy normalization is assumed.
There are no production default reviewer weights, mandatory reviewers, waivers,
grade bands or calibrated scoring anchors.

CEO cannot be a routine reviewer; its numerical contribution is always zero.
Technical measurements cannot be rescored as human contextual feedback. HR is
limited to professional conduct, workplace ethics, policy compliance, mandatory
learning and workplace accountability. Other eligible reviewers may assess only
the supported contextual dimensions explicitly assigned to them.

Every weighted role and dimension must be present exactly once, from an eligible
reviewer, observed and supported by independently validated evidence before H
can be calculated. No available-reviewer renormalization occurs. NOT_OBSERVED,
NOT_APPLICABLE and UNDER_REVIEW require reasons and have no numeric rating.
Without an approved resolution they block completion, rather than changing the
denominator or supplying zero/neutral credit. Missing E always leaves S null.

## Intake and privacy

[The service](../domain/services/performance_human_service.py) reuses existing
signed interpretation snapshots to bind organization, project, subject and exact
half-open period. An independent current Lead/PM technical administrator must
attest the reviewer's actual period interaction and absence of conflicts. The
attestation references exact source IDs/digests in that snapshot. Artifact
existence or a job title alone is not proof of the interaction.

Current account status, org, subject eligibility, project membership, reviewer
role/HR permission, issuer authority and expiry are checked on use. Subject and
issuer cannot review their own assignments. There is one immutable reviewer slot
per role and snapshot. Requesters cannot submit an evaluator ID, approved policy,
validated-evidence flag, engineering score or final score in a review body.

Observation references record source identity/revision, occurrence time, reason
and a direct-observation attestation. They are **not independently verified facts**.
In particular, a long comment or an arbitrary link cannot establish substantiated
negative or exceptional behavior. These references are never fetched or executed.
Their validation remains pending; current production H and S remain null.

Assignments, reviews and policy drafts use the existing HMAC-sealed `ai_runs`
envelope and are excluded from generic AI-run access. An identical review retry
returns its existing receipt. A different retry fails with 409 and preserves the
original. Identical assignment retries also recover their original receipt;
different reviewer/issuer/payload assignments conflict. Mongo primary-key
uniqueness arbitrates concurrent writes. Private
observations are returned only to their current eligible author. Scoped subject,
manager and assigned HR completeness responses contain role/state summaries,
without another reviewer's ratings, comments or evidence references. HR receives
no raw engineering snapshot access from this pathway. Nothing is sent to Ollama.

## API

All paths below are under `/api/performance`:

- `POST /human-reviewers`: attest an exact-period assignment.
- `POST /human-reviews/{assignment_id}`: submit an assigned contextual review.
- `POST /human-reviews/{assignment_id}/hr`: same intake with an additional HR-role check.
- `GET /human-reviews/{assignment_id}`: retrieve the current eligible author's own observations.
- `GET /human/{run_id}/completeness`: inspect redacted intake/eligibility status.
- `POST /human/policy-drafts`: seal an inactive policy proposal; cannot approve or activate it.

Legacy numerical role feedback, HR draft/submission and policy-activation writes
return 409 with a string `detail` and `POLICY_PENDING` (CEO numerical feedback:
`CEO_SCORING_DISABLED`). Programmatic mutation methods are retired too. They do
not initialize fake engineering rows, substitute missing HR ratings, rewrite
grades, double-weight old AI contributions or reuse prior composites as inputs.
Old HR scalar display conversion remains explicitly historical; legacy subset
averages can no longer supply H. Policy reads do not seed example policies.

## Deliberate remaining boundaries

Production-approved policy lookup, independent observation-source validation,
calibrated E measurement, assessment approval/revision/appeal, assignment
substitution and waivers are not invented here. Phases 5–6 own governance,
migration and calibration. The pure approved-policy tests use synthetic fixtures
only; no employee rating is activated by those fixtures.

Existing historical read routes remain compatible. This phase does **not** claim
to fix the previously audited cross-org legacy outcome/HR-read authorization
gap; its read migration/redaction remains outstanding for Phase 5. HMAC key
retention/rotation migration is likewise still required before production
assessment activation. No deployment or employment-outcome fairness sign-off is
implied by passing software tests.
