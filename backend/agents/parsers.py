"""Bounded specialist-v1 validation; parsed model output is still advisory.

Legacy node/public field names remain unchanged. Missing/invalid model data must
raise instead of filling numerical fields from fabricated fallback results.
"""

import json
import re
from typing import Annotated, Literal, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

MAX_RESPONSE_BYTES = 65536
MAX_RESPONSE_DEPTH = 16
T = TypeVar("T", bound=BaseModel)
Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=16000)]
ShortText = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2000)]
OptionalText = Annotated[str, StringConstraints(strict=True, max_length=2000)]
Items = Annotated[list[ShortText], Field(max_length=32)]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
Score = Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]
Risk = Literal["critical", "high", "medium", "low"]


class AgentResponseError(ValueError):
    """The model did not return the supported bounded response contract."""


class SpecialistContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    schema_version: Literal["legacy-specialist-v1"] = "legacy-specialist-v1"


class CodeBreakdown(SpecialistContractV1):
    # Advisory legacy point units only. These do not calculate engine scores.
    correctness: Annotated[float, Field(ge=0, le=20)] | None = None
    maintainability: Annotated[float, Field(ge=0, le=20)] | None = None
    security: Annotated[float, Field(ge=0, le=20)] | None = None
    testing: Annotated[float, Field(ge=0, le=15)] | None = None
    performance: Annotated[float, Field(ge=0, le=10)] | None = None
    architecture: Annotated[float, Field(ge=0, le=10)] | None = None
    readability: Annotated[float, Field(ge=0, le=5)] | None = None


class AgentAnalysisResult(SpecialistContractV1):
    analysis: Text
    recommendations: Items
    risk_level: Risk
    confidence: Probability


class CodeAnalysisResult(AgentAnalysisResult):
    quality_score: Score | None = None
    failure_risk: Score | None = None
    critical_issues: Items = Field(default_factory=list)
    review_focus: OptionalText | None = None
    quality_breakdown: CodeBreakdown | None = None


class CICDFailureResult(SpecialistContractV1):
    root_cause: Text
    affected_component: ShortText
    fix_recommendations: Items
    prevention: ShortText
    urgency: Risk
    confidence: Probability


def response_text(response) -> str:
    # Retain chat-message text support without stringifying arbitrary objects.
    text = response if isinstance(response, str) else getattr(response, "content", None)
    if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise AgentResponseError("Unsupported or oversized model response")
    return text.strip()


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AgentResponseError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_):
    raise AgentResponseError("Non-finite JSON constant")


def _bounded_json(text):
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_RESPONSE_DEPTH:
                raise AgentResponseError("JSON nesting exceeds contract")
        elif char in "]}":
            depth -= 1
    value = json.loads(text, object_pairs_hook=_object_pairs, parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise AgentResponseError("Expected one JSON object")
    return value


def extract_json(response) -> Optional[dict]:
    """Retain unambiguous legacy JSON/fence/prose wrappers, never merge objects."""
    text = response_text(response)
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    elif not text.startswith("["):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end >= start:
            text = text[start:end + 1]
    try:
        return _bounded_json(text)
    except (ValueError, TypeError, RecursionError) as error:
        raise AgentResponseError("Invalid JSON model response") from error


def safe_parse(response, model: Type[T], fallback: Optional[T] = None) -> T:
    """Parse v1 strictly. The old fallback argument never supplies missing facts."""
    try:
        return model.model_validate(extract_json(response))
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        raise AgentResponseError("Model response violates specialist-v1") from error


def failed_response(state, agent_name, error):
    """Explicit legacy errors list; no raw provider/model output is published."""
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        code = "MODEL_TIMEOUT"
    elif isinstance(error, AgentResponseError):
        code = "INVALID_MODEL_RESPONSE"
    else:
        code = "MODEL_UNAVAILABLE"
    output_fields = (
        "analysis", "recommendations", "risk_level", "confidence", "quality_score",
        "quality_breakdown", "failure_risk", "critical_issues", "review_focus",
        "evidence_risk_score", "evidence_quality_score", "risk_factors", "quality_factors",
        "affected_component", "prevention", "urgency",
    )
    return {
        **state,
        **dict.fromkeys(output_fields),
        "errors": list(state.get("errors") or []) + [f"{agent_name}: {code}"],
        "agent_history": list(state.get("agent_history") or []) + [agent_name],
        "next_agent": None,
    }
