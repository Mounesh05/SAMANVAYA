"""One pure period-composition implementation; no source validation or approval."""

import hashlib
import json
from domain.models.performance_scoring import (
    CalculationSnapshot, NormalizedLegacyAI, ScoreCalculation, ScoreUnit, ScoreValue, period_components,
)


def _checked_score(score: ScoreValue, unit: ScoreUnit) -> ScoreValue:
    value = ScoreValue.model_validate(score)
    if value.unit != unit:
        raise ValueError(f"Expected score unit {unit.value}, received {value.unit.value}")
    return value


def normalize_legacy_ai_contribution(score: ScoreValue) -> NormalizedLegacyAI:
    """Convert a declared legacy contribution; does not validate underlying work."""
    value = _checked_score(score, ScoreUnit.LEGACY_AI_0_90)
    return NormalizedLegacyAI(source=value)


def combine_scores(engineering: ScoreValue | NormalizedLegacyAI | None, human: ScoreValue | None) -> ScoreCalculation:
    e = (NormalizedLegacyAI.model_validate(engineering) if isinstance(engineering, NormalizedLegacyAI)
         else _checked_score(engineering, ScoreUnit.PERIOD_0_100) if engineering is not None else None)
    h = _checked_score(human, ScoreUnit.PERIOD_0_100) if human is not None else None
    e_contribution, h_contribution, combined = period_components(e, h)
    return ScoreCalculation(engineering_score=e, human_score=h,
        combined_score=ScoreValue(unit=ScoreUnit.PERIOD_0_100, value=combined) if combined is not None else None,
        engineering_contribution=ScoreValue(unit=ScoreUnit.ENGINEERING_CONTRIBUTION_0_90, value=e_contribution) if e is not None else None,
        human_contribution=ScoreValue(unit=ScoreUnit.HUMAN_CONTRIBUTION_0_10, value=h_contribution) if h is not None else None,
        status="COMPLETE" if combined is not None else "INCOMPLETE")


def snapshot_digest(snapshot: CalculationSnapshot) -> str:
    value = CalculationSnapshot.model_validate(snapshot)
    data = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
