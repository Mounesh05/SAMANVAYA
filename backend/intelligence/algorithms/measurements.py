"""Data-only validation of independent worker measurements; no candidate execution."""

import math

VERSION = "independent-v1"
STATUSES = {"AVAILABLE", "UNAVAILABLE", "INVALID"}


def validate_measurements(case, repetitions, python):
    """Reject contradictory envelopes. Legacy messages are validated by the runner."""
    if case.get("measurement_version") != VERSION:
        raise ValueError("Unsupported measurement version")
    if not {"timing_status", "timing_error", "memory_status", "memory_error", "timings_seconds", "memory_bytes"} <= case.keys():
        raise ValueError("Incomplete measurement envelope")
    for kind in ("timing", "memory"):
        status, error = case.get(kind + "_status"), case.get(kind + "_error")
        if status not in STATUSES:
            raise ValueError("Missing measurement availability")
        if status == "AVAILABLE":
            if error is not None:
                raise ValueError("Available measurements cannot have errors")
        elif not isinstance(error, str) or not error.strip():
            raise ValueError("Unavailable/invalid measurements require an error")
    samples = case.get("timings_seconds")
    if (not isinstance(samples, list) or len(samples) > repetitions
            or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in samples)):
        raise ValueError("Malformed timing samples")
    if case["timing_status"] == "AVAILABLE" and (
            len(samples) != repetitions or any(t <= 0 for t in samples)):
        raise ValueError("Available timing requires complete positive samples")
    if case["timing_status"] == "UNAVAILABLE" and samples:
        raise ValueError("Unavailable timing cannot carry samples")
    if case["timing_status"] == "INVALID" and len(samples) == repetitions and all(t > 0 for t in samples):
        raise ValueError("Complete positive samples cannot be invalid")
    memory = case.get("memory_bytes")
    if case["memory_status"] == "AVAILABLE":
        if type(memory) is not int or not -(2**63) <= memory < 2**63 or python and memory < 0:
            raise ValueError("Available memory requires a valid metric value")
    elif memory is not None:
        raise ValueError("Unavailable/invalid memory cannot carry a usable value")


def availability(case, repetitions, python):
    """Normalize safe historical evidence without upgrading missing provenance."""
    if "measurement_version" in case:
        validate_measurements(case, repetitions, python)
        return {kind: case[kind + "_status"] for kind in ("timing", "memory")}
    # Older workers couple successful correctness to complete measurements. Never
    # reinterpret a legacy error as an optional measurement failure.
    if case.get("error") is not None:
        return {"timing": "INVALID", "memory": "INVALID"}
    samples, memory = case.get("timings_seconds"), case.get("memory_bytes")
    timing = (isinstance(samples, list) and len(samples) == repetitions
              and all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in samples))
    valid_memory = (type(memory) is int and -(2**63) <= memory < 2**63 and (not python or memory >= 0))
    return {"timing": "AVAILABLE" if timing else "UNAVAILABLE" if samples in (None, []) else "INVALID",
            "memory": "AVAILABLE" if valid_memory else "UNAVAILABLE" if memory is None else "INVALID"}
