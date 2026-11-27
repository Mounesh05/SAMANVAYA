# OPS-03: pinned Node runtime + TypeScript parser for source-only function
# discovery (intelligence/algorithms/discovery/extractors.py). Developer code
# is parsed, never executed, in the API. Isolated tools run in the worker
# images through the worker broker; this image has no Docker client or socket.
FROM node:22.14.0-bookworm-slim AS node-tools
WORKDIR /opt/benchmark_worker
COPY benchmark_worker/package.json benchmark_worker/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node binary only (no npm); the parser package comes from the lockfile above.
COPY --from=node-tools /usr/local/bin/node /usr/local/bin/node

# Copy application code
COPY . .
COPY --from=node-tools /opt/benchmark_worker/node_modules /app/benchmark_worker/node_modules

# Runtime only needs read access to the application; temporary files use /tmp.
USER 65532:65532

# Expose port
EXPOSE 8000

# Liveness only: readiness (/health/ready) is for the orchestrator's traffic checks.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health/live'); assert r.status_code == 200"

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
