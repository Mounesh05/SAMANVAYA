"""Container entrypoint and Python harness. Never invoke with submitted code on the host."""

import copy
import inspect
import math
import json
import platform
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

try:  # Direct script entrypoint inside the image.
    from contracts import (
        _json,
        _same,
        is_generic,
        validate_function_payload,
        validate_schema,
    )
except ImportError:  # Package import on the host (data-only helpers/tests).
    from benchmark_worker.contracts import (
        _json,
        _same,
        is_generic,
        validate_function_payload,
        validate_schema,
    )

MEMORY_METRIC = "memray_peak_tracked_allocations_bytes"


def benchmark_independent_cases(payload, function, result, memray, pyperf):
    """Independent instrumentation failures; every actual invocation is validated."""
    generic = is_generic(payload)
    descriptors = (payload["datasets"] if generic else [
        {"size": n, "distribution": d} for n in payload["sizes"] for d in payload["distributions"]])
    for descriptor in descriptors:
        case = ({"case_id": descriptor["id"], "dimensions": copy.deepcopy(descriptor.get("dimensions", {})),
                 "validation_status": "failed"} if generic else dict(descriptor))
        case.update(correct=False, timings_seconds=[], memory_bytes=None, memory_metric=MEMORY_METRIC,
                    error=None, measurement_version="independent-v1", timing_status="UNAVAILABLE",
                    timing_error="Timing not reached", memory_status="UNAVAILABLE", memory_error="Memory not reached")
        result["cases"].append(case)
        if generic:
            original = descriptor["args"]
        else:
            original = [make_input(descriptor["size"], descriptor["distribution"], payload.get("seed", 42))]
        expected = None if generic else sorted(original[0])
        def validate_output(output, arguments):
            if generic:
                check_function_result(output, arguments, descriptor, payload["contract"])
            else:
                check_result(output, arguments[0], expected)
        def invoke():
            arguments = copy.deepcopy(original)
            output = function(*arguments)
            validate_output(output, arguments)
            return output
        try:
            for _ in range(2):
                invoke()
            timing_error = None
            timing_invalid = False
            for _ in range(payload["repetitions"]):
                # Clone outside the timed region, exactly as the historical harness.
                arguments = copy.deepcopy(original)
                try:
                    start = pyperf.perf_counter()
                except Exception as exc:
                    start = None
                    timing_error = type(exc).__name__ + ": timing instrumentation unavailable"
                output = function(*arguments)
                try:
                    elapsed = pyperf.perf_counter() - start if start is not None else None
                except Exception as exc:
                    elapsed = None
                    timing_error = type(exc).__name__ + ": timing instrumentation unavailable"
                validate_output(output, arguments)
                if elapsed is not None:
                    if not math.isfinite(elapsed) or elapsed < 0:
                        timing_error = "Invalid clock measurement"
                        timing_invalid = True
                    else:
                        case["timings_seconds"].append(elapsed)
            if timing_error:
                case.update(timings_seconds=[], timing_status="INVALID" if timing_invalid else "UNAVAILABLE", timing_error=timing_error)
            elif all(t > 0 for t in case["timings_seconds"]):
                case.update(timing_status="AVAILABLE", timing_error=None)
            else:
                case.update(timing_status="INVALID", timing_error="Zero-duration timing samples")
            # Instrumentation setup/extraction may fail independently. Invocation
            # and validation exceptions deliberately escape to correctness failure.
            directory = None
            memory_arguments = copy.deepcopy(original)
            try:
                directory = tempfile.TemporaryDirectory(prefix="memray-", dir="/tmp")
                trace = str(Path(directory.name) / "allocations.bin")
                tracker = memray.Tracker(trace, native_traces=True, trace_python_allocators=True)
                tracker.__enter__()
            except Exception as exc:
                case["memory_error"] = type(exc).__name__ + ": memory instrumentation unavailable"
                if directory is not None:
                    with suppress(Exception):
                        directory.cleanup()
                invoke()
            else:
                try:
                    # Preserve the historical metric's measured region: only the
                    # function invocation, excluding input cloning and validation.
                    output = function(*memory_arguments)
                except BaseException:
                    try:
                        tracker.__exit__(*sys.exc_info())
                    except Exception:
                        pass
                    raise
                else:
                    try:
                        tracker.__exit__(None, None, None)
                    except Exception as exc:
                        case["memory_error"] = type(exc).__name__ + ": memory tracker close unavailable"
                    # Validate even when instrumentation failed after invocation.
                    validate_output(output, memory_arguments)
                    try:
                        if case["memory_error"] != "Memory not reached":
                            raise RuntimeError("Memory tracker did not close successfully")
                        reader = memray.FileReader(trace)
                        memory = sum(r.size for r in reader.get_high_watermark_allocation_records())
                        if type(memory) is not int or not 0 <= memory < 2**63:
                            case.update(memory_status="INVALID", memory_error="Invalid tracked allocation peak")
                        else:
                            case.update(memory_bytes=memory, memory_status="AVAILABLE", memory_error=None)
                    except Exception as exc:
                        case["memory_error"] = type(exc).__name__ + ": memory extraction unavailable"
                finally:
                    with suppress(Exception):
                        directory.cleanup()
            verified = not generic or payload["contract"]["correctness"] == "expected"
            case["correct"] = True if verified else None
            if generic:
                case["validation_status"] = "verified" if verified else "unverified"
        except BaseException as exc:
            case["error"] = f"{type(exc).__name__}: {str(exc)[:1500]}"
            samples = case["timings_seconds"]
            if samples and len(samples) != payload["repetitions"]:
                case.update(timing_status="INVALID", timing_error="Incomplete timing due to invocation failure")


def make_input(size, distribution, seed):
    """Shared unsigned LCG: identical integer datasets in Python and Node."""
    state = seed
    values = []
    for _ in range(size):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        values.append(state % (8 if distribution == "duplicates" else 20001)
                      - (0 if distribution == "duplicates" else 10000))
    if distribution in ("sorted", "reversed"):
        values.sort(reverse=distribution == "reversed")
    return values


def check_result(result, data, expected):
    output = data if result is None else result
    if (not isinstance(output, list) or any(type(v) not in (int, float) for v in output)
            or output != expected):
        raise ValueError("incorrect numeric sorting result (order or multiset mismatch)")


def check_function_result(output, arguments, dataset, contract):
    """Data-only result checks; invocation and measurements belong to the container."""
    if (inspect.isawaitable(output) or inspect.isgenerator(output) or inspect.isasyncgen(output)
            or callable(getattr(output, "then", None))):
        raise ValueError("async, thenable, and generator results are unsupported")
    if contract.get("mutation", "allowed") == "forbidden":
        _json(arguments)
        if not _same(arguments, dataset["args"]):
            raise ValueError("argument mutation is forbidden")
    selector = contract.get("output", {"source": "return"})
    if selector["source"] == "argument":
        output = arguments[selector.get("index", 0)]
    validate_schema(output, contract["output_schema"])
    if contract["correctness"] == "expected" and not _same(output, dataset["expected"]):
        raise ValueError("output does not match expected JSON")


def benchmark_function_cases(payload, function, result, memray, pyperf):
    contract = payload["contract"]
    for dataset in payload["datasets"]:
        case = {"case_id": dataset["id"], "dimensions": copy.deepcopy(dataset.get("dimensions", {})),
                "correct": False, "validation_status": "failed", "timings_seconds": [],
                "memory_bytes": None, "memory_metric": MEMORY_METRIC, "error": None}
        result["cases"].append(case)
        try:
            for _ in range(2):
                arguments = copy.deepcopy(dataset["args"])
                output = function(*arguments)
                check_function_result(output, arguments, dataset, contract)
            for _ in range(payload["repetitions"]):
                arguments = copy.deepcopy(dataset["args"])
                start = pyperf.perf_counter()
                output = function(*arguments)
                elapsed = pyperf.perf_counter() - start
                check_function_result(output, arguments, dataset, contract)
                case["timings_seconds"].append(elapsed)
            arguments = copy.deepcopy(dataset["args"])
            with tempfile.TemporaryDirectory(prefix="memray-", dir="/tmp") as directory:
                trace = str(Path(directory) / "allocations.bin")
                with memray.Tracker(trace, native_traces=True, trace_python_allocators=True):
                    output = function(*arguments)
                check_function_result(output, arguments, dataset, contract)
                reader = memray.FileReader(trace)
                case["memory_bytes"] = sum(
                    record.size for record in reader.get_high_watermark_allocation_records()
                )
            verified = contract["correctness"] == "expected"
            case["correct"] = True if verified else None
            case["validation_status"] = "verified" if verified else "unverified"
        except BaseException as exc:
            case["error"] = f"{type(exc).__name__}: {str(exc)[:1500]}"


def benchmark(payload):
    if payload.get("measurement_protocol") == "independent-v1":
        try:
            import memray
        except Exception:
            memray = None
        try:
            import pyperf
        except Exception:
            pyperf = None
    else:
        import memray
        import pyperf

    candidate = payload["candidates"][0]
    result = {"candidate": candidate["name"], "cases": [], "error": None}
    message = {
        "environment": {"runtime": platform.python_version(), "platform": platform.platform(),
                        "warmups": 2, "input_generator": "explicit-json-v1" if is_generic(payload) else "lcg32-v1"},
        "result": result,
        "tools": {"pyperf": getattr(pyperf, "__version__", "unavailable"), "memray": getattr(memray, "__version__", "unavailable"),
                  "timing": "pyperf.perf_counter repeated samples; not calibrated pyperf.Runner",
                  "memory": MEMORY_METRIC},
    }
    if payload.get("measurement_protocol") == "independent-v1":
        message["environment"]["measurement_protocol"] = "independent-v1"
    try:
        if is_generic(payload):
            validate_function_payload(payload)
        namespace = {"__name__": "benchmark_candidate"}
        exec(compile(candidate["source"], "<candidate>", "exec"), namespace)
        function = namespace.get(candidate["entrypoint"])
        if (not callable(function) or inspect.iscoroutinefunction(function)
                or inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function)):
            raise ValueError("entrypoint must be a synchronous function")
    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:1500]}"
        return message

    if payload.get("measurement_protocol") == "independent-v1":
        benchmark_independent_cases(payload, function, result, memray, pyperf)
        return message
    if is_generic(payload):
        benchmark_function_cases(payload, function, result, memray, pyperf)
        return message

    for size in payload["sizes"]:
        for distribution in payload["distributions"]:
            data = make_input(size, distribution, payload["seed"])
            expected = sorted(data)
            case = {"size": size, "distribution": distribution, "correct": False,
                    "timings_seconds": [], "memory_bytes": None,
                    "memory_metric": MEMORY_METRIC, "error": None}
            result["cases"].append(case)
            try:
                for _ in range(2):
                    argument = data.copy()
                    check_result(function(argument), argument, expected)
                for _ in range(payload["repetitions"]):
                    argument = data.copy()
                    start = pyperf.perf_counter()
                    output = function(argument)
                    elapsed = pyperf.perf_counter() - start
                    check_result(output, argument, expected)
                    case["timings_seconds"].append(elapsed)
                # Input copying and correctness checks are outside the tracked region.
                argument = data.copy()
                with tempfile.TemporaryDirectory(prefix="memray-", dir="/tmp") as directory:
                    trace = str(Path(directory) / "allocations.bin")
                    with memray.Tracker(trace, native_traces=True, trace_python_allocators=True):
                        output = function(argument)
                    check_result(output, argument, expected)
                    reader = memray.FileReader(trace)
                    case["memory_bytes"] = sum(
                        record.size for record in reader.get_high_watermark_allocation_records()
                    )
                case["correct"] = True
            except BaseException as exc:
                case["error"] = f"{type(exc).__name__}: {str(exc)[:1500]}"
    return message


def supervise():
    # The candidate runs only in a child inside the container. Its stdout/stderr never
    # share the controller protocol; the private result file is NOT tamper-proof.
    payload = sys.stdin.buffer.read(1_300_001)
    if len(payload) > 1_300_000:
        raise ValueError("worker input too large")
    with tempfile.TemporaryDirectory(prefix="benchmark-", dir="/tmp") as directory:
        result_path = str(Path(directory) / "result.json")
        completed = subprocess.run(
            [sys.executable, "-B", __file__, "--child", result_path], input=payload,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=115, check=False,
        )
        if completed.returncode:
            raise RuntimeError(f"candidate harness exited with status {completed.returncode}")
        with open(result_path, "rb") as handle:
            output = handle.read(2_000_001)
        if len(output) > 2_000_000:
            raise ValueError("worker result too large")
        sys.stdout.buffer.write(output)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        report = benchmark(json.load(sys.stdin))
        with open(sys.argv[2], "w", encoding="utf-8") as handle:
            json.dump(report, handle, allow_nan=False)
    else:
        supervise()
