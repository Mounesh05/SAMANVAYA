"""
Tests for core security module.
"""

import pytest
from datetime import datetime, timezone, timedelta
import jwt
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    revoke_token,
    is_token_revoked,
)
from core.config import settings


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_returns_hash(self):
        pwd = "test_password_123"
        hashed = hash_password(pwd)
        assert hashed != pwd
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        pwd = "secure_password"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_verify_password_incorrect(self):
        pwd = "secure_password"
        hashed = hash_password(pwd)
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_empty(self):
        hashed = hash_password("something")
        assert verify_password("", hashed) is False

    def test_hash_different_each_time(self):
        pwd = "same_password"
        h1 = hash_password(pwd)
        h2 = hash_password(pwd)
        # bcrypt uses random salt, so hashes should differ
        assert h1 != h2
        # But both should verify correctly
        assert verify_password(pwd, h1) is True
        assert verify_password(pwd, h2) is True


class TestJWT:
    """Test JWT token creation and decoding."""

    def test_create_and_decode_token(self):
        payload = {
            "sub": "E001",
            "employee_id": "E001",
            "email": "test@company.com",
            "name": "Test User",
            "role": "DEVELOPER",
        }
        token = create_access_token(payload)
        decoded = decode_token(token)
        assert decoded["employee_id"] == "E001"
        assert decoded["email"] == "test@company.com"
        assert decoded["role"] == "DEVELOPER"
        assert "exp" in decoded
        assert "jti" in decoded  # New: JTI should be present

    def test_decode_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token("invalid.token.here")

    def test_decode_tampered_token(self):
        payload = {"sub": "E001", "employee_id": "E001"}
        token = create_access_token(payload)
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token(tampered)


class TestJWTLogout:
    """Test JWT logout and token revocation."""

    @pytest.mark.anyio
    async def test_token_revocation(self, mock_db, monkeypatch):
        monkeypatch.setattr("core.database.get_db", lambda: mock_db)
        """Test that a token can be revoked and is properly rejected."""
        # Create a token
        payload = {"sub": "E001", "employee_id": "E001"}
        token = create_access_token(payload)
        decoded = decode_token(token)
        jti = decoded["jti"]
        exp = decoded["exp"]
        
        # Token should not be revoked initially
        assert not await is_token_revoked(jti)
        
        # Revoke the token
        exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
        await revoke_token(jti, exp_datetime)
        
        # Token should now be revoked
        assert await is_token_revoked(jti)

    def test_token_without_jti_handled_gracefully(self):
        """Test that tokens without jti don't crash the system."""
        # Manually create a token without jti (simulating old tokens)
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        payload_without_jti = {
            "sub": "E001",
            "employee_id": "E001",
            "exp": expire
        }
        old_token = jwt.encode(
            payload_without_jti,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # Decode should work
        decoded = decode_token(old_token)
        assert decoded["employee_id"] == "E001"
        assert "jti" not in decoded
        
        # Decoding legacy JWT syntax remains possible, but authentication now
        # requires a versioned session and JTI; old sessions must log in again.
        jti = decoded.get("jti")
        assert jti is None

    @pytest.mark.anyio
    async def test_expired_revocations_cleaned_up(self, mock_db, monkeypatch):
        monkeypatch.setattr("core.database.get_db", lambda: mock_db)
        """Test that expired revoked tokens are automatically cleaned up."""
        # Create a token that expired in the past
        past_expiration = datetime.now(timezone.utc) - timedelta(minutes=1)
        jti_expired = "expired-jti-123"
        
        # Create a token that will expire in the future
        future_expiration = datetime.now(timezone.utc) + timedelta(minutes=30)
        jti_future = "future-jti-456"
        
        # Revoke both tokens
        await revoke_token(jti_expired, past_expiration)
        await revoke_token(jti_future, future_expiration)
        
        # Check that the future one is still revoked
        assert await is_token_revoked(jti_future)
        
        # Expired records are ignored even before MongoDB's TTL sweep runs.
        assert not await is_token_revoked(jti_expired)
        
        # Verify the future token is still in the store
        assert await is_token_revoked(jti_future)

    @pytest.mark.anyio
    async def test_revoked_token_rejected_by_get_current_user(self, mock_db, monkeypatch):
        monkeypatch.setattr("core.database.get_db", lambda: mock_db)
        await mock_db.users.insert_one({"employee_id": "E001", "role": "DEVELOPER", "is_active": True})
        """Test that get_current_user rejects revoked tokens with proper error."""
        from core.dependencies import get_current_user
        
        # Create a valid token
        payload = {"sub": "E001", "employee_id": "E001", "role": "DEVELOPER"}
        token = create_access_token(payload)
        decoded = decode_token(token)
        jti = decoded["jti"]
        exp_datetime = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        
        # Token should work before revocation
        # Call get_current_user with the token - it should succeed
        result = await get_current_user(authorization=f"Bearer {token}")
        assert result["employee_id"] == "E001"
        
        # Now revoke the token
        await revoke_token(jti, exp_datetime)
        
        # Attempt to use the revoked token - should raise HTTPException with 401
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token has been revoked"
