"""
Password hashing and JWT token management.
All auth primitives live here — nowhere else.
"""

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(plain)


# Alias for compatibility
get_password_hash = hash_password


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a hashed password."""
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(payload: dict) -> str:
    """
    Create a JWT access token.
    
    Args:
        payload: Dict containing user data (employee_id, role, etc.)
    
    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {**payload, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload dict
    
    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise ValueError("Invalid or expired token")
