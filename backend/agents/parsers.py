"""
Shared LLM response parsers.
Replaces fragile string-splitting with JSON extraction + Pydantic validation.

All agents should use these utilities instead of manual line-by-line parsing.
"""

import json
import re
from typing import Optional, Type, TypeVar
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def extract_json(response: str) -> Optional[dict]:
    """
    Extract the first valid JSON object from an LLM response string.

    LLMs often wrap JSON in markdown code fences or add prose before/after.
    This handles:
      - ```json ... ```
      - ``` ... ```
      - Raw {...} anywhere in the response

    Returns:
        Parsed dict if JSON found, None otherwise.
    """
    if not response:
        return None

    # Try stripping markdown code fences first
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Fall back to finding outermost {...}
    start = response.find("{")
    end = response.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(response[start:end])
        except json.JSONDecodeError:
            # Try to handle truncated/malformed JSON gracefully
            pass

    return None


def safe_parse(response: str, model: Type[T], fallback: T) -> T:
    """
    Extract JSON from an LLM response and validate it against a Pydantic model.

    Args:
        response: Raw LLM string output
        model: Pydantic model class to validate against
        fallback: Instance to return if parsing/validation fails

    Returns:
        Validated model instance, or fallback on failure.
    """
    data = extract_json(response)
    if data is None:
        return fallback

    try:
        return model.model_validate(data)
    except Exception:
        # Try partial construction — fill missing fields from fallback
        try:
            merged = fallback.model_dump()
            merged.update({k: v for k, v in data.items() if k in merged})
            return model.model_validate(merged)
        except Exception:
            return fallback


# ── Agent-specific response models ──────────────────────────────────────────

class CodeAnalysisResult(BaseModel):
    """Structured output for code_agent LLM response."""
    quality_score: float = 0.0          # 0–100
    failure_risk: float = 0.0           # 0–100
    risk_level: str = "medium"          # critical|high|medium|low
    confidence: float = 0.0             # 0.0–1.0
    analysis: str = ""
    critical_issues: list[str] = []
    recommendations: list[str] = []
    review_focus: str = ""
    quality_breakdown: dict = {}


class AgentAnalysisResult(BaseModel):
    """Structured output for devops/qa/meeting agents."""
    analysis: str = ""
    recommendations: list[str] = []
    risk_level: str = "medium"
    confidence: float = 0.0


class CICDFailureResult(BaseModel):
    """Structured output for cicd_agent."""
    root_cause: str = ""
    affected_component: str = ""
    fix_recommendations: list[str] = []
    prevention: str = ""
    urgency: str = "medium"
    confidence: float = 0.0
