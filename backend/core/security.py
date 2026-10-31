"""
Password hashing and JWT token management.
All auth primitives live here â€” nowhere else.
"""

from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
import bcrypt
import uuid
from threading import Lock
from .config import settings


# TODO: For production multi-instance deployments, replace in-memory storage
# with Redis to share revocation list across instances.
_revoked_tokens: dict[str, datetime] = {}
_revoked_tokens_lock = Lock()


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    pw_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


# Alias for compatibility
get_password_hash = hash_password


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a hashed password."""
    try:
        pw_bytes = plain.encode("utf-8")[:72]
        hashed_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hashed_bytes)
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
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    jti = str(uuid.uuid4())
    return jwt.encode(
        {**payload, "exp": expire, "jti": jti},
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


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength for production use.
    
    Requirements:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter  
    - At least one digit
    - At least one special character
    
    Args:
        password: Password to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    special_chars = "!@#$%^&*(),.?\":{}|<>[]\\-_=+"
    if not any(c in special_chars for c in password):
        return False, f"Password must contain at least one special character ({special_chars})"
    
    if is_password_compromised(password):
        return False, "Password is too common; choose a less predictable password"

    return True, ""


def is_password_compromised(password: str) -> bool:
    """
    Check if password is in common/compromised passwords list.
    
    In production, this should check against Have I Been Pwned API
    or a local database of compromised passwords.
    
    Args:
        password: Password to check
    
    Returns:
        True if password is compromised/common
    """
    # Common passwords that should never be allowed
    common_passwords = {
        "password", "password123", "12345678", "qwerty", "abc123",
        "password1", "admin123", "letmein", "welcome", "monkey",
        "1234567890", "password!", "Password1", "Admin123"
    }
    
    return password.lower() in common_passwords


def revoke_token(jti: str, exp_timestamp: datetime) -> None:
    """
    Revoke a token by adding its JTI to the revocation list.
    
    Args:
        jti: JWT ID (unique identifier for the token)
        exp_timestamp: Token expiration timestamp
    """
    with _revoked_tokens_lock:
        _revoked_tokens[jti] = exp_timestamp
        _cleanup_expired_revocations()


def is_token_revoked(jti: str) -> bool:
    """
    Check if a token has been revoked.
    
    Args:
        jti: JWT ID to check
    
    Returns:
        True if token is revoked
    """
    with _revoked_tokens_lock:
        _cleanup_expired_revocations()
        return jti in _revoked_tokens


def _cleanup_expired_revocations() -> None:
    """
    Remove expired tokens from the revocation list.
    Called automatically during revocation checks to prevent memory leaks.
    """
    now = datetime.now(timezone.utc)
    expired = [j for j, exp in _revoked_tokens.items() if exp < now]
    for j in expired:
        del _revoked_tokens[j]
