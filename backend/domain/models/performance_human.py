"""Human observation contracts. Parsing a policy never establishes its authority."""

from datetime import datetime
from decimal import localcontext
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from domain.models.performance_claims import Text
from domain.models.performance_evidence import utc_time
from domain.models.performance_scoring import FrozenContract, NonEmpty, Number, ScoreCalculation, SubjectRole

HUMAN_METHOD_VERSION = "human-aggregation-v1"
ReviewerRole = Literal["LEAD", "PM", "QA", "DEVOPS", "HR"]
HumanDimension = Literal["communication", "collaboration", "follow_through", "mentoring",
    "professional_conduct", "workplace_ethics", "policy_compliance", "mandatory_learning", "workplace_accountability"]
HR_DIMENSIONS = frozenset({"professional_conduct", "workplace_ethics", "policy_compliance",
                           "mandatory_learning", "workplace_accountability"})
Rating = Annotated[int, Field(strict=True, ge=1, le=5)]
Weight = Annotated[Number, Field(gt=0, le=1)]


def weights_sum_to_one(weights):
    weights = tuple(weights)
    with localcontext() as context:
        context.prec = max(50, sum(len(w.as_tuple().digits) + abs(w.as_tuple().exponent) for w in weights) + 10)
        return sum(weights) == 1


def check_dimensions(role, dimensions):
    if len(set(dimensions)) != len(dimensions):
        raise ValueError("Duplicate dimensions are not independent observations")
    if any((dimension in HR_DIMENSIONS) != (role == "HR") for dimension in dimensions):
        raise ValueError("HR reviews are limited to workplace dimensions; technical reviewers cannot rescore HR dimensions")


class HumanEvidenceReference(FrozenContract):
    source_reference: NonEmpty
    source_revision: NonEmpty
    observed_at: datetime

    _utc = field_validator("observed_at")(utc_time)


class HumanObservation(FrozenContract):
    dimension: HumanDimension
    state: Literal["OBSERVED", "NOT_OBSERVED", "NOT_APPLICABLE", "UNDER_REVIEW"]
    rating: Rating | None = None
    reason: Text
    direct_observation: bool = Field(default=False, strict=True)
    evidence: Annotated[tuple[HumanEvidenceReference, ...], Field(max_length=8)] = ()

    @model_validator(mode="after")
    def observed_shape(self):
        if self.state == "OBSERVED":
            if self.rating is None or not self.direct_observation or not self.evidence:
                raise ValueError("Observed ratings require direct observation and versioned evidence references")
        elif self.rating is not None:
            raise ValueError("Unobserved, inapplicable or disputed dimensions cannot have numeric ratings")
        keys = [(e.source_reference, e.source_revision, e.observed_at) for e in self.evidence]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate evidence references are not independent support")
        return self


class HumanRatingAnchor(FrozenContract):
    rating: Rating
    score: Annotated[Number, Field(ge=0, le=100)]
    description: Text
    evidence_required: bool = Field(strict=True)


class HumanDimensionRule(FrozenContract):
    dimension: HumanDimension
    weight: Weight
    anchors: Annotated[tuple[HumanRatingAnchor, ...], Field(min_length=2, max_length=5)]

    @model_validator(mode="after")
    def anchors_complete(self):
        if {a.rating for a in self.anchors} != set(range(1, len(self.anchors) + 1)):
            raise ValueError("Explicit unique anchors for the declared contiguous rating scale are required")
        # Negative and exceptional ratings always require substantiated evidence.
        if any(not a.evidence_required for a in self.anchors if a.rating in {1, 2, len(self.anchors)}):
            raise ValueError("Negative and exceptional anchors must require evidence")
        return self


class HumanRoleRule(FrozenContract):
    role: ReviewerRole
    weight: Weight
    dimensions: Annotated[tuple[HumanDimensionRule, ...], Field(min_length=1, max_length=9)]

    @model_validator(mode="after")
    def role_scope(self):
        check_dimensions(self.role, [d.dimension for d in self.dimensions])
        if not weights_sum_to_one(d.weight for d in self.dimensions):
            raise ValueError("Dimension weights must sum exactly to one")
        return self


class HumanPolicy(FrozenContract):
    policy_id: NonEmpty
    version: NonEmpty
    subject_role: SubjectRole
    status: Literal["DRAFT", "APPROVED"] = "DRAFT"
    roles: Annotated[tuple[HumanRoleRule, ...], Field(min_length=1, max_length=5)]
    ceo_weight: Literal[0] = 0
    nonobserved_rule: Literal["BLOCK_UNTIL_APPROVED_RESOLUTION"] = "BLOCK_UNTIL_APPROVED_RESOLUTION"
    method_version: Literal["human-aggregation-v1"] = HUMAN_METHOD_VERSION

    @model_validator(mode="after")
    def complete_weights(self):
        if len({r.role for r in self.roles}) != len(self.roles) or not weights_sum_to_one(r.weight for r in self.roles):
            raise ValueError("Unique reviewer roles with weights summing exactly to one are required")
        return self


class HumanPolicyDraftRequest(FrozenContract):
    project_id: NonEmpty
    policy: HumanPolicy
    reason: Text

    @model_validator(mode="after")
    def not_an_approval(self):
        if self.policy.status != "DRAFT":
            raise ValueError("Policy activation requires independent governance and calibration, not a request flag")
        return self


class HumanReviewerAssignmentRequest(FrozenContract):
    run_id: NonEmpty
    reviewer_id: NonEmpty
    role: ReviewerRole
    dimensions: Annotated[tuple[HumanDimension, ...], Field(min_length=1, max_length=9)]
    interaction_reason: Text
    interaction_evidence: Annotated[tuple[HumanEvidenceReference, ...], Field(min_length=1, max_length=8)]
    interaction_attested: Literal[True]
    no_conflict_attested: Literal[True]
    expires_at: datetime

    _utc = field_validator("expires_at")(utc_time)

    @model_validator(mode="after")
    def scope(self):
        check_dimensions(self.role, self.dimensions)
        return self


class HumanReviewRequest(FrozenContract):
    observations: Annotated[tuple[HumanObservation, ...], Field(min_length=1, max_length=9)]
    no_conflict_attested: Literal[True]

    @model_validator(mode="after")
    def unique(self):
        if len({o.dimension for o in self.observations}) != len(self.observations):
            raise ValueError("One observation per assigned dimension is required")
        return self


class EligibleHumanReview(FrozenContract):
    """Internal resolved inputs; eligibility/validation cannot be supplied by API clients."""
    assignment_id: NonEmpty
    reviewer_id: NonEmpty
    role: ReviewerRole
    eligibility: Literal["ELIGIBLE", "REVOKED", "UNKNOWN"]
    observations: tuple[HumanObservation, ...]
    validated_dimensions: tuple[HumanDimension, ...] = ()

    @model_validator(mode="after")
    def scope(self):
        check_dimensions(self.role, [o.dimension for o in self.observations])
        return self


class HumanAggregation(FrozenContract):
    method_version: Literal["human-aggregation-v1"] = HUMAN_METHOD_VERSION
    status: Literal["POLICY_PENDING", "INCOMPLETE", "COMPLETE"]
    policy_id: str | None = None
    policy_version: str | None = None
    required_roles: tuple[ReviewerRole, ...] = ()
    submitted_roles: tuple[ReviewerRole, ...] = ()
    missing_requirements: tuple[str, ...]
    calculation: ScoreCalculation
    ceo_contribution: Literal[0] = 0
    is_finalizable: Literal[False] = False
