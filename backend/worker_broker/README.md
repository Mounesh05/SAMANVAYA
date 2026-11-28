# Isolated workers (OPS-03)

Code-quality tools and algorithm benchmarks run developer code (or tools over
it) in fixed, prebuilt Docker images with no network, a read-only filesystem,
dropped capabilities and CPU/memory/PID limits. The public API never runs
developer code itself.

| Image | Built from | Used for |
|---|---|---|
| `samanvaya-quality:2` | `backend/quality_worker/Dockerfile` | Ruff, ESLint, TypeScript, mypy, Bandit on a pinned PR snapshot |
| `samanvaya-benchmark-python:1` | `backend/benchmark_worker/Dockerfile.python` | Python benchmarks |
| `samanvaya-benchmark-node:1` | `backend/benchmark_worker/Dockerfile.node` | JavaScript/TypeScript benchmarks and structure parsing |
| `samanvaya-worker-broker:1` | `backend/worker_broker/Dockerfile` | Internal service that runs the three images above |

The API image (`backend/Dockerfile`) includes a pinned Node binary and the
TypeScript parser from `backend/benchmark_worker/package-lock.json`. These are
used only to *parse* TypeScript for function discovery, never to run it.

## Build the images

```
docker compose -f docker-compose.workers.yml --profile images build
docker compose -f docker-compose.workers.yml build worker-broker
```

Images are never pulled at run time (`--pull=never`). Rebuild them and bump
the tag when a Dockerfile or pinned tool version changes.

## Production mode: worker broker

The API container gets **no Docker socket**. Only the worker broker has it.
The broker:

- listens on the internal `samanvaya-workers` network and is never published;
- requires `Authorization: Bearer <WORKER_BROKER_TOKEN>` (32+ characters, compared in constant time);
- runs fixed operations only: `/v1/quality/analyze`, `/v1/benchmark/run`,
  `/v1/benchmark/analyze`, `/v1/availability`. It never accepts image names,
  Docker arguments or host paths;
- runs at most `WORKER_BROKER_MAX_CONCURRENT` containers (default 2). When
  full, it answers 429 instead of queueing.

The API re-checks every quality result against the snapshot it sent: the
revision, the file hashes, the paths and the isolation provenance.

```
# 1. Start the broker
WORKER_BROKER_TOKEN=<secret> docker compose -f docker-compose.workers.yml up -d worker-broker
# 2. Start the API on the same network with
WORKER_BROKER_URL=http://worker-broker:8090
WORKER_BROKER_TOKEN=<same secret>
```

If the socket is not owned by root's group on your host, set
`DOCKER_SOCKET_GID` to its group ID (`stat -c %g /var/run/docker.sock`).

Treat access to the Docker socket as root on that host. Keep the broker on a
dedicated worker host or VM where possible.

## Development mode

Leave `WORKER_BROKER_URL` empty and run the API on a machine with the Docker
CLI. The API then starts the same images directly. Build the images first,
otherwise analyses report "Isolated quality analysis could not complete".
