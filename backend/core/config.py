"""
Application configuration loaded from .env via pydantic-settings.
All settings are typed. SECRET_KEY has no default — must be set.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "samanvaya"

    # ── Auth ──────────────────────────────────────────────────
    SECRET_KEY: str  # no default — required in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── AI / Ollama ───────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"  # or llama3.1, mistral, etc.

    # ── GitHub ────────────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_TIMEOUT: int = 15
    GITHUB_WEBHOOK_SECRET: str = ""  # Set to your webhook secret from GitHub

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
