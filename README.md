# SAMANVAYA

SAMANVAYA combines project management, GitHub synchronization, QA evidence,
static code analysis, and engineering performance workflows. The React/Vite
frontend calls a FastAPI backend; services use repositories backed by MongoDB.
Ollama supplies optional local model explanations. Submitted benchmark code runs
only in isolated Docker workers.

## Local setup

The tested backend runtime is **Python 3.12** (CI and the backend image use it).
Python 3.14 is not certified with the current pinned native dependencies.
Use **Node.js 22**, MongoDB 4.2 or newer, and optionally Ollama.

From the repository root in PowerShell:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
npm ci --prefix frontend
npm ci --prefix backend/benchmark_worker --ignore-scripts
```

Set your own `SECRET_KEY`, MongoDB connection and database name in
[configuration template](backend/.env.example). Configure GitHub tokens and webhook secrets
only if using those integrations. Start MongoDB through your existing local
installation. For Ollama, pull the configured model and run `ollama serve`.

Run the API from the backend directory:

```powershell
cd backend
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In a separate terminal, run `npm run dev --prefix frontend` from the repository
root, then open http://localhost:5173. Employee accounts are provisioned by an
administrator; self-registration is disabled by default.

Run backend tests from the backend directory with
`.venv/Scripts/python.exe -m pytest`; run frontend tests with
`npm run test --prefix frontend -- --run`.

Build the API image with `docker build -f backend/Dockerfile -t samanvaya-backend backend`.
The image excludes local secrets and runs as UID 65532. Supply secrets at runtime
with `--env-file`; MongoDB and Ollama URLs must be reachable from the container.
JavaScript/TypeScript source discovery additionally requires the Node parser
runtime/package documented in the [discovery guide](backend/intelligence/algorithms/discovery/README.md); the base API image does not
provide that runtime. Container benchmarks use their separate worker images.

## Session and webhook lifecycle

Every authenticated request reads the current employee record. Deactivation,
role/designation/admin changes and team/project membership removal take effect
on the next request, including requests using an older JWT. Logout persists JWT
revocation in MongoDB with a TTL index. Deploying this session format requires
all existing users to log in again: unversioned JWTs are rejected so tokens
revoked by the previous in-memory store cannot revive after rollout. All API
instances must share the same database, session format, and signing settings;
restart the old instances together rather than mixing authentication versions.

Accepted GitHub events are stored before acknowledgment. The API lifespan starts
a recovery poll every five seconds, with at most four tasks per process, renewable
60-second leases, three total processing attempts, and retry backoff. Pending
events and expired leases are recovered after restart; live leases are preserved.
This is **at-least-once processing**, not exactly-once delivery of external side
effects: a crash after a side effect but before completion can repeat that effect.
Exhausted events remain failed for inspection. Shut down workers before closing
MongoDB. No Redis or new queue service is required.

Department normalization is an explicit one-time migration, if needed:
`python -m migrations.normalize_executive_departments` from the backend directory.
Startup no longer rewrites employee departments.

Dependency scanning uses the installed `pip-audit` CLI. The optional Safety
adapter remains available, but Safety is not installed in the API environment:
its current `filelock<4` requirement conflicts with the required security fixes.
Unavailable scans remain explicitly unverified. CI blocks on runtime-name/syntax
errors and dependency vulnerabilities; broader lint/type/Bandit findings remain
advisory while their existing baseline is addressed separately.

## Numeric sorting comparisons

The Code Quality screen includes opt-in, evidence-first comparisons for named
Python, JavaScript, and TypeScript sorting functions. Candidates run only in
hardened Docker Linux containers; recommendations use passing measured evidence,
with project-scoped MongoDB history and optional grounded explanations.

See [benchmark setup, Windows/Docker requirements, API, and validation](backend/benchmark_worker/README.md).
Execution is disabled by default and does not replace the existing quality or
security analyzers.
