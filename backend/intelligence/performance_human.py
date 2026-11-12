"""Deterministic human aggregation; callers must establish policy/evidence authority.

No public API accepts approved policies, validated_dimensions or E from a client.
This function performs arithmetic, not approval of an employee assessment.
"""

from decimal import Decimal, localcontext

from domain.models.performance_human import EligibleHumanReview, HumanAggregation, HumanPolicy
from domain.models.performance_scoring import ScoreValue
from intelligence.performance_scoring import combine_scores


def aggregate_human_reviews(policy: HumanPolicy | None, reviews: tuple[EligibleHumanReview, ...],
                            engineering: ScoreValue | None = None) -> HumanAggregation:
    policy = HumanPolicy.model_validate(policy) if policy is not None else None
    reviews = tuple(EligibleHumanReview.model_validate(r) for r in reviews)
    missing = []
    if policy is None or policy.status != "APPROVED":
        return HumanAggregation(status="POLICY_PENDING", policy_id=policy.policy_id if policy else None,
            policy_version=policy.version if policy else None,
            missing_requirements=("Approved applicable human policy, reviewer weights, anchors and completeness rules",),
            calculation=combine_scores(engineering, None))
    required = tuple(rule.role for rule in policy.roles)
    submitted = tuple(dict.fromkeys(r.role for r in reviews))
    if len({r.reviewer_id for r in reviews}) != len(reviews):
        missing.append("One independent reviewer per role; duplicate reviewer influence is unresolved")
    if len({r.role for r in reviews}) != len(reviews):
        missing.append("Duplicate reviewer roles require an approved resolution")
    if any(r.role not in required for r in reviews):
        missing.append("Review role is outside the approved policy")
    # Bound precision by actual input sizes; never round intermediate H.
    numbers = [n for r in policy.roles for d in r.dimensions for n in (r.weight, d.weight, *(a.score for a in d.anchors))]
    with localcontext() as context:
        context.prec = max(50, sum(len(n.as_tuple().digits) + abs(n.as_tuple().exponent) for n in numbers) + 10)
        human = Decimal(0)
        for rule in policy.roles:
            matches = [r for r in reviews if r.role == rule.role]
            if len(matches) != 1:
                missing.append(f"{rule.role}: exactly one eligible assigned review required")
                continue
            review = matches[0]
            if review.eligibility != "ELIGIBLE":
                missing.append(f"{rule.role}: current reviewer/assignment eligibility not established")
            expected = {d.dimension for d in rule.dimensions}
            if {o.dimension for o in review.observations} != expected or len(review.observations) != len(expected):
                missing.append(f"{rule.role}: assigned policy dimensions are incomplete or duplicated")
            for dimension in rule.dimensions:
                observations = [o for o in review.observations if o.dimension == dimension.dimension]
                if len(observations) != 1 or observations[0].state != "OBSERVED":
                    missing.append(f"{rule.role}/{dimension.dimension}: observed assessment or approved resolution required")
                    continue
                observation = observations[0]
                if dimension.dimension not in review.validated_dimensions:
                    missing.append(f"{rule.role}/{dimension.dimension}: evidence validation required")
                    continue
                anchor = next((a for a in dimension.anchors if a.rating == observation.rating), None)
                if anchor is None:
                    missing.append(f"{rule.role}/{dimension.dimension}: rating is outside the approved scale")
                    continue
                human += rule.weight * dimension.weight * anchor.score
        h = ScoreValue(unit="PERIOD_0_100", value=human) if not missing else None
    calculation = combine_scores(engineering, h)
    if engineering is None:
        missing.append("Validated engineering measurement E on the PERIOD_0_100 scale")
    return HumanAggregation(status="INCOMPLETE" if missing else "COMPLETE", policy_id=policy.policy_id,
        policy_version=policy.version, required_roles=required, submitted_roles=submitted,
        missing_requirements=tuple(missing), calculation=calculation)
