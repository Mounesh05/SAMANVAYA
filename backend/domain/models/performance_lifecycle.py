"""Lifecycle transport contracts carry no authority to supply scores or approval."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from domain.models.performance_claims import Text
from domain.models.performance_evidence import utc_time
from domain.models.performance_human import EligibleHumanReview
from domain.models.performance_scoring import (
    CalculationSnapshot, Digest, FrozenContract, NonEmpty, Number, SubjectRole, VersionReference,
)


class AssessmentCreateRequest(FrozenContract):
    run_id: NonEmpty
    reason: Text


class RevisionRequest(FrozenContract):
    expected_digest: Digest
    request_id: NonEmpty
    reason: Text


class AssessmentActionRequest(RevisionRequest):
    action: Literal["COLLECT", "VALIDATE", "ELIGIBLE", "CALCULATE", "REVIEW", "APPROVE", "REJECT", "CANCEL", "CORRECT"]
    run_id: NonEmpty | None = None
    measurement_id: NonEmpty | None = None
    assignment_id: NonEmpty | None = None


class AssessmentAppealRequest(RevisionRequest):
    evidence_references: Annotated[tuple[NonEmpty, ...], Field(max_length=20)] = ()


class ApproverAssignmentRequest(FrozenContract):
    reviewer_id: NonEmpty
    qualification_reason: Text
    qualification_source_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    no_conflict_attested: Literal[True]
    expires_at: datetime

    _utc = field_validator("expires_at")(utc_time)


class PolicyReviewRequest(FrozenContract):
    reason: Text
    effective_from: datetime

    _utc = field_validator("effective_from")(utc_time)


class ScoringRelease(FrozenContract):
    """Internal calibrated-release adapter contract; not accepted by public APIs."""
    policy_draft_id: NonEmpty
    policy_draft_digest: Digest
    policy_review_id: NonEmpty
    policy_review_digest: Digest
    rubric: VersionReference
    subject_role: SubjectRole
    measurement_method: VersionReference
    minimum_engineering_coverage: Annotated[Number, Field(ge=0, le=100)]
    calibration_source_refs: Annotated[tuple[NonEmpty, ...], Field(min_length=1, max_length=20)]
    effective_from: datetime
    effective_until: datetime

    _utc = field_validator("effective_from", "effective_until")(utc_time)


class MeasurementAttestation(FrozenContract):
    """Frozen outputs from a trusted deterministic adapter, never caller numbers."""
    run_id: NonEmpty
    release_id: NonEmpty
    snapshot: CalculationSnapshot
    human_reviews: Annotated[tuple[EligibleHumanReview, ...], Field(min_length=1, max_length=5)]
    human_review_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1, max_length=5)]
