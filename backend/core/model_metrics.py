"""AI-01: in-process record of recent model call latency and outcomes.

Shows operators whether the configured model and hardware can finish calls
inside the configured limits (OLLAMA_INFERENCE_TIMEOUT_SECONDS,
PR_AGENT_SPECIALIST_TIMEOUT_SECONDS). Holds only durations and outcome labels,
never prompts or responses.
"""

import threading
import time
from collections import deque
from contextlib import contextmanager

MAX_SAMPLES = 200
_samples: dict[str, deque] = {}
_lock = threading.Lock()


def record(operation: str, seconds: float, outcome: str) -> None:
    with _lock:
        _samples.setdefault(operation, deque(maxlen=MAX_SAMPLES)).append((round(seconds, 2), outcome))


@contextmanager
def measure(operation: str):
    """Record the duration; outcome is 'ok', 'timeout' or 'error'."""
    started = time.monotonic()
    try:
        yield
    except TimeoutError:
        record(operation, time.monotonic() - started, "timeout")
        raise
    except Exception:
        record(operation, time.monotonic() - started, "error")
        raise
    else:
        record(operation, time.monotonic() - started, "ok")


def _percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def summary() -> dict:
    with _lock:
        data = {name: list(samples) for name, samples in _samples.items()}
    result = {}
    for name, samples in data.items():
        durations = [seconds for seconds, _ in samples]
        result[name] = {
            "calls": len(samples),
            "ok": sum(1 for _, outcome in samples if outcome == "ok"),
            "timeouts": sum(1 for _, outcome in samples if outcome == "timeout"),
            "errors": sum(1 for _, outcome in samples if outcome == "error"),
            "p50_seconds": _percentile(durations, 0.5) if durations else None,
            "p95_seconds": _percentile(durations, 0.95) if durations else None,
            "max_seconds": max(durations) if durations else None,
        }
    return result


def reset() -> None:
    with _lock:
        _samples.clear()
