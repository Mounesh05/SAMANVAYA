"""
Application configuration loaded from .env via pydantic-settings.
All settings are typed. SECRET_KEY has no default — must be set.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from typing import List, Optional


class Settings(BaseSettings):
    # ── Environment ──────────────────────────────────────────────
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = True
    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = Field(default=8000, ge=1, le=65535)
    PR_MULTI_AGENT_INTERNAL_ENABLED: bool = False
    PR_MULTI_AGENT_MANUAL_ENABLED: bool = False  # Manual API/UI worker, development/test only.
    RELEASE_MANAGEMENT_ENABLED: bool = False
    RELEASE_TRUSTED_WORKFLOW_PATH: str = ""
    RELEASE_TRUSTED_WORKFLOW_SHA256: str = ""
    RELEASE_TRUSTED_BUILD_REF: str = "main"
    RELEASE_REQUIRED_TEST_SUITES: str = ""  # Comma-separated artifact-name/JUnit-path identities.
    RELEASE_MIN_COVERAGE_PERCENT: float = Field(default=0, ge=0, le=100)
    
    # ── Database ──────────────────────────────────────────────────
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "samanvaya"
    DEFAULT_ORG_ID: str = "ORG001"
    DB_MAX_POOL_SIZE: int = 10
    DB_MIN_POOL_SIZE: int = 2

    # ── Auth ──────────────────────────────────────────────────────
    SECRET_KEY: str  # no default — required in .env
    # Retained performance-artifact verification keys; never expose in APIs/logs.
    PERFORMANCE_SIGNING_KEY_ID: str = "application-secret"
    PERFORMANCE_SIGNING_KEYS: dict[str, str] = Field(default_factory=dict, repr=False)
    PERFORMANCE_LEGACY_SIGNING_KEY: str = Field(default="", repr=False)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Changed from 1440 to 60
    SECURE_COOKIES: bool = False  # Set to True in production

    # ── CORS ──────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # ── Security ──────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True  # Rate limiting on by default
    MAX_REQUESTS_PER_MINUTE: int = Field(default=100, gt=0)
    MAX_LOGIN_ATTEMPTS: int = Field(default=5, gt=0)
    # Public POST /api/auth/register (DEVELOPER role only). Off by default;
    # HR/admin create accounts via POST /api/employees instead.
    ALLOW_SELF_REGISTRATION: bool = False
    DEMO_SETUP_SECRET: str = ""

    # ── AI / Ollama ───────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"  # or llama3.1, mistral, etc.
    # Read timeout for one model call. CPU-only hosts need more (often 300+).
    OLLAMA_INFERENCE_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=1800)
    # AI-01: per-specialist limit for the PR multi-agent workflow.
    PR_AGENT_SPECIALIST_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=900)

    # ── Isolated workers (OPS-03) ─────────────────────────────────
    # Empty: the API runs the fixed worker images through the local Docker CLI
    # (development). Set: the API calls the internal worker broker instead and
    # never needs Docker access itself (production).
    WORKER_BROKER_URL: str = ""
    WORKER_BROKER_TOKEN: str = ""
    WORKER_BROKER_TIMEOUT_SECONDS: float = Field(default=180.0, gt=0, le=900)

    # ── Background work limits (CQ-05, AI-02) ─────────────────────
    CODE_QUALITY_MAX_CONCURRENT_RUNS: int = Field(default=2, ge=1, le=16)
    CODE_QUALITY_MAX_PENDING_PER_ORG: int = Field(default=20, ge=1, le=1000)
    PR_WORKFLOW_MAX_ACTIVE_PER_ACTOR: int = Field(default=3, ge=1, le=100)
    PR_WORKFLOW_MAX_ACTIVE_PER_ORG: int = Field(default=20, ge=1, le=1000)
    PR_WORKFLOW_MAX_ACTIVE_TOTAL: int = Field(default=100, ge=1, le=10000)

    # ── Evaluation policy (EV-05) ─────────────────────────────────
    # Manual 1-10 baseline scores blend into the PR-only advisory score. Off
    # until the organisation approves a calibrated human-score policy.
    EVALUATION_HUMAN_BASELINE_ENABLED: bool = False

    # ── GitHub ────────────────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_TIMEOUT: int = 15
    GITHUB_WEBHOOK_SECRET: str = ""  # Set to your webhook secret from GitHub
    # Background check of linked repositories for new or changed pull requests,
    # for installs GitHub cannot reach with webhooks (e.g. localhost). 0 = off.
    GITHUB_POLL_INTERVAL_SECONDS: int = 180
    QA_TEST_RESULTS_TOKEN: str = ""  # Token used by CI to submit test results
    SAMANVAYA_PUBLIC_API_URL: str = ""  # Public HTTPS URL used by provisioned CI workflows
    
    # Opt in only after configuring isolated Docker Linux benchmark workers.
    ALGORITHM_BENCHMARK_ENABLED: bool = False

    # ── Logging ───────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT: str = "json"  # json or text
    
    # ── Monitoring ────────────────────────────────────────────────
    SENTRY_DSN: Optional[str] = None  # For error tracking
    APM_ENABLED: bool = False  # Application Performance Monitoring

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @model_validator(mode="after")
    def _active_signing_key_is_configured(self):
        """Fail at startup instead of rejecting every signed performance write at runtime."""
        if self.PERFORMANCE_SIGNING_KEYS:
            if not self.PERFORMANCE_SIGNING_KEYS.get(self.PERFORMANCE_SIGNING_KEY_ID):
                raise ValueError("PERFORMANCE_SIGNING_KEY_ID must name a non-empty key in PERFORMANCE_SIGNING_KEYS")
        elif self.PERFORMANCE_SIGNING_KEY_ID != "application-secret":
            raise ValueError("PERFORMANCE_SIGNING_KEYS must be configured for a custom PERFORMANCE_SIGNING_KEY_ID")
        return self

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"
    
    def validate_production_settings(self) -> List[str]:
        """
        Validate that all required production settings are configured.
        Returns list of errors, empty if all good.
        """
        errors = []
        
        if not self.is_production():
            return errors  # Only validate in production
        
        # Check SECRET_KEY is not default
        if not self.SECRET_KEY or "CHANGE_ME" in self.SECRET_KEY:
            errors.append("SECRET_KEY must be set to a secure value in production")
        
        if len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters long")
        
        # Check CORS is restricted
        if "localhost" in self.ALLOWED_ORIGINS.lower():
            errors.append("ALLOWED_ORIGINS must not include localhost in production")
        
        # Check security settings
        if not self.SECURE_COOKIES:
            errors.append("SECURE_COOKIES must be True in production")
        
        if not self.RATE_LIMIT_ENABLED:
            errors.append("RATE_LIMIT_ENABLED should be True in production")

        if not self.QA_TEST_RESULTS_TOKEN:
            errors.append("QA_TEST_RESULTS_TOKEN must be set for CI test-result ingestion")
        
        # Check database is not local
        if "localhost" in self.MONGO_URI.lower() or "127.0.0.1" in self.MONGO_URI:
            errors.append("MONGO_URI should not be localhost in production")
        
        if self.DEBUG:
            errors.append("DEBUG must be False in production")

        if self.WORKER_BROKER_URL and len(self.WORKER_BROKER_TOKEN) < 32:
            errors.append("WORKER_BROKER_TOKEN must be at least 32 characters when WORKER_BROKER_URL is set")

        return errors


settings = Settings()

# Validate on startup if production
if settings.is_production():
    errors = settings.validate_production_settings()
    if errors:
        import sys
        print("=" * 60)
        print("PRODUCTION CONFIGURATION ERRORS:")
        print("=" * 60)
        for error in errors:
            print(f"❌ {error}")
        print("=" * 60)
        print("\nFix these errors before deploying to production!")
        sys.exit(1)
