"""Versioned scoring contracts. Shape validation never establishes evidence authority."""

import math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from enum import Enum
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, computed_field, field_validator, model_validator


SCHEMA_VERSION = "performance-scoring-v1"
REGISTRY_VERSION = "performance-dimensions-v1"


def strict_decimal(value):
    if type(value) not in (int, float, Decimal):
        raise ValueError("A native finite number is required; coercion is not allowed")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("A finite number is required")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("A finite number is required")
    # A transport/resource bound, not an employee measurement threshold.
    if len(number.as_tuple().digits) > 1024 or abs(number.as_tuple().exponent) > 1024:
        raise ValueError("Numeric precision exceeds the supported transport bound")
    return number if number != 0 else Decimal(0)


Number = Annotated[Decimal, BeforeValidator(strict_decimal), PlainSerializer(float, return_type=float, when_used="json")]
def nonblank(value):
    if not value.strip():
        raise ValueError("Blank identifiers/reasons are not permitted")
    return value


NonEmpty = Annotated[str, Field(strict=True, min_length=1, max_length=500), AfterValidator(nonblank)]
Digest = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always", validate_default=True)


class ScoreUnit(str, Enum):
    PERIOD_0_100 = "PERIOD_0_100"
    LEGACY_AI_0_90 = "LEGACY_AI_0_90"
    PR_0_10 = "PR_0_10"
    ENGINEERING_CONTRIBUTION_0_90 = "ENGINEERING_CONTRIBUTION_0_90"
    HUMAN_CONTRIBUTION_0_10 = "HUMAN_CONTRIBUTION_0_10"


class ScoreValue(FrozenContract):
    unit: ScoreUnit
    value: Number

    @model_validator(mode="after")
    def unit_bounds(self):
        maximum = {ScoreUnit.PERIOD_0_100: 100, ScoreUnit.LEGACY_AI_0_90: 90, ScoreUnit.PR_0_10: 10,
                   ScoreUnit.ENGINEERING_CONTRIBUTION_0_90: 90, ScoreUnit.HUMAN_CONTRIBUTION_0_10: 10}[self.unit]
        if not 0 <= self.value <= maximum:
            raise ValueError(f"Score must be between 0 and {maximum} for {self.unit.value}")
        return self


class NormalizedLegacyAI(FrozenContract):
    """Lossless origin for a potentially repeating 90-to-100 conversion.

    The displayed value is derived. Exact composition uses the original
    contribution so Decimal approximation cannot move a half-cent boundary.
    """
    source: ScoreValue
    unit: Literal["PERIOD_0_100"] = "PERIOD_0_100"

    @model_validator(mode="before")
    @classmethod
    def discard_derived_display_value(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.pop("value", None)
        return value

    @model_validator(mode="after")
    def declared_origin(self):
        if self.source.unit != ScoreUnit.LEGACY_AI_0_90:
            raise ValueError("Conversion requires a declared LEGACY_AI_0_90 origin")
        return self

    @computed_field(return_type=Number)
    @property
    def value(self) -> Decimal:
        with localcontext() as context:
            context.prec = 50
            return self.source.value / Decimal(90) * Decimal(100)


def period_components(engineering: ScoreValue | NormalizedLegacyAI | None,
                      human: ScoreValue | None) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Exact shared arithmetic for already unit-validated period inputs."""
    exact_inputs = [item.source.value if isinstance(item, NormalizedLegacyAI) else item.value
                    for item in (engineering, human) if item is not None]
    with localcontext() as context:
        context.prec = max([50, *(len(value.as_tuple().digits) + abs(value.as_tuple().exponent) + 10
                                  for value in exact_inputs)])
        e = (engineering.source.value if isinstance(engineering, NormalizedLegacyAI)
             else engineering.value * Decimal("0.90") if engineering is not None else None)
        h = human.value * Decimal("0.10") if human is not None else None
        combined = ((e + h).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if e is not None and h is not None else None)
    return e, h, combined


class SubjectRole(str, Enum):
    DEVELOPER = "DEVELOPER"
    QA = "QA"
    DEVOPS = "DEVOPS"
    LEAD = "LEAD"
    PM = "PM"


class DimensionId(str, Enum):
    CODE_QUALITY = "code_quality"
    DELIVERY = "delivery"
    COLLABORATION = "collaboration"
    RELIABILITY = "reliability"
    ENGINEERING_IMPACT = "engineering_impact"
    ENGINEERING_JUDGMENT = "engineering_judgment"


class DimensionState(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ASSESSED = "NOT_ASSESSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    DISPUTED = "DISPUTED"
    INVALID = "INVALID"


class VersionReference(FrozenContract):
    id: NonEmpty
    version: NonEmpty


class SnapshotReference(FrozenContract):
    id: NonEmpty
    digest: Digest


class CoverageSummary(FrozenContract):
    """Reported coverage, never an inferred eligibility threshold or approval."""
    engineering_percent: Annotated[Number, Field(ge=0, le=100)] | None = None
    human_completeness: Literal["UNKNOWN", "INCOMPLETE", "COMPLETE"] = "UNKNOWN"
    policy: VersionReference | None = None


class AssessmentIdentity(FrozenContract):
    assessment_id: NonEmpty
    revision: Annotated[int, Field(strict=True, ge=1)]
    predecessor_digest: Digest | None = None
    organization_id: NonEmpty
    employee_id: NonEmpty
    employee_role_at_period: SubjectRole
    project_ids: tuple[NonEmpty, ...] = ()
    rubric_profile_id: NonEmpty
    period_start: datetime
    period_end: datetime
    timezone: Literal["UTC"] = "UTC"

    @field_validator("period_start", "period_end")
    @classmethod
    def utc_period(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Period boundaries must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("project_ids")
    @classmethod
    def normalized_scope(cls, value):
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def period_and_revision(self):
        if self.period_start >= self.period_end:
            raise ValueError("Period must be a nonempty half-open interval [start, end)")
        if (self.revision == 1) != (self.predecessor_digest is None):
            raise ValueError("Only a first revision may omit its predecessor digest")
        return self


class DimensionResult(FrozenContract):
    dimension_id: DimensionId
    state: DimensionState
    score: ScoreValue | None = None
    evidence_refs: tuple[NonEmpty, ...] = ()
    reason: NonEmpty | None = None
    measurement_rule: VersionReference | None = None

    @field_validator("evidence_refs")
    @classmethod
    def canonical_refs(cls, value):
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def observed_or_missing(self):
        if self.state == DimensionState.ELIGIBLE:
            if self.score is None or self.score.unit != ScoreUnit.PERIOD_0_100 or not self.evidence_refs:
                raise ValueError("Eligible dimensions require a PERIOD_0_100 score and evidence references")
        elif self.score is not None or self.reason is None:
            raise ValueError("Unassessed/inapplicable/disputed/invalid dimensions require a reason and null score")
        return self


class ScoreCalculation(FrozenContract):
    """Arithmetic output only: not an approved policy or employee assessment."""
    methodology: Literal["canonical-90-10-v1"] = "canonical-90-10-v1"
    formula: Literal["round_half_up(0.90 * E + 0.10 * H, 2)"] = "round_half_up(0.90 * E + 0.10 * H, 2)"
    engineering_score: ScoreValue | NormalizedLegacyAI | None
    human_score: ScoreValue | None
    combined_score: ScoreValue | None
    engineering_contribution: ScoreValue | None
    human_contribution: ScoreValue | None
    status: Literal["COMPLETE", "INCOMPLETE"]
    is_authoritative: Literal[False] = False

    @model_validator(mode="after")
    def replayable_calculation(self):
        expected_units = (
            (self.engineering_score, ScoreUnit.PERIOD_0_100),
            (self.human_score, ScoreUnit.PERIOD_0_100),
            (self.combined_score, ScoreUnit.PERIOD_0_100),
            (self.engineering_contribution, ScoreUnit.ENGINEERING_CONTRIBUTION_0_90),
            (self.human_contribution, ScoreUnit.HUMAN_CONTRIBUTION_0_10),
        )
        if any(value is not None and value.unit != unit for value, unit in expected_units):
            raise ValueError("Calculation fields must use their declared period/contribution units")
        expected = period_components(self.engineering_score, self.human_score)
        actual = tuple(item.value if item is not None else None for item in (
            self.engineering_contribution, self.human_contribution, self.combined_score))
        if actual != expected:
            raise ValueError("Calculation outputs must match the declared inputs and canonical formula")
        if self.status != ("COMPLETE" if expected[2] is not None else "INCOMPLETE"):
            raise ValueError("Calculation status must reflect component completeness")
        return self


class CalculationSnapshot(FrozenContract):
    """Immutable replay contract; references themselves are not proof of verification."""
    schema_version: Literal["performance-scoring-v1"] = SCHEMA_VERSION
    registry_version: Literal["performance-dimensions-v1"] = REGISTRY_VERSION
    identity: AssessmentIdentity
    methodology: VersionReference
    policy: VersionReference | None = None
    rubric: VersionReference | None = None
    evidence: SnapshotReference | None = None
    ai_output: SnapshotReference | None = None
    coverage: CoverageSummary = Field(default_factory=CoverageSummary)
    dimensions: tuple[DimensionResult, ...] = ()
    calculation: ScoreCalculation | None = None

    @field_validator("dimensions")
    @classmethod
    def canonical_dimensions(cls, value):
        if len({item.dimension_id for item in value}) != len(value):
            raise ValueError("Duplicate dimensions are not permitted")
        return tuple(sorted(value, key=lambda item: item.dimension_id.value))

    @model_validator(mode="after")
    def replayable_numbers(self):
        scores = [item.score for item in self.dimensions]
        if self.calculation:
            scores += [self.calculation.engineering_score, self.calculation.human_score, self.calculation.combined_score,
                       self.calculation.engineering_contribution, self.calculation.human_contribution]
        originals = [value.source if isinstance(value, NormalizedLegacyAI) else value for value in scores]
        numbers = [value.value for value in originals if value is not None]
        if self.coverage.engineering_percent is not None:
            numbers.append(self.coverage.engineering_percent)
        if any(Decimal(str(float(value))) != value for value in numbers):
            raise ValueError("Snapshot numbers must round-trip through JSON without precision loss")
        return self


class EvidenceKind(str, Enum):
    COMMIT = "commit"
    PR = "pr"
    REVIEW = "review"
    TASK = "task"
    STORY = "story"
    CI = "ci"
    TEST_RUN = "test_run"
    DEFECT = "defect"
    INCIDENT = "incident"
    BENCHMARK = "benchmark"
    DESIGN_RECORD = "design_record"
    HUMAN_OBSERVATION = "human_observation"
    ANALYSIS = "analysis"


class DimensionDefinition(FrozenContract):
    dimension_id: DimensionId
    score_unit: Literal["PERIOD_0_100"] = "PERIOD_0_100"
    evidence_kinds: tuple[EvidenceKind, ...]


class RubricDimension(FrozenContract):
    dimension_id: DimensionId
    weight: Annotated[Number, Field(ge=0, le=1)] | None = None
    measurement_rule: VersionReference | None = None
    required: bool | None = None


class RubricProfile(FrozenContract):
    id: NonEmpty
    version: NonEmpty
    registry_version: Literal["performance-dimensions-v1"] = REGISTRY_VERSION
    role: SubjectRole
    calibration_status: Literal["PENDING_CALIBRATION", "UNAVAILABLE"]
    dimensions: tuple[RubricDimension, ...] = ()
    coverage_policy: VersionReference | None = None
    reviewer_policy: VersionReference | None = None
    grade_policy: VersionReference | None = None
    is_finalizable: Literal[False] = False

    @model_validator(mode="after")
    def structurally_valid_draft(self):
        ids = [item.dimension_id for item in self.dimensions]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate rubric dimensions")
        weights = [item.weight for item in self.dimensions if item.weight is not None]
        if sum(weights) > 1 or (weights and len(weights) == len(ids) and sum(weights) != 1):
            raise ValueError("A complete dimension weight set must sum to 1")
        if self.calibration_status == "UNAVAILABLE" and self.dimensions:
            raise ValueError("Unavailable profiles cannot invent rubric dimensions")
        return self


class ShadowAssessment(FrozenContract):
    schema_version: Literal["performance-scoring-v1"] = SCHEMA_VERSION
    identity: AssessmentIdentity
    profile: RubricProfile
    dimensions: tuple[DimensionResult, ...]
    status: Literal["POLICY_PENDING", "RUBRIC_UNAVAILABLE"]
    engineering_score: None = None
    human_score: None = None
    combined_score: None = None
    coverage: CoverageSummary = Field(default_factory=CoverageSummary)
    is_finalizable: Literal[False] = False
    missing_requirements: tuple[NonEmpty, ...]


class AssessmentStatus(str, Enum):
    DRAFT = "DRAFT"
    EVIDENCE_COLLECTING = "EVIDENCE_COLLECTING"
    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    SCORING_ELIGIBLE = "SCORING_ELIGIBLE"
    PROVISIONAL = "PROVISIONAL"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class LegacyScoreUnits(FrozenContract):
    final_score: Literal["PERIOD_0_100"] = "PERIOD_0_100"
    ai_evaluation_score: Literal["LEGACY_AI_0_90"] = "LEGACY_AI_0_90"
    role_evaluation_contribution: Literal["HUMAN_CONTRIBUTION_0_10"] = "HUMAN_CONTRIBUTION_0_10"
    hr_normalized_score: Literal["PERIOD_0_100"] = "PERIOD_0_100"


class LegacyScoringMetadata(FrozenContract):
    schema_version: Literal["performance-scoring-v1"] = SCHEMA_VERSION
    mode: Literal["LEGACY_READ_ONLY"] = "LEGACY_READ_ONLY"
    status: Literal["LEGACY_UNVERIFIABLE"] = "LEGACY_UNVERIFIABLE"
    legacy_methodology_version: str | None = None
    legacy_human_policy_version: str | None = None
    source_units: LegacyScoreUnits = Field(default_factory=LegacyScoreUnits)
    engineering_score: None = None
    human_score: None = None
    combined_score: None = None
    approved_score: None = None
    snapshot: None = None
    rubric: None = None
    policy: None = None
    coverage: CoverageSummary = Field(default_factory=CoverageSummary)
    is_finalizable: Literal[False] = False
    limitations: tuple[str, ...] = (
        "Legacy values retain their original units and calculation semantics.",
        "A canonical evidence snapshot, calibrated rubric and independent approval are not established.",
    )


def legacy_scoring_metadata(methodology_version: str | None = None,
                            human_policy_version: str | None = None) -> LegacyScoringMetadata:
    return LegacyScoringMetadata(legacy_methodology_version=methodology_version,
                                 legacy_human_policy_version=human_policy_version)


def legacy_metadata_for_record(record) -> LegacyScoringMetadata:
    """Read only declared legacy versions, never caller-supplied scoring claims.

    Supports raw historical mappings and the existing typed response objects.
    Numeric inputs, evidence and sensitive HR observations are not copied here.
    """
    def field(value, name):
        return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
    version = field(field(record, "contribution_credit"), "methodology_version")
    human_version = field(record, "human_evaluation_policy_version")
    return legacy_scoring_metadata(version if isinstance(version, str) else None,
                                   human_version if isinstance(human_version, str) else None)
