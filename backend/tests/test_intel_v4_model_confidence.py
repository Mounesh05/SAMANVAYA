"""v4 investigation item 7 / phase 3: invalid model confidence is rejected, never clamped.

The developer evaluation clamped whatever the model returned into [0, 1]:
NaN, Infinity, 7 and ``true`` became 1.0 (maximum certainty), a missing value
became 0.0 and the string "0.4" was accepted. Dimension scores were already
rejected without normalization; confidence now follows the same rule.
"""

import json

import pytest

from api.routes import evaluation
from test_evaluation_engine import _model_response, _run_model_response


def _response_with_confidence(value):
    response = json.loads(_model_response())
    if value is _MISSING:
        response.pop("confidence")
    else:
        response["confidence"] = value
    return json.dumps(response)


_MISSING = object()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, 0.35, 1])
async def test_valid_confidence_is_kept_unchanged(monkeypatch, value):
    result = await _run_model_response(monkeypatch, _response_with_confidence(value))
    assert result["confidence"] == value


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [float("nan"), float("inf"), 7, -3, 1.01, True, "0.4", None, _MISSING])
async def test_invalid_confidence_is_rejected_without_normalization(monkeypatch, value):
    with pytest.raises(evaluation.ModelResponseValidationError, match="confidence must be a number between 0 and 1"):
        await _run_model_response(monkeypatch, _response_with_confidence(value))
