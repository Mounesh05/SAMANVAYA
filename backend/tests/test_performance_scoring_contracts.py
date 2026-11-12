"""Canonical contracts/arithmetic; examples are not approved employee rubrics."""

import importlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError


def models():
    return importlib.import_module("domain.models.performance_scoring")


def engine():
    return importlib.import_module("intelligence.performance_scoring")


def score(value, unit="PERIOD_0_100"):
    return models().ScoreValue(value=value, unit=unit)


def identity(**overrides):
    fields = dict(assessment_id="ASSESSMENT-1", revision=1, organization_id="ORG-1", employee_id="EMP-1",
        employee_role_at_period="DEVELOPER", project_ids=("P2", "P1"), rubric_profile_id="developer-candidate-v1",
        period_start=datetime(2026, 7, 1, tzinfo=timezone.utc), period_end=datetime(2026, 10, 1, tzinfo=timezone.utc))
    return models().AssessmentIdentity(**{**fields, **overrides})


def snapshot(**overrides):
    m = models()
    fields = dict(identity=identity(), methodology=m.VersionReference(id="canonical-90-10", version="1"),
        policy=m.VersionReference(id="test-policy-not-production", version="1"),
        rubric=m.VersionReference(id="test-rubric-not-production", version="1"),
        evidence=m.SnapshotReference(id="EV-1", digest="a" * 64), dimensions=(m.DimensionResult(
            dimension_id="code_quality", state="ELIGIBLE", score=score(86), evidence_refs=("commit:c1",)),))
    return m.CalculationSnapshot(**{**fields, **overrides})


def test_worked_example_has_one_weighting_pass_and_explicit_contributions():
    result = engine().combine_scores(score(86), score(80))
    assert result.combined_score.value == Decimal("85.4")
    assert result.engineering_contribution.value == Decimal("77.4")
    assert result.human_contribution.value == Decimal("8")
    assert result.status == "COMPLETE" and result.is_authoritative is False
    assert result.model_dump(mode="json")["combined_score"]["value"] == 85.4


@pytest.mark.parametrize("changes", [
    {"engineering_score": {"unit": "PR_0_10", "value": 8}},
    {"human_score": {"unit": "LEGACY_AI_0_90", "value": 80}},
    {"combined_score": {"unit": "PR_0_10", "value": 8}},
    {"engineering_contribution": {"unit": "PERIOD_0_100", "value": 77.4}},
    {"human_contribution": {"unit": "PERIOD_0_100", "value": 8}},
    {"human_score": None}, {"combined_score": None}, {"engineering_contribution": None},
    {"status": "INCOMPLETE"},
    {"combined_score": {"unit": "PERIOD_0_100", "value": 100}},
    {"engineering_contribution": {"unit": "ENGINEERING_CONTRIBUTION_0_90", "value": 70}},
    {"human_contribution": {"unit": "HUMAN_CONTRIBUTION_0_10", "value": 9}},
])
def test_direct_and_json_calculation_contracts_reject_unreplayable_results(changes):
    calculation = engine().combine_scores(score(86), score(80)).model_dump(mode="json")
    calculation.update(changes)
    with pytest.raises(ValidationError):
        models().ScoreCalculation.model_validate(calculation)
    with pytest.raises(ValidationError):
        models().ScoreCalculation.model_validate_json(json.dumps(calculation))
    saved = snapshot().model_dump(mode="json")
    saved["calculation"] = calculation
    with pytest.raises(ValidationError):
        models().CalculationSnapshot.model_validate_json(json.dumps(saved))


def test_snapshot_digest_revalidates_constructed_calculations():
    valid = engine().combine_scores(score(86), score(80)).model_dump(mode="python")
    invalid = models().ScoreCalculation.model_construct(**{**valid, "human_score": None})
    forged = models().CalculationSnapshot.model_construct(**{**snapshot().model_dump(mode="python"), "calculation": invalid})
    with pytest.raises(ValidationError):
        engine().snapshot_digest(forged)


def test_legacy_conversion_is_explicit_and_does_not_double_discount():
    converted = engine().normalize_legacy_ai_contribution(score(77.4, "LEGACY_AI_0_90"))
    assert converted.value == 86 and converted.unit == "PERIOD_0_100"
    assert engine().combine_scores(converted, score(80)).combined_score.value == Decimal("85.4")


def test_repeating_legacy_conversion_preserves_source_before_final_rounding():
    converted = engine().normalize_legacy_ai_contribution(score(Decimal("77.405"), "LEGACY_AI_0_90"))
    result = engine().combine_scores(converted, score(80))
    assert result.engineering_contribution.value == Decimal("77.405")
    assert result.combined_score.value == Decimal("85.41")
    saved = snapshot(calculation=result)
    restored = models().CalculationSnapshot.model_validate_json(saved.model_dump_json())
    assert engine().snapshot_digest(restored) == engine().snapshot_digest(saved)


def test_pathological_decimal_precision_is_rejected_before_calculation():
    with pytest.raises(ValidationError):
        score(Decimal("1e-1000000000"))


def test_legacy_origin_precision_is_retained_at_a_rounding_boundary():
    source = Decimal("77.404" + "9" * 200)
    converted = engine().normalize_legacy_ai_contribution(score(source, "LEGACY_AI_0_90"))
    assert engine().combine_scores(converted, score(80)).combined_score.value == Decimal("85.40")


def test_normalized_display_cannot_override_its_declared_origin():
    converted = models().NormalizedLegacyAI.model_validate({"source": score(77.4, "LEGACY_AI_0_90"), "value": 100})
    assert converted.value == 86
    assert engine().combine_scores(converted, score(80)).combined_score.value == Decimal("85.4")
    with pytest.raises(ValidationError):
        models().NormalizedLegacyAI(source=score(77.4))


def test_coverage_contract_preserves_unknowns_without_inventing_thresholds():
    coverage = models().CoverageSummary()
    assert coverage.engineering_percent is None and coverage.human_completeness == "UNKNOWN"
    assert coverage.policy is None
    assert snapshot().coverage == coverage
    shadow = registry().prepare_shadow_assessment(identity(), ())
    assert shadow.coverage == coverage and shadow.combined_score is None
    for bad in (True, "80", -1, 101, float("nan")):
        with pytest.raises(ValidationError):
            models().CoverageSummary(engineering_percent=bad)


@pytest.mark.parametrize("unit", ["PR_0_10", "LEGACY_AI_0_90", "HUMAN_CONTRIBUTION_0_10"])
def test_period_calculation_rejects_other_score_families(unit):
    with pytest.raises(ValueError, match="PERIOD_0_100"):
        engine().combine_scores(score(8, unit), score(80))


def test_conversion_rejects_an_unlabeled_or_wrong_family_input():
    with pytest.raises(ValidationError):
        models().ScoreValue(value=77.4)
    with pytest.raises(ValueError):
        engine().normalize_legacy_ai_contribution(score(8, "PR_0_10"))


@pytest.mark.parametrize("bad", [True, False, "86", None, -1, 101, float("nan"), float("inf"), Decimal("NaN")])
def test_scores_reject_coercion_nonfinite_and_out_of_range(bad):
    with pytest.raises(ValidationError):
        score(bad)


@pytest.mark.parametrize("unit,bad", [("PR_0_10", 11), ("LEGACY_AI_0_90", 91),
                                     ("ENGINEERING_CONTRIBUTION_0_90", 91), ("HUMAN_CONTRIBUTION_0_10", 11)])
def test_unit_specific_bounds_are_enforced(unit, bad):
    with pytest.raises(ValidationError):
        score(bad, unit)


@pytest.mark.parametrize("engineering,human", [(None, 80), (86, None), (None, None)])
def test_missing_components_remain_null_without_weight_normalization(engineering, human):
    result = engine().combine_scores(score(engineering) if engineering is not None else None,
                                     score(human) if human is not None else None)
    assert result.combined_score is None and result.status == "INCOMPLETE"
    if human is None:
        assert result.human_score is None and result.human_contribution is None
    if engineering is not None:
        assert result.engineering_contribution.value == Decimal("77.4")


def test_rounding_is_decimal_half_up_once_after_addition():
    result = engine().combine_scores(score(Decimal("0.05")), score(0))
    assert result.engineering_contribution.value == Decimal("0.045")
    assert result.combined_score.value == Decimal("0.05")


def test_invalid_model_construct_cannot_bypass_the_calculator_boundary():
    invalid = models().ScoreValue.model_construct(unit="PERIOD_0_100", value=float("nan"))
    with pytest.raises(ValidationError):
        engine().combine_scores(invalid, score(80))


@pytest.mark.parametrize("change", [dict(period_start=datetime(2026, 7, 1)),
    dict(period_end=datetime(2026, 7, 1, tzinfo=timezone.utc)), dict(revision=True),
    dict(revision=2), dict(employee_role_at_period="CEO"), dict(employee_role_at_period="HR")])
def test_assessment_identity_rejects_ambiguous_period_or_revision(change):
    with pytest.raises(ValidationError):
        identity(**change)


def test_identity_normalizes_utc_scope_and_requires_revision_lineage():
    start = datetime(2026, 7, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    value = identity(period_start=start, revision=2, predecessor_digest="b" * 64)
    assert value.period_start == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert value.project_ids == ("P1", "P2")
    with pytest.raises(ValidationError):
        identity(revision=1, predecessor_digest="b" * 64)


def test_snapshot_is_nested_immutable_roundtrippable_and_hash_stable():
    value = snapshot()
    with pytest.raises(ValidationError):
        value.identity.employee_id = "OTHER"
    with pytest.raises(ValidationError):
        value.dimensions[0].score.value = 0
    restored = models().CalculationSnapshot.model_validate_json(value.model_dump_json())
    assert engine().snapshot_digest(restored) == engine().snapshot_digest(value)
    assert len(engine().snapshot_digest(value)) == 64
    other = snapshot(identity=identity(employee_id="OTHER"))
    assert engine().snapshot_digest(other) != engine().snapshot_digest(value)


def test_ineligible_dimensions_cannot_smuggle_numeric_scores():
    with pytest.raises(ValidationError):
        models().DimensionResult(dimension_id="code_quality", state="NOT_ASSESSED", score=score(0), reason="No evidence")
    with pytest.raises(ValidationError):
        models().DimensionResult(dimension_id="code_quality", state="ELIGIBLE", score=score(86))
    result = models().DimensionResult(dimension_id="code_quality", state="NOT_ASSESSED", reason="Connector unavailable")
    assert result.score is None


def registry():
    return importlib.import_module("intelligence.performance_registry")


def test_registry_drives_schema_and_generated_contract_without_dimension_drift():
    contract = registry().canonical_scoring_contract()
    schema_ids = set(models().DimensionResult.model_json_schema()["$defs"]["DimensionId"]["enum"])
    assert set(contract["dimension_ids"]) == schema_ids
    assert set(contract["dimensions"]) == schema_ids
    assert "innovation" not in schema_ids and "technical_design" not in schema_ids
    contract["dimensions"]["code_quality"]["evidence_kinds"].append("invented")
    assert "invented" not in registry().canonical_scoring_contract()["dimensions"]["code_quality"]["evidence_kinds"]


@pytest.mark.parametrize("role", ["DEVELOPER", "QA", "DEVOPS", "LEAD", "PM"])
def test_no_role_profile_fabricates_weights_or_allows_finalization(role):
    profile = registry().get_rubric_profile(role)
    assert profile.is_finalizable is False
    assert all(d.weight is None and d.measurement_rule is None for d in profile.dimensions)
    if role != "DEVELOPER":
        assert profile.calibration_status == "UNAVAILABLE" and profile.dimensions == ()
    with pytest.raises(ValidationError):
        profile.is_finalizable = True


def test_draft_profile_cannot_be_approved_by_an_input_flag():
    profile = registry().get_rubric_profile("DEVELOPER").model_dump(mode="python")
    with pytest.raises(ValidationError):
        models().RubricProfile.model_validate({**profile, "calibration_status": "APPROVED", "is_finalizable": True})


@pytest.mark.parametrize("role", ["CEO", "HR", "UNKNOWN"])
def test_nonengineering_subject_profiles_are_not_created(role):
    with pytest.raises(ValueError):
        registry().get_rubric_profile(role)


def test_structural_validation_rejects_duplicates_unknown_sources_and_wrong_kinds():
    result = models().DimensionResult(dimension_id="code_quality", state="ELIGIBLE", score=score(86), evidence_refs=("commit:c1",))
    assert registry().validate_dimension_results((result,), {"commit:c1": "commit"}) == (result,)
    with pytest.raises(ValueError, match="Duplicate"):
        registry().validate_dimension_results((result, result))
    for kinds in [{}, {"commit:c1": "unknown"}, {"commit:c1": "human_observation"}]:
        with pytest.raises(ValueError):
            registry().validate_dimension_results((result,), kinds)
    with pytest.raises(ValidationError):
        models().DimensionResult(dimension_id="invented", state="NOT_ASSESSED", reason="unknown")


def test_shadow_assessment_preserves_observations_without_promoting_an_unapproved_policy():
    dimension = models().DimensionResult(dimension_id="code_quality", state="ELIGIBLE", score=score(86), evidence_refs=("commit:c1",))
    result = registry().prepare_shadow_assessment(identity(), (dimension,))
    assert result.status == "POLICY_PENDING" and result.dimensions == (dimension,)
    assert result.engineering_score is None and result.human_score is None and result.combined_score is None
    assert result.is_finalizable is False and result.missing_requirements
    with pytest.raises(ValidationError):
        models().ShadowAssessment.model_validate({**result.model_dump(mode="python"), "combined_score": score(85.4)})
    with pytest.raises(ValueError):
        registry().prepare_shadow_assessment(identity(rubric_profile_id="different-policy"), (dimension,))


def test_structural_state_machine_is_not_an_approval_shortcut():
    registry().validate_transition("DRAFT", "EVIDENCE_COLLECTING")
    with pytest.raises(ValueError):
        registry().validate_transition("DRAFT", "APPROVED")
    with pytest.raises(ValueError):
        registry().validate_transition("APPROVED", "DRAFT")


def test_snapshot_rejects_unreplayable_precision_and_is_order_independent():
    m = models()
    quality = m.DimensionResult(dimension_id="code_quality", state="ELIGIBLE", score=score(86), evidence_refs=("b", "a"))
    delivery = m.DimensionResult(dimension_id="delivery", state="NOT_ASSESSED", reason="No collection")
    first = snapshot(dimensions=(quality, delivery))
    reordered_quality = m.DimensionResult(dimension_id="code_quality", state="ELIGIBLE", score=score(86.0), evidence_refs=("a", "b"))
    second = snapshot(dimensions=(delivery, reordered_quality))
    assert engine().snapshot_digest(first) == engine().snapshot_digest(second)
    with pytest.raises(ValidationError):
        snapshot(dimensions=(m.DimensionResult(dimension_id="code_quality", state="ELIGIBLE",
            score=score(Decimal("86.000000000000000001")), evidence_refs=("commit:c1",)),))
