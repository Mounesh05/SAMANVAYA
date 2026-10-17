"""
Application configuration loaded from environment variables or .env.
"""
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "samanvaya"
    DB_MAX_POOL_SIZE: int = 10
    DB_MIN_POOL_SIZE: int = 2

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SECURE_COOKIES: bool = False

    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    RATE_LIMIT_ENABLED: bool = True
    MAX_REQUESTS_PER_MINUTE: int = 100
    MAX_LOGIN_ATTEMPTS: int = 5

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    GITHUB_TOKEN: str = ""
    GITHUB_TIMEOUT: int = 15
    GITHUB_WEBHOOK_SECRET: str = ""
    QA_TEST_RESULTS_TOKEN: str = ""
    SAMANVAYA_PUBLIC_API_URL: str = ""

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    SENTRY_DSN: Optional[str] = None
    APM_ENABLED: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    def validate_production_settings(self) -> List[str]:
        errors = []
        if not self.is_production():
            return errors
        if not self.SECRET_KEY or "CHANGE_ME" in self.SECRET_KEY:
            errors.append("SECRET_KEY must be set to a secure value in production")
        if len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters long")
        if "localhost" in self.ALLOWED_ORIGINS.lower():
            errors.append("ALLOWED_ORIGINS must not include localhost in production")
        if not self.SECURE_COOKIES:
            errors.append("SECURE_COOKIES must be True in production")
        if not self.RATE_LIMIT_ENABLED:
            errors.append("RATE_LIMIT_ENABLED should be True in production")
        if not self.QA_TEST_RESULTS_TOKEN:
            errors.append("QA_TEST_RESULTS_TOKEN must be set for CI test-result ingestion")
        if "localhost" in self.MONGO_URI.lower() or "127.0.0.1" in self.MONGO_URI:
            errors.append("MONGO_URI should not be localhost in production")
        if self.DEBUG:
            errors.append("DEBUG must be False in production")
        return errors


settings = Settings()

if settings.is_production():
    errors = settings.validate_production_settings()
    if errors:
        import sys
        print("PRODUCTION CONFIGURATION ERRORS:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)
