"""
Rate Limiting Middleware
Protects API from abuse and DoS attacks.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, FastAPI
from core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"] if settings.RATE_LIMIT_ENABLED else [],
    enabled=settings.RATE_LIMIT_ENABLED,
)


def setup_rate_limiting(app: FastAPI):
    """
    Configure rate limiting for the application.
    
    Args:
        app: FastAPI application instance
    """
    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting is DISABLED")
        return
    
    # Add limiter to app state
    app.state.limiter = limiter
    
    # Add exception handler for rate limit exceeded
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    logger.info(f"Rate limiting ENABLED: {settings.MAX_REQUESTS_PER_MINUTE} requests/minute")


# Rate limit decorators for different endpoints
def auth_rate_limit():
    """Rate limit for authentication endpoints (stricter)."""
    return limiter.limit(f"{settings.MAX_LOGIN_ATTEMPTS}/minute")


def api_rate_limit():
    """Rate limit for general API endpoints."""
    return limiter.limit(f"{settings.MAX_REQUESTS_PER_MINUTE}/minute")


def strict_rate_limit():
    """Strict rate limit for sensitive operations."""
    return limiter.limit("10/minute")
