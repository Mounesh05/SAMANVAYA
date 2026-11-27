"""OPS-03: internal worker broker — the only service with Docker access.

The public API never mounts the Docker socket. It calls this service over a
private network. The broker exposes a few fixed operations that run the
versioned, prebuilt worker images with the existing isolation flags
(no network, read-only, dropped capabilities, CPU/memory/PID limits). It never
accepts image names, Docker arguments or host paths from callers.

Environment:
  WORKER_BROKER_TOKEN           shared secret, at least 32 characters (required)
  WORKER_BROKER_MAX_CONCURRENT  parallel worker containers, default 2
"""

import asyncio
import hmac
import json
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from intelligence.algorithms.runner import BenchmarkFailure, BenchmarkUnavailable, DockerBenchmarkRunner
from intelligence.analyzers.isolated import IMAGE as QUALITY_IMAGE, DockerQualityRunner

PROTOCOL = "samanvaya-worker-broker-v1"
MAX_BODY_BYTES = 5_000_000
logger = logging.getLogger("worker_broker")


def _token() -> str:
    token = os.environ.get("WORKER_BROKER_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("WORKER_BROKER_TOKEN must be set to at least 32 characters")
    return token


def _max_concurrent() -> int:
    try:
        value = int(os.environ.get("WORKER_BROKER_MAX_CONCURRENT", "2"))
    except ValueError:
        value = 2
    return min(max(value, 1), 8)


def create_app(token: str | None = None, max_concurrent: int | None = None) -> FastAPI:
    secret = token if token is not None else _token()
    if len(secret) < 32:
        raise RuntimeError("WORKER_BROKER_TOKEN must be set to at least 32 characters")
    limit = max_concurrent or _max_concurrent()
    slots = asyncio.Semaphore(limit)
    active = {"count": 0}
    app = FastAPI(title="Samanvaya worker broker", docs_url=None, redoc_url=None, openapi_url=None)

    def reply(code, /, **body):
        return JSONResponse(status_code=code, content={"protocol": PROTOCOL, **body})

    async def authorized_body(request: Request):
        supplied = request.headers.get("authorization", "")
        scheme, _, value = supplied.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(value.strip().encode(), secret.encode()):
            return None, reply(401, detail="Unauthorized")
        if request.headers.get("x-worker-protocol") != PROTOCOL:
            return None, reply(422, detail="Unsupported worker protocol")
        if request.method == "GET":
            return {}, None
        declared = request.headers.get("content-length")
        if declared and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
            return None, reply(413, detail="Request too large")
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return None, reply(413, detail="Request too large")
        try:
            body = json.loads(raw)
        except ValueError:
            return None, reply(422, detail="Invalid JSON")
        if not isinstance(body, dict):
            return None, reply(422, detail="Invalid request")
        return body, None

    async def bounded(operation):
        # A full broker refuses instead of queueing unbounded work.
        if active["count"] >= limit:
            return reply(429, detail="All isolated workers are busy; retry shortly")
        active["count"] += 1
        try:
            async with slots:
                return reply(200, **(await operation()))
        except ValueError as exc:
            return reply(422, detail=str(exc)[:300] or "Invalid worker request")
        except BenchmarkUnavailable as exc:
            return reply(503, detail=str(exc)[:300] or "Isolated workers unavailable")
        except (BenchmarkFailure, TimeoutError) as exc:
            return reply(502, detail=str(exc)[:300] or "Isolated worker failed")
        except Exception:
            logger.exception("Worker broker operation failed")
            return reply(502, detail="Isolated worker failed")
        finally:
            active["count"] -= 1

    @app.get("/v1/health")
    async def health():
        return reply(200, status="ok")

    @app.get("/v1/availability")
    async def availability(request: Request):
        _, error = await authorized_body(request)
        if error:
            return error
        runner = DockerBenchmarkRunner()
        benchmark = await runner.availability()
        try:
            await asyncio.wait_for(runner._inspect([QUALITY_IMAGE]), 30)
            quality: dict[str, object] = {"available": True, "error": None}
        except (BenchmarkUnavailable, BenchmarkFailure, TimeoutError) as exc:
            quality = {"available": False, "error": str(exc)[:300]}
        return reply(200, benchmark=benchmark, quality=quality)

    @app.post("/v1/benchmark/run")
    async def benchmark_run(request: Request):
        body, error = await authorized_body(request)
        if error:
            return error
        payload = body.get("payload")
        # Internal operations (e.g. "structure") are chosen by the broker, never by callers.
        if not isinstance(payload, dict) or "operation" in payload:
            return reply(422, detail="Invalid benchmark request")

        async def operation():
            return {"result": await DockerBenchmarkRunner().run(payload)}
        return await bounded(operation)

    @app.post("/v1/benchmark/analyze")
    async def benchmark_analyze(request: Request):
        body, error = await authorized_body(request)
        if error:
            return error
        payload = body.get("payload")
        if not isinstance(payload, dict):
            return reply(422, detail="Invalid structure request")

        async def operation():
            return {"result": await DockerBenchmarkRunner().analyze(payload)}
        return await bounded(operation)

    @app.post("/v1/quality/analyze")
    async def quality_analyze(request: Request):
        body, error = await authorized_body(request)
        if error:
            return error
        changed_files, context = body.get("changed_files"), body.get("context")
        if not isinstance(changed_files, list) or not isinstance(context, dict):
            return reply(422, detail="Invalid quality request")

        async def operation():
            evidence = await DockerQualityRunner().analyze(changed_files, context)
            return {"evidence": evidence.model_dump(mode="json")}
        return await bounded(operation)

    return app


def main():  # pragma: no cover - container entrypoint
    import uvicorn
    # Listens on the private worker network only; the service is never published.
    uvicorn.run(create_app(), host=os.environ.get("WORKER_BROKER_HOST", "0.0.0.0"),  # nosec B104
                port=int(os.environ.get("WORKER_BROKER_PORT", "8090")), log_level="info")


if __name__ == "__main__":  # pragma: no cover
    main()
