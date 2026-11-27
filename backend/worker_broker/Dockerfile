# OPS-03: internal worker broker. Build from the backend directory:
#   docker build -f worker_broker/Dockerfile -t samanvaya-worker-broker:1 .
# It is the only service that receives the Docker socket. Never publish its port.
FROM docker:27.5.1-cli AS docker-cli

FROM python:3.12.8-slim-bookworm
ENV PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/app
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY worker_broker/requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
WORKDIR /opt/app
# Only the modules the broker runs; no API code, settings or database access.
COPY benchmark_worker/contracts.py /opt/app/benchmark_worker/contracts.py
COPY intelligence/__init__.py /opt/app/intelligence/__init__.py
COPY intelligence/algorithms/runner.py intelligence/algorithms/measurements.py /opt/app/intelligence/algorithms/
COPY intelligence/analyzers/__init__.py intelligence/analyzers/isolated.py /opt/app/intelligence/analyzers/
COPY intelligence/evidence /opt/app/intelligence/evidence
COPY worker_broker/__init__.py worker_broker/app.py /opt/app/worker_broker/
# Needs read/write on the mounted Docker socket; grant it with the socket's
# group (compose: group_add) rather than running as root.
USER 10001:10001
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/v1/health', timeout=3)"
ENTRYPOINT ["python", "-m", "worker_broker.app"]
