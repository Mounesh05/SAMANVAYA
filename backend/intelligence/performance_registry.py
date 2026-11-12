"""Single canonical structural catalog. It is not a calibrated scoring policy."""

from types import MappingProxyType
from typing import Mapping

from domain.models.performance_scoring import (
    AssessmentIdentity, AssessmentStatus, DimensionDefinition, DimensionId, DimensionResult,
    EvidenceKind, REGISTRY_VERSION, RubricDimension, RubricProfile, ScoreUnit, ShadowAssessment, SubjectRole,
)


_DEFINITIONS = (
    DimensionDefinition(dimension_id="code_quality", evidence_kinds=("commit", "pr", "ci", "test_run", "analysis")),
    DimensionDefinition(dimension_id="delivery", evidence_kinds=("task", "story", "pr")),
    DimensionDefinition(dimension_id="collaboration", evidence_kinds=("review", "human_observation")),
    DimensionDefinition(dimension_id="reliability", evidence_kinds=("ci", "test_run", "defect", "incident")),
    DimensionDefinition(dimension_id="engineering_impact", evidence_kinds=("benchmark", "pr", "design_record")),
    DimensionDefinition(dimension_id="engineering_judgment", evidence_kinds=("design_record", "pr", "human_observation")),
)
if len(_DEFINITIONS) != len(DimensionId) or {item.dimension_id for item in _DEFINITIONS} != set(DimensionId):
    raise RuntimeError("Canonical dimension model and registry disagree")
DIMENSIONS = MappingProxyType({item.dimension_id: item for item in _DEFINITIONS})


def get_rubric_profile(role: SubjectRole | str) -> RubricProfile:
    subject_role = SubjectRole(role)
    developer = subject_role == SubjectRole.DEVELOPER
    return RubricProfile(id="developer-candidate-v1" if developer else f"{subject_role.value.lower()}-pending-v1",
        version="1", role=subject_role, calibration_status="PENDING_CALIBRATION" if developer else "UNAVAILABLE",
        dimensions=tuple(RubricDimension(dimension_id=key) for key in DIMENSIONS) if developer else ())


def canonical_scoring_contract() -> dict:
    """Fresh schema metadata for future validators/advisory prompt labels.

    Evidence kinds identify potentially relevant source types, not proof of a
    claim. Model prompts must never treat this as permission to award points.
    """
    return {"registry_version": REGISTRY_VERSION, "score_units": [unit.value for unit in ScoreUnit],
        "dimension_ids": [key.value for key in DIMENSIONS],
        "dimensions": {key.value: definition.model_dump(mode="json") for key, definition in DIMENSIONS.items()},
        "dimension_result_schema": DimensionResult.model_json_schema(),
        "roles": {role.value: get_rubric_profile(role).model_dump(mode="json") for role in SubjectRole}}


def validate_dimension_results(results: tuple[DimensionResult, ...],
                               source_kinds: Mapping[str, str | EvidenceKind] | None = None) -> tuple[DimensionResult, ...]:
    values = tuple(DimensionResult.model_validate(item) for item in results)
    if len({item.dimension_id for item in values}) != len(values):
        raise ValueError("Duplicate dimensions are not permitted")
    for item in values:
        definition = DIMENSIONS[item.dimension_id]
        if source_kinds is not None:
            for reference in item.evidence_refs:
                if reference not in source_kinds:
                    raise ValueError("An evidence reference is absent from the supplied source map")
                if EvidenceKind(source_kinds[reference]) not in definition.evidence_kinds:
                    raise ValueError("Source kind is not structurally relevant to this dimension")
    return tuple(sorted(values, key=lambda item: item.dimension_id.value))


def prepare_shadow_assessment(identity: AssessmentIdentity, dimensions: tuple[DimensionResult, ...]) -> ShadowAssessment:
    subject = AssessmentIdentity.model_validate(identity)
    profile = get_rubric_profile(subject.employee_role_at_period)
    if subject.rubric_profile_id != profile.id:
        raise ValueError("Assessment identity and rubric profile do not match")
    values = validate_dimension_results(dimensions)
    if any(item.dimension_id not in {d.dimension_id for d in profile.dimensions} for item in values):
        raise ValueError("Dimension is not configured for this subject role")
    return ShadowAssessment(identity=subject, profile=profile, dimensions=values,
        status="RUBRIC_UNAVAILABLE" if profile.calibration_status == "UNAVAILABLE" else "POLICY_PENDING",
        missing_requirements=("Calibrated role rubric and measurement rules", "Approved evidence/coverage policy",
                              "Eligible reviewer policy and complete reviews", "Independent approval workflow"))


_TRANSITIONS = MappingProxyType({
    "DRAFT": frozenset({"EVIDENCE_COLLECTING", "CANCELLED"}),
    "EVIDENCE_COLLECTING": frozenset({"EVIDENCE_VALIDATED", "INSUFFICIENT_EVIDENCE", "CANCELLED"}),
    "EVIDENCE_VALIDATED": frozenset({"SCORING_ELIGIBLE", "INSUFFICIENT_EVIDENCE", "UNDER_REVIEW"}),
    "SCORING_ELIGIBLE": frozenset({"PROVISIONAL", "UNDER_REVIEW"}),
    "PROVISIONAL": frozenset({"UNDER_REVIEW", "DISPUTED"}),
    "UNDER_REVIEW": frozenset({"APPROVED", "DISPUTED", "REJECTED"}),
    "APPROVED": frozenset({"SUPERSEDED", "DISPUTED"}),
    "INSUFFICIENT_EVIDENCE": frozenset({"EVIDENCE_COLLECTING", "CANCELLED"}),
    "DISPUTED": frozenset({"UNDER_REVIEW", "CANCELLED"}),
    "REJECTED": frozenset(), "SUPERSEDED": frozenset(), "CANCELLED": frozenset(),
})


def validate_transition(current: AssessmentStatus | str, target: AssessmentStatus | str) -> None:
    """Validate adjacency only; callers still need scope, eligibility and approval guards."""
    before, after = AssessmentStatus(current), AssessmentStatus(target)
    if after.value not in _TRANSITIONS[before.value]:
        raise ValueError(f"Transition {before.value} -> {after.value} is not structurally permitted")
