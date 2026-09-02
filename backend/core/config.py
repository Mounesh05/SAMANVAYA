"""
Application configuration loaded from .env via pydantic-settings.
All settings are typed. SECRET_KEY has no default — must be set.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # ── Environment ──────────────────────────────────────────────
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = True
    
    # ── Database ──────────────────────────────────────────────────
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "samanvaya"
    DB_MAX_POOL_SIZE: int = 10
    DB_MIN_POOL_SIZE: int = 2

    # ── Auth ──────────────────────────────────────────────────────
    SECRET_KEY: str  # no default — required in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Changed from 1440 to 60
    SECURE_COOKIES: bool = False  # Set to True in production

    # ── CORS ──────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # ── Security ──────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = False  # Enable in production
    MAX_REQUESTS_PER_MINUTE: int = 100
    MAX_LOGIN_ATTEMPTS: int = 5

    # ── AI / Ollama ───────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"  # or llama3.1, mistral, etc.

    # ── GitHub ────────────────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_TIMEOUT: int = 15
    GITHUB_WEBHOOK_SECRET: str = ""  # Set to your webhook secret from GitHub
    
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
        
        # Check database is not local
        if "localhost" in self.MONGO_URI.lower() or "127.0.0.1" in self.MONGO_URI:
            errors.append("MONGO_URI should not be localhost in production")
        
        if self.DEBUG:
            errors.append("DEBUG must be False in production")
        
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
