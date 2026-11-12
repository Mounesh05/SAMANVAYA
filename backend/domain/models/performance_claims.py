"""Strict advisory proposals, narrow validated facts and signed review contracts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, field_validator, model_validator

from domain.models.performance_evidence import Count, EvidencePreview, utc_time
from domain.models.performance_scoring import Digest, DimensionId, FrozenContract, NonEmpty, nonblank

PROTECTED_RUN_TYPES = ("performance_interpretation", "performance_claim_assignment", "performance_claim_review",
    "performance_human_assignment", "performance_human_review", "performance_human_policy_draft")

ClaimType = Literal["recorded_status", "recorded_test_outcome", "possible_regression_fixed",
    "possible_benchmark_improvement", "possible_architecture_tradeoff", "possible_mentoring_contribution",
    "possible_substantive_review"]
Text = Annotated[str, Field(strict=True, min_length=1, max_length=2000), AfterValidator(nonblank)]
ClaimId = Annotated[str, Field(strict=True, pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class Citation(FrozenContract):
    source_id: Digest
    content_digest: Digest


class ClaimProposal(FrozenContract):
    claim_id: ClaimId
    claim_type: ClaimType
    dimension_id: DimensionId
    citations: Annotated[tuple[Citation, ...], Field(min_length=1, max_length=8)]
    expected_status: Literal["todo", "in_progress", "review", "done", "completed", "closed", "resolved", "blocked",
        "open", "merged", "passed", "failed", "error", "cancelled", "skipped", "unknown", "assigned", "fixed",
        "ready_for_retest", "reopened"] | None = None
    test_outcome: Literal["PASSED", "FAILED", "NO_EXECUTED_TESTS"] | None = None
    tests_passed: Count | None = None
    tests_failed: Count | None = None
    tests_skipped: Count | None = None
    interpretation: Text

    @model_validator(mode="after")
    def predicate_shape(self):
        refs = [(c.source_id, c.content_digest) for c in self.citations]
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate citations do not establish independent support")
        test_values = (self.test_outcome, self.tests_passed, self.tests_failed, self.tests_skipped)
        if self.claim_type == "recorded_status":
            if self.expected_status is None or any(v is not None for v in test_values):
                raise ValueError("Status claims require only an explicit status predicate")
        elif self.claim_type == "recorded_test_outcome":
            if self.expected_status is not None or any(v is None for v in test_values):
                raise ValueError("Test outcome claims require complete explicit test predicates")
        elif self.expected_status is not None or any(v is not None for v in test_values):
            raise ValueError("Qualitative proposals cannot inject measurement predicates")
        return self


class ProposalPayload(FrozenContract):
    schema_version: Literal["performance-claims-v1"] = "performance-claims-v1"
    claims: Annotated[tuple[ClaimProposal, ...], Field(max_length=16)]

    @model_validator(mode="after")
    def distinct_claims(self):
        if len({c.claim_id for c in self.claims}) != len(self.claims):
            raise ValueError("Duplicate claim identities")
        return self


class ValidatedClaimFact(FrozenContract):
    predicate: Literal["recorded_status", "recorded_test_outcome", "qualified_review_attestation"]
    recorded_status: str | None = None
    test_outcome: Literal["PASSED", "FAILED", "NO_EXECUTED_TESTS"] | None = None
    tests_passed: Count | None = None
    tests_failed: Count | None = None
    tests_skipped: Count | None = None
    citations: tuple[Citation, ...]
    snapshot_digest: Digest
    attested_claim_digest: Digest | None = None
    is_performance_credit: Literal[False] = False


class ClaimValidation(FrozenContract):
    claim_id: ClaimId
    status: Literal["VALIDATED", "REJECTED", "NEEDS_REVIEW"]
    reasons: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    method: Literal["performance-claim-validator-v1"] = "performance-claim-validator-v1"
    fact: ValidatedClaimFact | None = None
    score_effect: None = None

    @model_validator(mode="after")
    def validated_predicate_only(self):
        if (self.status == "VALIDATED") != (self.fact is not None):
            raise ValueError("Only a validated predicate can emit a typed fact")
        return self


class Interpretation(FrozenContract):
    model_config = {"protected_namespaces": ()}
    schema_version: Literal["performance-interpretation-v1"] = "performance-interpretation-v1"
    status: Literal["COMPLETED", "UNAVAILABLE", "INVALID_OUTPUT", "NO_EVIDENCE"]
    snapshot_digest: Digest
    proposal: ProposalPayload | None = None
    decisions: tuple[ClaimValidation, ...] = ()
    model_provider: Literal["ollama"] = "ollama"
    model_id: NonEmpty
    model_version: None = None
    prompt_version: Literal["performance-claims-prompt-v1"] = "performance-claims-prompt-v1"
    prompt_digest: Digest | None = None
    model_output_digest: Digest | None = None
    limitations: tuple[NonEmpty, ...] = ("MODEL_TEXT_IS_UNVERIFIED_ADVISORY_CONTENT", "NO_NUMERIC_SCORING_AUTHORITY",
        "MODEL_ARTIFACT_VERSION_NOT_ESTABLISHED", "SNAPSHOT_NOT_A_FINAL_ASSESSMENT_APPROVAL")
    engineering_score: None = None
    human_score: None = None
    combined_score: None = None
    is_authoritative: Literal[False] = False

    @model_validator(mode="after")
    def traceable_outcome(self):
        if self.status == "COMPLETED":
            if self.proposal is None or self.prompt_digest is None or self.model_output_digest is None:
                raise ValueError("Completed interpretations require a proposal and prompt/output provenance")
            if [d.claim_id for d in self.decisions] != [c.claim_id for c in self.proposal.claims]:
                raise ValueError("Every proposal requires exactly one corresponding validation decision")
            if any(d.fact and d.fact.snapshot_digest != self.snapshot_digest for d in self.decisions):
                raise ValueError("Validated facts must reference this exact snapshot")
        elif self.proposal is not None or self.decisions:
            raise ValueError("Unavailable, invalid or empty-source interpretations cannot emit validated claims")
        return self


class InterpretationRun(FrozenContract):
    run_id: NonEmpty
    evidence: EvidencePreview
    interpretation: Interpretation
    created_at: datetime
    created_by: NonEmpty

    @model_validator(mode="after")
    def exact_evidence(self):
        if self.interpretation.snapshot_digest != self.evidence.digest:
            raise ValueError("Interpretation must reference its exact evidence snapshot")
        return self


class ReviewerAssignmentRequest(FrozenContract):
    reviewer_id: NonEmpty
    project_id: NonEmpty
    dimensions: Annotated[tuple[DimensionId, ...], Field(min_length=1, max_length=6)]
    claim_types: Annotated[tuple[ClaimType, ...], Field(min_length=1, max_length=7)]
    qualification_reason: Text
    qualification_source_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1, max_length=8)]
    qualification_attested: Annotated[bool, Field(strict=True)]
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value):
        return utc_time(value)

    @model_validator(mode="after")
    def explicit_qualification(self):
        if self.qualification_attested is not True:
            raise ValueError("Explicit qualification attestation is required; role alone is insufficient")
        return self


class ClaimReviewRequest(FrozenContract):
    assignment_id: NonEmpty
    expected_snapshot_digest: Digest
    expected_proposal_digest: Digest
    previous_review_digest: Digest | None = None
    decision: Literal["VALIDATE", "REJECT"]
    reason: Text
    attribution_checked: Annotated[bool, Field(strict=True)] = False
    predicate_checked: Annotated[bool, Field(strict=True)] = False


class ClaimReview(FrozenContract):
    review_id: NonEmpty
    run_id: NonEmpty
    claim_id: ClaimId
    revision: Annotated[int, Field(strict=True, ge=1, le=100)]
    previous_review_digest: Digest | None
    assignment_id: NonEmpty
    reviewer_id: NonEmpty
    snapshot_digest: Digest
    proposal_digest: Digest
    decision: Literal["VALIDATE", "REJECT"]
    reason: Text
    reviewed_at: datetime
    fact: ValidatedClaimFact | None
    score_effect: None = None
    is_final_assessment_approval: Literal[False] = False


class InterpretationDetails(FrozenContract):
    run: InterpretationRun
    reviews: tuple[ClaimReview, ...]
    effective_decisions: tuple[ClaimValidation, ...]
    facts_for_measurement: tuple[()] = ()
