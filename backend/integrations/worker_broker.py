"""OPS-03: API-side client for the internal worker broker.

In production the public API holds no Docker socket. It sends fixed,
validated operations to the worker broker over the internal network and
re-checks what comes back. With no ``WORKER_BROKER_URL`` the local Docker CLI
runners are used (development mode).
"""

import json
import math

import httpx

from core.config import settings
from intelligence.algorithms.runner import BenchmarkFailure, BenchmarkUnavailable, DockerBenchmarkRunner

PROTOCOL = "samanvaya-worker-broker-v1"
MAX_RESPONSE_BYTES = 6_000_000


def broker_enabled() -> bool:
    return bool(settings.WORKER_BROKER_URL.strip())


class _BrokerClient:
    def __init__(self, url=None, token=None, timeout_seconds=None):
        self.url = (url if url is not None else settings.WORKER_BROKER_URL).rstrip("/")
        self.token = token if token is not None else settings.WORKER_BROKER_TOKEN
        self.timeout_seconds = timeout_seconds or settings.WORKER_BROKER_TIMEOUT_SECONDS
        if not self.url.startswith(("http://", "https://")):
            raise BenchmarkUnavailable("WORKER_BROKER_URL must be an http(s) URL")
        if len(self.token) < 32:
            raise BenchmarkUnavailable("WORKER_BROKER_TOKEN must be at least 32 characters")

    async def request(self, method, path, body=None):
        headers = {"Authorization": f"Bearer {self.token}", "X-Worker-Protocol": PROTOCOL}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(method, self.url + path, headers=headers,
                                                content=None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False),
                                                )
        except httpx.TimeoutException as exc:
            raise BenchmarkFailure("Worker broker timed out") from exc
        except httpx.HTTPError as exc:
            raise BenchmarkUnavailable("Worker broker unreachable") from exc
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise BenchmarkFailure("Worker broker response exceeded its bound")
        try:
            data = response.json()
        except ValueError as exc:
            raise BenchmarkFailure("Worker broker returned invalid JSON") from exc
        if not isinstance(data, dict) or data.get("protocol") != PROTOCOL:
            raise BenchmarkFailure("Worker broker protocol mismatch")
        if response.status_code == 422:
            raise ValueError(str(data.get("detail") or "Worker request rejected"))
        if response.status_code in (401, 403):
            raise BenchmarkUnavailable("Worker broker rejected the API credentials")
        if response.status_code in (429, 503):
            raise BenchmarkUnavailable(str(data.get("detail") or "Worker broker unavailable"))
        if response.status_code != 200:
            raise BenchmarkFailure(str(data.get("detail") or "Isolated worker failed"))
        return data


class BrokerBenchmarkRunner:
    """Same interface as DockerBenchmarkRunner (run / analyze / availability)."""

    def __init__(self, timeout_seconds=120, client=None):
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be finite and positive")
        self.timeout_seconds = timeout_seconds
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = _BrokerClient()
        return self._client

    async def run(self, payload: dict) -> dict:
        DockerBenchmarkRunner._validate(payload)
        return (await self.client.request("POST", "/v1/benchmark/run", {"payload": payload}))["result"]

    async def analyze(self, payload):
        return (await self.client.request("POST", "/v1/benchmark/analyze", {"payload": payload}))["result"]

    async def availability(self) -> dict:
        try:
            data = await self.client.request("GET", "/v1/availability")
        except (BenchmarkUnavailable, BenchmarkFailure) as exc:
            return {"available": False, "environment": {}, "error": str(exc)}
        result = data.get("benchmark")
        if not isinstance(result, dict) or not isinstance(result.get("available"), bool):
            return {"available": False, "environment": {}, "error": "Worker broker returned an invalid availability report"}
        return result


class BrokerQualityRunner:
    """Same interface as DockerQualityRunner.analyze; results are re-verified locally."""

    def __init__(self, client=None):
        self._client = client

    async def analyze(self, changed_files, context):
        from intelligence.analyzers.isolated import snapshot_payload, verify_brokered_evidence
        from intelligence.evidence.models import CodeQualityEvidence

        payload = snapshot_payload(changed_files, context)
        client = self._client or _BrokerClient()
        data = await client.request("POST", "/v1/quality/analyze",
                                    {"changed_files": payload["changed_files"], "context": {
                                        **payload["context"], "source_files": payload["sources"]}})
        evidence = CodeQualityEvidence.model_validate(data["evidence"])
        return verify_brokered_evidence(evidence, payload, context)


def benchmark_runner():
    return BrokerBenchmarkRunner() if broker_enabled() else DockerBenchmarkRunner()


def quality_runner():
    if broker_enabled():
        return BrokerQualityRunner()
    from intelligence.analyzers.isolated import DockerQualityRunner
    return DockerQualityRunner()
