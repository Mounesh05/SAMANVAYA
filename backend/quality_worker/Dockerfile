FROM node:22.14.0-bookworm-slim AS tools
RUN npm install --prefix /opt/tools --ignore-scripts --no-audit --no-fund eslint@9.22.0 typescript@5.7.3 @typescript-eslint/parser@8.26.0
FROM python:3.12.8-slim-bookworm
ENV PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/app HOME=/tmp XDG_CACHE_HOME=/tmp NPM_CONFIG_OFFLINE=true MYPY_CACHE_DIR=/tmp/mypy
COPY --from=tools /usr/local/bin/node /usr/local/bin/node
COPY --from=tools /opt/tools /opt/tools
COPY --from=tools /usr/local/lib/node_modules/npm /opt/npm
COPY quality_worker/requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
COPY intelligence/analyzers /opt/app/intelligence/analyzers
COPY intelligence/evidence /opt/app/intelligence/evidence
COPY intelligence/algorithms/discovery /opt/app/intelligence/algorithms/discovery
COPY domain/models/project_code_config.py /opt/app/domain/models/project_code_config.py
COPY domain/services/code_quality_service.py /opt/app/domain/services/code_quality_service.py
COPY quality_worker/worker.py /opt/app/worker.py
COPY quality_worker/eslint.config.mjs /opt/tools/eslint.config.mjs
RUN mkdir /opt/quality-bin && printf '#!/bin/sh\nexec node /opt/tools/node_modules/eslint/bin/eslint.js --no-config-lookup --config /opt/tools/eslint.config.mjs "$@"\n' > /opt/quality-bin/eslint && printf '#!/bin/sh\nexec node /opt/tools/node_modules/typescript/bin/tsc "$@"\n' > /opt/quality-bin/tsc && printf '#!/bin/sh\nexec python -I -m pip_audit --disable-pip --no-deps --timeout 5 "$@"\n' > /opt/quality-bin/pip-audit && chmod 755 /opt/quality-bin/*
RUN printf '#!/bin/sh\nexec python -I -m mypy --config-file=/dev/null --no-incremental --follow-imports=skip "$@"\n' > /opt/quality-bin/mypy && printf '#!/bin/sh\nexec node /opt/npm/bin/npm-cli.js "$@"\n' > /opt/quality-bin/npm && chmod 755 /opt/quality-bin/*
ENV PATH=/opt/quality-bin:/usr/local/bin:/usr/bin:/bin
WORKDIR /opt/app
USER 65532:65532
ENTRYPOINT ["python", "-B", "/opt/app/worker.py"]
