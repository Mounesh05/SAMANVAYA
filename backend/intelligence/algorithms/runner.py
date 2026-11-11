"""Docker-only function benchmarks with a backwards-compatible sorting preset."""

import asyncio
import json
import math
import re
import uuid
from contextlib import suppress

from benchmark_worker.contracts import is_generic, validate_function_payload
from intelligence.algorithms.measurements import VERSION, validate_measurements

__all__ = ["DockerBenchmarkRunner", "BenchmarkUnavailable", "BenchmarkFailure"]


class BenchmarkUnavailable(RuntimeError):
    """Docker or a prebuilt benchmark image is unavailable."""


class BenchmarkFailure(RuntimeError):
    """A worker timed out, exceeded its output budget, or broke the protocol."""


IMAGES = {
    "python": "samanvaya-benchmark-python:1",
    "javascript": "samanvaya-benchmark-node:1",
    "typescript": "samanvaya-benchmark-node:1",
}
DISTRIBUTIONS = {"random", "sorted", "reversed", "duplicates"}
MEMORY_METRICS = {
    "python": "memray_peak_tracked_allocations_bytes",
    "javascript": "node_heap_used_delta_bytes",
    "typescript": "node_heap_used_delta_bytes",
}


class DockerBenchmarkRunner:
    def __init__(self, timeout_seconds=120, max_output_bytes=2_000_000):
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be finite and positive")
        if type(max_output_bytes) is not int or max_output_bytes < 1:
            raise ValueError("max_output_bytes must be a positive integer")
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    async def _command(self, *args, data=None):
        """Drain both pipes concurrently; never buffer unlimited communicate() output."""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", *args, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise BenchmarkUnavailable("Docker CLI unavailable; install Docker and start its daemon") from exc
        consumed = 0

        async def read(stream):
            nonlocal consumed
            chunks = []
            while True:
                chunk = await stream.read(65536)
                if not chunk:
                    return b"".join(chunks)
                consumed += len(chunk)
                if consumed > self.max_output_bytes:
                    raise BenchmarkFailure("Docker output exceeded max_output_bytes")
                chunks.append(chunk)

        async def write():
            try:
                if data:
                    process.stdin.write(data)
                    await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                process.stdin.close()

        tasks = [asyncio.create_task(read(process.stdout)),
                 asyncio.create_task(read(process.stderr)),
                 asyncio.create_task(write()), asyncio.create_task(process.wait())]
        try:
            stdout, stderr, _, code = await asyncio.gather(*tasks)
            return code, stdout, stderr
        finally:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.kill()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await process.wait()

    async def _inspect(self, images):
        code, output, _ = await self._command("version", "--format", "{{.Server.Version}}")
        if code or not output.strip():
            raise BenchmarkUnavailable("Docker daemon unavailable; start Docker and check docker version")
        found = {}
        for image in dict.fromkeys(images):
            code, image_id, _ = await self._command("image", "inspect", "--format", "{{.Id}}", image)
            if code or not image_id.strip():
                dockerfile = "Dockerfile.python" if image == IMAGES["python"] else "Dockerfile.node"
                raise BenchmarkUnavailable(
                    f"Missing local image {image}; build from the repository root: "
                    f"docker build -f backend/benchmark_worker/{dockerfile} -t {image} backend/benchmark_worker "
                    "(runtime pulling is disabled)"
                )
            found[image] = image_id.decode("utf-8", "replace").strip()
        return {"docker_version": output.decode("utf-8", "replace").strip(), "images": found}

    async def availability(self) -> dict:
        """Probe both fixed images without pulling; return an actionable reason if absent."""
        try:
            environment = await asyncio.wait_for(self._inspect(IMAGES.values()), self.timeout_seconds)
            return {"available": True, "environment": environment, "error": None}
        except (BenchmarkUnavailable, BenchmarkFailure, asyncio.TimeoutError) as exc:
            return {"available": False, "environment": {},
                    "error": str(exc) or "Docker availability probe timed out"}

    @staticmethod
    def _validate(payload):
        if (not isinstance(payload, dict) or not isinstance(payload.get("language"), str)
                        or payload["language"] not in IMAGES):
            raise ValueError("language must be python, javascript, or typescript")
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 5:
            raise ValueError("provide 1..5 candidates")
        names = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("invalid candidate")
            name, source, entrypoint = (candidate.get(k) for k in ("name", "source", "entrypoint"))
            if not isinstance(name, str) or not 1 <= len(name) <= 200 or name in names:
                raise ValueError("candidate names must be unique nonempty strings up to 200 characters")
            names.add(name)
            if not isinstance(source, str) or not source or len(source.encode("utf-8")) > 200_000:
                raise ValueError("candidate source must contain 1..200000 UTF-8 bytes")
            if not isinstance(entrypoint, str) or not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]{0,127}", entrypoint):
                raise ValueError("entrypoint must be a simple function identifier")
        validate_function_payload(payload)
        if not is_generic(payload):
            sizes = payload.get("sizes")
            if (not isinstance(sizes, list) or not 1 <= len(sizes) <= 16
                    or any(type(n) is not int or not 0 <= n <= 10_000 for n in sizes)
                    or len(set(sizes)) != len(sizes)):
                raise ValueError("sizes must contain 1..16 unique integers in 0..10000")
            distributions = payload.get("distributions")
            if (not isinstance(distributions, list) or not 1 <= len(distributions) <= 4
                    or any(not isinstance(d, str) or d not in DISTRIBUTIONS for d in distributions)
                    or len(set(distributions)) != len(distributions)):
                raise ValueError("invalid or duplicate distributions")
        if type(payload.get("repetitions")) is not int or not 1 <= payload["repetitions"] <= 10:
            raise ValueError("repetitions must be in 1..10")
        if type(payload.get("seed", 42)) is not int or not 0 <= payload.get("seed", 42) <= 0xFFFFFFFF:
            raise ValueError("seed must be an unsigned 32-bit integer")

    async def _remove(self, name):
        try:
            await asyncio.wait_for(self._command("rm", "--force", name), 5)
            # An already removed (--rm) container also returns nonzero.
        except (BenchmarkUnavailable, BenchmarkFailure, asyncio.TimeoutError):
            pass

    @staticmethod
    def _parse(stdout, payload, candidate):
        try:
            def reject_constant(value):
                raise ValueError(f"non-finite JSON number: {value}")

            def require(condition):
                # Protocol checks must remain enabled under python -O.
                if not condition:
                    raise ValueError("worker schema mismatch")

            message = json.loads(stdout, parse_constant=reject_constant)
            result = message["result"]
            require(isinstance(message["environment"], dict) and isinstance(message["tools"], dict))
            require(result["candidate"] == candidate["name"])
            require(result["error"] is None or isinstance(result["error"], str))
            cases = result["cases"]
            require(isinstance(cases, list))
            if result["error"] is not None:
                require(bool(result["error"]) and cases == [])
            elif payload.get("operation") == "structure":
                require(cases == [] and isinstance(result.get("structure"), dict))
                require(result["structure"].get("status") in ("available", "unavailable"))
            else:
                generic = is_generic(payload)
                expected = (payload["datasets"] if generic else
                            [(n, d) for n in payload["sizes"] for d in payload["distributions"]])
                require(len(cases) == len(expected))
                for case, descriptor in zip(cases, expected):
                    if generic:
                        require(case["case_id"] == descriptor["id"])
                        dimensions = case["dimensions"]
                        require(isinstance(dimensions, dict))
                        require(all(isinstance(k, str) and type(v) is int for k, v in dimensions.items()))
                        require(dimensions == descriptor.get("dimensions", {}))
                        if payload.get("compatibility_context"):
                            behavior = case.get("behavioral_validation", {})
                            require(isinstance(behavior, dict))
                            require(behavior.get("version") == "functional-validation-v1")
                            require(behavior.get("status") in {"PASS", "FAIL", "UNVERIFIED"})
                            require(type(behavior.get("validated_calls")) is int and behavior["validated_calls"] >= 0)
                        status = case["validation_status"]
                        if status == "verified":
                            require(payload["contract"]["correctness"] == "expected" and case["correct"] is True)
                        elif status == "unverified":
                            require(payload["contract"]["correctness"] == "none" and case["correct"] is None)
                        else:
                            require(status == "failed" and case["correct"] is False)
                    else:
                        size, distribution = descriptor
                        require(type(case["size"]) is int and case["size"] == size)
                        require(case["distribution"] == distribution)
                        require(type(case["correct"]) is bool)
                    require(case["error"] is None or isinstance(case["error"], str))
                    require(case["memory_metric"] == MEMORY_METRICS[payload["language"]])
                    memory = case["memory_bytes"]
                    require(memory is None or type(memory) is int and -(2**63) <= memory < 2**63)
                    if payload["language"] == "python" and memory is not None:
                        require(memory >= 0)
                    timings = case["timings_seconds"]
                    require(isinstance(timings, list) and len(timings) <= payload["repetitions"])
                    require(all(type(t) in (int, float) and math.isfinite(t) and t >= 0 for t in timings))
                    if "measurement_version" in case:
                        validate_measurements(case, payload["repetitions"], payload["language"] == "python")
                        if case["correct"] is False:
                            require(isinstance(case["error"], str) and bool(case["error"]))
                        else:
                            require(case["error"] is None)
                    elif payload.get("decision_policy") is not None:
                        require(False)  # New-policy execution cannot silently downgrade the protocol.
                    elif case["correct"] is True or generic and case["validation_status"] == "unverified":
                        require(case["error"] is None and len(timings) == payload["repetitions"])
                        require(memory is not None)
                    else:
                        require(isinstance(case["error"], str) and bool(case["error"]))
            return message
        except (ValueError, KeyError, TypeError, OverflowError, RecursionError) as exc:
            raise BenchmarkFailure("Malformed worker results (invalid JSON or result schema)") from exc

    async def _candidate(self, payload, candidate):
        name = "samanvaya-benchmark-" + uuid.uuid4().hex
        request = {key: payload[key] for key in (
            "language", "sizes", "distributions", "repetitions", "seed", "contract", "datasets", "resources"
        ) if key in payload}
        if payload.get("operation") == "structure":
            request["operation"] = "structure"
        request["candidates"] = [{key: candidate[key] for key in ("name", "source", "entrypoint")}]
        if payload.get("decision_policy") is not None:
            request["measurement_protocol"] = VERSION
        resources = payload.get("resources", {})
        memory = resources.get("memory_bytes")
        memory_flag = str(memory) if memory is not None else "512m"
        cpus = resources.get("cpus", 1)
        pids = resources.get("pids", 64)
        try:
            code, stdout, stderr = await self._command(
                "run", "--rm", "--pull=never", "--name", name,
                "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
                "--user=65532:65532", "--read-only",
                "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
                f"--memory={memory_flag}", f"--memory-swap={memory_flag}", f"--cpus={cpus}", f"--pids-limit={pids}",
                "--ulimit=nofile=128:128", "--init", "--log-driver=none", "--interactive",
                IMAGES[payload["language"]], data=json.dumps(request, allow_nan=False, ensure_ascii=False).encode("utf-8"),
            )
            if code:
                detail = stderr.decode("utf-8", "replace")[:1000]
                raise BenchmarkFailure(f"Benchmark container exited with status {code}: {detail}")
            return self._parse(stdout, payload, candidate)
        finally:
            cleanup = asyncio.create_task(self._remove(name))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise

    async def run(self, payload: dict) -> dict:
        self._validate(payload)
        resources = payload.get("resources", {})
        timeout = min(self.timeout_seconds, resources.get("timeout_seconds", self.timeout_seconds))

        async def execute():
            environment = await self._inspect([IMAGES[payload["language"]]])
            environment.update({"isolation": "docker", "network": "none", "cpus": resources.get("cpus", 1),
                                "memory_limit_bytes": resources.get("memory_bytes", 536870912),
                                "pids_limit": resources.get("pids", 64),
                                "timeout_seconds": timeout,
                                "timing_method": "warmups_then_repeated_samples_not_calibrated",
                                "seed": payload.get("seed", 42), "language": payload["language"],
                                "protocol": "json-function-v1" if is_generic(payload) else "numeric-ascending-sort-v1"})
            results, tools, workers = [], {}, []
            for candidate in payload["candidates"]:
                message = await self._candidate(payload, candidate)
                results.append(message["result"])
                tools.update(message["tools"])
                worker = {**message["environment"], "candidate": candidate["name"]}
                if payload.get("decision_policy") is not None:
                    worker["measurement_tools"] = message["tools"]
                workers.append(worker)
            environment["workers"] = workers
            return {"environment": environment, "results": results, "tools": tools}

        try:
            return await asyncio.wait_for(execute(), timeout)
        except asyncio.TimeoutError as exc:
            raise BenchmarkFailure(f"Benchmark exceeded total deadline of {timeout}s") from exc

    async def analyze(self, payload):
        """Parse JavaScript/TypeScript ASTs in fixed containers, without invoking source."""
        request = {"language": payload["language"], "candidates": payload["candidates"],
                   "sizes": [0], "distributions": ["random"], "repetitions": 1, "seed": 42,
                   "resources": payload.get("resources", {})}
        self._validate(request)
        if request["language"] == "python":
            raise ValueError("Use source-only Python AST analysis for Python")
        request["operation"] = "structure"
        # run() only forwards this trusted internal operation; API benchmark requests
        # cannot select it because their schema forbids unknown top-level fields.
        return await self.run(request)
