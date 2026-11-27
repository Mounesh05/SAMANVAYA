"""
Samanvaya FastAPI application entry point.
All routers will be registered here with their URL prefixes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.database import col, close_db
from core.config import settings
import asyncio
import time
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
import uuid

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Index initialisers that protect security or idempotency. If one of them fails
# the service still starts (so it can recover), but readiness reports 503.
REQUIRED_INDEXES = ("hitl", "qa", "token_revocation", "blocked_work", "release")
index_failures: set[str] = set()


async def _index_initializers():
    """(name, coroutine function) pairs, resolved at call time so tests can patch them."""
    from intelligence.baselines.repository_baseline import RepositoryBaseline
    from domain.services.hitl_workflow_service import hitl_service
    from repositories.qa_repository import QARepository
    from core.security import ensure_revocation_indexes
    from domain.services.pm_blocked_work import ensure_blocked_work_indexes
    from domain.services.release_management import ensure_indexes as ensure_release_indexes
    return [
        ("repository_baseline", RepositoryBaseline().ensure_index),
        ("hitl", hitl_service._ensure_indexes),
        ("qa", QARepository().ensure_indexes),
        ("token_revocation", ensure_revocation_indexes),
        ("blocked_work", ensure_blocked_work_indexes),
        ("release", ensure_release_indexes),
    ]


async def ensure_all_indexes() -> set[str]:
    """Run every initialiser independently; one failure no longer skips the rest."""
    failures: set[str] = set()
    try:
        initializers = await _index_initializers()
    except Exception:
        logger.exception("Index initialisers could not be loaded")
        index_failures.clear()
        index_failures.update(REQUIRED_INDEXES)
        return set(REQUIRED_INDEXES)
    for name, initialise in initializers:
        try:
            await initialise()
        except Exception as exc:
            failures.add(name)
            logger.error("Database index initialisation failed: %s (%s)", name, type(exc).__name__)
    index_failures.clear()
    index_failures.update(failures)
    if not failures:
        logger.info("✓ Database indexes created/verified")
    return failures


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # Startup: create database indexes (each independently; see ensure_all_indexes).
    await ensure_all_indexes()

    # Use the route's processor and stop its owned tasks before closing MongoDB.
    # Start independently of optional indexes so an unrelated index failure
    # cannot silently disable event recovery.
    from api.routes.webhooks import event_processor
    from domain.services.pr_workflow_runtime import PRWorkflowRuntime
    from domain.services.github_pr_poller import pr_poller
    from api.routes.code_quality import recovery as code_quality_recovery
    workflow_runtime = PRWorkflowRuntime()
    app.state.pr_workflow_runtime = workflow_runtime
    try:
        await event_processor.start()
        await workflow_runtime.start()
        # Pull requests of linked repositories without webhooks (e.g. localhost).
        await pr_poller.start()
        # CQ-05: restart never-claimed analysis runs; fail interrupted ones.
        code_quality_recovery.start()
        yield
    finally:
        await code_quality_recovery.stop()
        await pr_poller.stop()
        await workflow_runtime.stop()
        await event_processor.stop()
        await close_db()


app = FastAPI(
    title="Samanvaya API",
    version="1.0.0",
    description="AI-powered software project execution and engineering intelligence platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# ── Wire Rate Limiting ──
from core.rate_limiting import setup_rate_limiting
setup_rate_limiting(app)

# ── Request ID Middleware ──
@app.middleware('http')
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    return await call_next(request)

# ── Global Exception Handlers ──
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.error(f'Request {request_id} failed: {exc}', exc_info=True)
    return JSONResponse(
        status_code=500,
        content={'detail': f'Internal server error. Request ID: {request_id}'}
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with logging."""
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={"path": request.url.path, "method": request.method}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


def sanitize_validation_errors(errors) -> list[dict]:
    """Keep only where and why validation failed.

    Pydantic includes the submitted value (``input``) and sometimes ``ctx``/``url``;
    for sign-in, employee or CI payloads that value can be a password or token, so it
    is never returned or logged.
    """
    safe = []
    for error in errors:
        safe.append({
            "type": str(error.get("type", "value_error")),
            "loc": [part if isinstance(part, (str, int)) else str(part) for part in error.get("loc", ())],
            "msg": str(error.get("msg", "Invalid value")),
        })
    return safe


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return validation feedback without echoing or logging submitted values."""
    errors = sanitize_validation_errors(exc.errors())
    logger.warning(
        "Validation error at %s",
        [{"loc": error["loc"], "type": error["type"]} for error in errors],
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(errors)},
    )


# ── Request Logging Middleware ──
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    
    # Log request
    logger.info(f"→ {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log response with timing
    duration = time.time() - start_time
    logger.info(
        f"← {request.method} {request.url.path} - {response.status_code} - {duration:.3f}s"
    )
    
    return response


# ── Security Headers Middleware ──
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Only add security headers in production or staging
    if not settings.is_development():
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    
    return response


# ── Request Size Limit Middleware ──
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size to prevent DoS attacks via Content-Length or chunked encoding."""
    max_size = 10_000_000  # 10MB
    
    # Fast path: check Content-Length header if present
    content_length = request.headers.get('content-length')
    if content_length:
        content_length = int(content_length)
        if content_length > max_size:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body too large. Maximum size is {max_size} bytes."}
            )
    
    # For chunked/streamed requests without Content-Length, count bytes during streaming
    received_bytes = 0
    original_receive = request.receive
    
    async def counting_receive():
        nonlocal received_bytes
        message = await original_receive()
        
        if message["type"] == "http.request":
            body_chunk = message.get("body", b"")
            received_bytes += len(body_chunk)
            
            if received_bytes > max_size:
                # Raise exception that will be caught by exception handlers
                raise StarletteHTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Request body too large. Maximum size is {max_size} bytes."
                )
        
        return message
    
    # Replace receive with counting version
    request._receive = counting_receive
    
    return await call_next(request)




# ━━ Root endpoint ━━
@app.get("/")
async def root():
    return {
        "message": "Samanvaya API v1.0 — AI-powered engineering intelligence platform",
        "status": "operational",
        "version": "1.0.0",
    }


# ━━ Health checks ━━
DATABASE_CHECK_TIMEOUT_SECONDS = 3.0


async def _database_status() -> str:
    """Bounded MongoDB round trip; a slow or failed database is not 'connected'."""
    try:
        await asyncio.wait_for(col("users").find_one({}, {"_id": 1}), DATABASE_CHECK_TIMEOUT_SECONDS)
        return "connected"
    except Exception:
        return "connection_failed"


@app.get("/health/live")
async def liveness_check():
    """Liveness: the process is running and serving requests. No dependency checks."""
    return {"status": "alive", "version": "1.0.0"}


@app.get("/health")
@app.get("/health/ready")
async def health_check():
    """
    Readiness: 200 only when MongoDB answers and required indexes exist (503 otherwise).
    Ollama and GitHub are optional; when they are unavailable the service is 'degraded'.
    """
    from agents.llm_provider import check_ollama_connection
    from integrations.github.client import GitHubClient

    db_status = await _database_status()
    # The provider check uses a blocking HTTP client, so keep it off the event loop.
    ollama_status = await asyncio.to_thread(check_ollama_connection)

    github_status = "not_configured"
    if settings.GITHUB_TOKEN:
        try:
            client = GitHubClient()
            github_status = "configured" if await client.check_token_validity() else "invalid_token"
        except Exception:
            github_status = "error"

    missing_indexes = sorted(index_failures & set(REQUIRED_INDEXES))
    ready = db_status == "connected" and not missing_indexes
    if not ready:
        overall = "unhealthy"
    elif not ollama_status or github_status in {"invalid_token", "error"}:
        overall = "degraded"
    else:
        overall = "healthy"
    body = {
        "status": overall,
        "dependencies": {
            "database": db_status,
            "indexes": "missing" if missing_indexes else "ready",
            "ollama": "connected" if ollama_status else "not_available",
            "github": github_status,
        },
        "version": "1.0.0",
    }
    if missing_indexes:
        body["missing_indexes"] = missing_indexes
    return JSONResponse(status_code=200 if ready else status.HTTP_503_SERVICE_UNAVAILABLE, content=body)


# ━━ Register API Routers ━━
from api.routes import (
    auth, projects, sprints, intelligence, stories, tasks, github, ai, setup,
    cicd_logs, qa_test_runs, qa_management, performance, employees, teams, evaluation,
    boards, comments, activity, notifications, webhooks, code_quality,
    recommendations, traceability, risk_configurations, audit, transfers,
    reports, pr_workflows, release_decisions, release_gates,
)
from api.roles import developer, lead, pm, ceo, hr, qa, devops

# Core feature routes
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(setup.router, prefix="/api/setup", tags=["Local Setup"])
app.include_router(employees.router, prefix="/api/employees", tags=["Employee Management"])
app.include_router(teams.router, prefix="/api/teams", tags=["Team Management"])
app.include_router(transfers.router, prefix="/api/transfers", tags=["Transfers"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
from api.routes import release_gate_settings, releases
app.include_router(release_gate_settings.router, prefix="/api/projects", tags=["Release gate settings"])
app.include_router(releases.router, prefix="/api/projects", tags=["Release management"])
app.include_router(sprints.router, prefix="/api/sprints", tags=["Sprints"])
app.include_router(stories.router, prefix="/api/stories", tags=["Stories"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(release_decisions.router, prefix="/api/tasks", tags=["Task release decisions"])
app.include_router(release_gates.router, prefix="/api/release-gates", tags=["Release gates"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["Intelligence Engine"])
app.include_router(github.router, prefix="/api/github", tags=["GitHub Integration"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI Agents"])
app.include_router(pr_workflows.router, prefix="/api/ai/workflows/v1")
app.include_router(cicd_logs.router, prefix="/api/cicd-logs", tags=["CI/CD Logs"])
app.include_router(qa_test_runs.router, prefix="/api/qa", tags=["QA Test Results"])
app.include_router(qa_management.router, prefix="/api/qa", tags=["QA Management"])
# QA CI test automation (CR-002): was never registered, so Enable CI had no endpoint
from api.routes import qa_ci_provisioning
app.include_router(qa_ci_provisioning.router, prefix="/api/qa", tags=["QA CI Provisioning"])
app.include_router(performance.router, prefix="/api/performance", tags=["Developer Performance"])

# ━━ New Features ━━
app.include_router(boards.router, prefix="/api/boards", tags=["Boards"])
app.include_router(comments.router, prefix="/api/comments", tags=["Comments"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity Feed"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])

# Incident reporting (CR-001); triage arrives with CR-003
from api.routes import incidents
app.include_router(incidents.router, prefix="/api/incidents", tags=["Incidents"])

# Code Quality & Multi-Language Intelligence Engine
app.include_router(code_quality.router, prefix="/api/code-quality", tags=["Code Quality"])

# Evidence-first, opt-in isolated algorithm comparisons.
from api.routes import algorithms
app.include_router(algorithms.router, prefix="/api/algorithms", tags=["Algorithm Intelligence"])

# Risk Configuration Management (Production-scale configurable weights)
app.include_router(risk_configurations.router, prefix="/api/risk-configurations", tags=["Risk Configuration"])

# AI Evaluation (Requires Auth)
app.include_router(evaluation.router, prefix="/api/evaluation", tags=["AI Evaluation"])

# Recommendations & Traceability (Phase 1)
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])
app.include_router(traceability.router, prefix="/api/traceability", tags=["Traceability"])

# Phase 1.4: Enhanced Notifications
from api.routes import notification_preferences
app.include_router(notification_preferences.router, prefix="/api/notifications", tags=["Notification Preferences"])

# Phase 3: Approvals & HITL Workflow
from api.routes import approvals
app.include_router(approvals.router, prefix="/api/approvals", tags=["Approvals"])

# Audit Logs (Role-based filtering)
app.include_router(audit.router, prefix="/api/audit", tags=["Audit Logs"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])  # CR-011

# Role-specific dashboards
app.include_router(developer.router, prefix="/api/role/developer", tags=["Role: Developer"])
app.include_router(lead.router, prefix="/api/role/lead", tags=["Role: Lead"])
app.include_router(pm.router, prefix="/api/role/pm", tags=["Role: PM"])
app.include_router(ceo.router, prefix="/api/role/ceo", tags=["Role: CEO"])
app.include_router(hr.router, prefix="/api/role/hr", tags=["Role: HR"])
app.include_router(qa.router, prefix="/api/role/qa", tags=["Role: QA"])
app.include_router(devops.router, prefix="/api/role/devops", tags=["Role: DevOps"])
