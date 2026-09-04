"""
Samanvaya FastAPI application entry point.
All routers will be registered here with their URL prefixes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.database import col, close_db
from core.config import settings


from contextlib import asynccontextmanager
from core.database import col, close_db
from core.config import settings
import time
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # Startup: nothing to do (client is created lazily)
    yield
    # Shutdown: close MongoDB connection
    await close_db()


app = FastAPI(
    title="Samanvaya API",
    version="1.0.0",
    description="AI-powered software project execution and engineering intelligence platform",
    lifespan=lifespan,
)

# CORS configuration - properly configured from environment
allowed_origins = getattr(settings, 'ALLOWED_ORIGINS', "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Global Exception Handlers ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions to prevent information leakage."""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method}
    )
    
    # Don't expose internal errors in production
    if settings.is_production():
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error. Please contact support."}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "type": type(exc).__name__}
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
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed feedback."""
    logger.warning(
        f"Validation error: {exc.errors()}",
        extra={"path": request.url.path, "method": request.method}
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
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
    """Limit request body size to prevent DoS attacks."""
    content_length = request.headers.get('content-length')
    if content_length:
        content_length = int(content_length)
        max_size = 10_000_000  # 10MB
        if content_length > max_size:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body too large. Maximum size is {max_size} bytes."}
            )
    
    return await call_next(request)




# ━━ Root endpoint ━━
@app.get("/")
async def root():
    return {
        "message": "Samanvaya API v1.0 — AI-powered engineering intelligence platform",
        "status": "operational",
        "version": "1.0.0",
    }


# ━━ Health check ━━
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns system status and dependencies.
    """
    from agents.llm_provider import check_ollama_connection
    from integrations.github.client import GitHubClient
    
    # Check dependencies
    ollama_status = check_ollama_connection()
    
    # Check GitHub token (if configured)
    github_status = "not_configured"
    if settings.GITHUB_TOKEN:
        try:
            client = GitHubClient()
            github_status = "configured" if await client.check_token_validity() else "invalid_token"
        except Exception:
            github_status = "error"
    
    # Check database connection
    db_status = "unknown"
    try:
        # Try a simple database operation
        await col("users").count_documents({})
        db_status = "connected"
    except Exception:
        db_status = "connection_failed"
    
    return {
        "status": "healthy",
        "dependencies": {
            "database": db_status,
            "ollama": "connected" if ollama_status else "not_available",
            "github": github_status,
        },
        "version": "1.0.0",
    }


# ━━ Register API Routers ━━
from api.routes import (
    auth, projects, sprints, intelligence, stories, tasks, github, ai,
    cicd_logs, performance, employees, teams, evaluation,
    boards, comments, activity, notifications, webhooks, code_quality,
    recommendations, traceability, risk_configurations,
)
from api.roles import developer, lead, pm, ceo, hr, qa, devops

# Core feature routes
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(employees.router, prefix="/api/employees", tags=["Employee Management"])
app.include_router(teams.router, prefix="/api/teams", tags=["Team Management"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(sprints.router, prefix="/api/sprints", tags=["Sprints"])
app.include_router(stories.router, prefix="/api/stories", tags=["Stories"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["Intelligence Engine"])
app.include_router(github.router, prefix="/api/github", tags=["GitHub Integration"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI Agents"])
app.include_router(cicd_logs.router, prefix="/api/cicd-logs", tags=["CI/CD Logs"])
app.include_router(performance.router, prefix="/api/performance", tags=["Developer Performance"])

# ━━ New Features ━━
app.include_router(boards.router, prefix="/api/boards", tags=["Boards"])
app.include_router(comments.router, prefix="/api/comments", tags=["Comments"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity Feed"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])

# Code Quality & Multi-Language Intelligence Engine
app.include_router(code_quality.router, prefix="/api/code-quality", tags=["Code Quality"])

# Risk Configuration Management (Production-scale configurable weights)
app.include_router(risk_configurations.router, prefix="/api/risk-configurations", tags=["Risk Configuration"])
app.include_router(code_quality.router, prefix="/api/code-quality", tags=["Code Quality"])

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

# Role-specific dashboards
app.include_router(developer.router, prefix="/api/role/developer", tags=["Role: Developer"])
app.include_router(lead.router, prefix="/api/role/lead", tags=["Role: Lead"])
app.include_router(pm.router, prefix="/api/role/pm", tags=["Role: PM"])
app.include_router(ceo.router, prefix="/api/role/ceo", tags=["Role: CEO"])
app.include_router(hr.router, prefix="/api/role/hr", tags=["Role: HR"])
app.include_router(qa.router, prefix="/api/role/qa", tags=["Role: QA"])
app.include_router(devops.router, prefix="/api/role/devops", tags=["Role: DevOps"])


