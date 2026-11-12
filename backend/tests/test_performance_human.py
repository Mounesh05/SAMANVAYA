"""Synthetic approved policy fixtures test mechanics, never production calibration."""

from decimal import Decimal
import importlib

import pytest
from pydantic import ValidationError


def contracts():
    assert importlib.util.find_spec("domain.models.performance_human"), "Phase 4 human contracts are missing"
    return importlib.import_module("domain.models.performance_human")


def policy(**changes):
    m = contracts()
    anchors = [{"rating": n, "score": n * 20, "description": f"Synthetic anchor {n}",
                "evidence_required": n in (1, 2, 5)} for n in range(1, 6)]
    return m.HumanPolicy(**{**dict(policy_id="synthetic", version="test-only", subject_role="DEVELOPER",
        status="APPROVED", roles=[{"role": r, "weight": Decimal("0.5"), "dimensions": [
            {"dimension": d, "weight": 1, "anchors": anchors}]} for r, d in
            (("LEAD", "collaboration"), ("HR", "professional_conduct"))]), **changes})


def review(role="LEAD", **changes):
    m = contracts()
    dimension = "professional_conduct" if role == "HR" else "collaboration"
    return m.EligibleHumanReview(**{**dict(reviewer_id=role, role=role, assignment_id=role,
        eligibility="ELIGIBLE", observations=[dict(dimension=dimension, state="OBSERVED", rating=4,
        reason="Personally observed in the assessed period", evidence=[dict(source_reference="task:synthetic",
        source_revision="v1", observed_at="2026-08-01T00:00:00Z")], direct_observation=True)],
        validated_dimensions=[dimension]), **changes})


def aggregate(p=None, reviews=None, engineering=86):
    from domain.models.performance_scoring import ScoreValue
    from intelligence.performance_human import aggregate_human_reviews
    e = ScoreValue(unit="PERIOD_0_100", value=engineering) if engineering is not None else None
    return aggregate_human_reviews(p or policy(), tuple(reviews if reviews is not None else [review(), review("HR")]), e)


def test_phase4_has_strict_human_contracts():
    assert contracts().HumanPolicy


def test_complete_approved_policy_uses_canonical_ninety_ten_once():
    result = aggregate()
    assert result.calculation.human_score.value == 80
    assert result.calculation.combined_score.value == Decimal("85.40")
    assert result.status == "COMPLETE" and result.is_finalizable is False


@pytest.mark.parametrize("reviews", [[], ["LEAD"], ["HR"]])
def test_missing_roles_never_renormalize_available_reviewers(reviews):
    policy()
    result = aggregate(reviews=[review(r) for r in reviews])
    assert result.calculation.human_score is None and result.calculation.combined_score is None
    assert result.missing_requirements and result.status == "INCOMPLETE"


@pytest.mark.parametrize("state", ["NOT_OBSERVED", "NOT_APPLICABLE", "UNDER_REVIEW"])
def test_nonobserved_states_have_reasons_and_never_become_neutral_or_change_denominator(state):
    m = contracts()
    observation = m.HumanObservation(dimension="professional_conduct", state=state, reason="No established observation")
    result = aggregate(reviews=[review(), review("HR", observations=[observation])])
    assert result.calculation.human_score is None
    with pytest.raises(ValidationError):
        m.HumanObservation(dimension="professional_conduct", state=state, reason="No observation", rating=3)


def test_draft_policy_and_unvalidated_evidence_cannot_produce_human_scores():
    result = aggregate(p=policy(status="DRAFT"))
    assert result.status == "POLICY_PENDING" and result.calculation.human_score is None
    result = aggregate(reviews=[review(validated_dimensions=[]), review("HR")])
    assert result.calculation.human_score is None and result.missing_requirements


def test_duplicate_roles_and_ineligible_reviews_block_instead_of_amplify():
    result = aggregate(reviews=[review(), review(), review("HR")])
    assert result.calculation.human_score is None
    result = aggregate(reviews=[review(eligibility="REVOKED"), review("HR")])
    assert result.calculation.human_score is None


def test_no_engineering_measurement_leaves_final_score_null():
    result = aggregate(engineering=None)
    assert result.calculation.human_score.value == 80 and result.calculation.combined_score is None
    assert result.status == "INCOMPLETE"


def test_ceo_and_hr_technical_scoring_are_not_supported_policy_dimensions():
    m = contracts()
    body = policy().model_dump()
    body["roles"][0]["role"] = "CEO"
    with pytest.raises(ValidationError):
        m.HumanPolicy(**body)
    body = policy().model_dump()
    body["roles"][1]["dimensions"][0]["dimension"] = "collaboration"
    with pytest.raises(ValidationError):
        m.HumanPolicy(**body)
    body = policy().model_dump()
    body["roles"][0]["weight"] = Decimal("0.49")
    with pytest.raises(ValidationError):
        m.HumanPolicy(**body)


@pytest.mark.parametrize("rating", [True, "4", 4.0, 0, 6])
def test_ratings_are_native_integers(rating):
    m = contracts()
    with pytest.raises(ValidationError):
        m.HumanObservation(dimension="collaboration", state="OBSERVED", rating=rating,
                           direct_observation=True, reason="Observed", evidence=[dict(
                               source_reference="task:x", source_revision="v1", observed_at="2026-08-01T00:00:00Z")])


def test_observed_needs_actual_references_not_comment_length():
    m = contracts()
    with pytest.raises(ValidationError):
        m.HumanObservation(dimension="collaboration", state="OBSERVED", rating=1,
                           direct_observation=True, reason="x" * 2000, evidence=[])


def test_ordinary_and_hr_orchestrators_use_the_same_result():
    from domain.services.performance_service import PerformanceService
    from domain.services.hr_performance_service import HRPerformanceService
    p = policy()
    from domain.models.performance_scoring import ScoreValue
    e = ScoreValue(unit="PERIOD_0_100", value=86)
    rows = (review(), review("HR"))
    ordinary = PerformanceService.compose_human_reviews(p, rows, e)
    hr = HRPerformanceService.compose_human_reviews(p, rows, e)
    assert ordinary == hr and hr.calculation.combined_score.value == Decimal("85.40")


def test_no_intermediate_rounding_of_human_score():
    m = contracts()
    data = policy().model_dump()
    for role in data["roles"]:
        for anchor in role["dimensions"][0]["anchors"]:
            if anchor["rating"] == 4:
                anchor["score"] = Decimal("80.049")
    result = aggregate(p=m.HumanPolicy(**data))
    assert result.calculation.human_score.value == Decimal("80.049")
    assert result.calculation.combined_score.value == Decimal("85.40")


def test_policy_draft_cannot_smuggle_an_approved_status_or_measurements():
    m = contracts()
    with pytest.raises(ValidationError):
        m.HumanPolicyDraftRequest(project_id="P", reason="Proposed", policy=policy())
    with pytest.raises(ValidationError):
        m.HumanReviewRequest(observations=review().observations, no_conflict_attested=True,
                             engineering_score=100, validated_dimensions=["collaboration"])


def test_explicit_four_point_hr_scale_does_not_inherit_five_point_normalization():
    m = contracts()
    data = policy().model_dump()
    hr = data["roles"][1]["dimensions"][0]
    hr["anchors"] = [dict(rating=n, score=n * 25, description=f"Synthetic HR {n}", evidence_required=True)
                     for n in range(1, 5)]
    result = aggregate(p=m.HumanPolicy(**data))
    assert result.calculation.human_score.value == 90  # (80 + 100) / 2, not (80 + 80) / 2
    five = review("HR").model_dump()
    five["observations"][0]["rating"] = 5
    result = aggregate(p=m.HumanPolicy(**data), reviews=[review(), m.EligibleHumanReview(**five)])
    assert result.calculation.human_score is None


def test_weights_do_not_pass_by_decimal_context_rounding():
    m = contracts()
    data = policy().model_dump()
    data["roles"][0]["weight"] = Decimal("0.50000000000000000000000000000000001")
    with pytest.raises(ValidationError):
        m.HumanPolicy(**data)
