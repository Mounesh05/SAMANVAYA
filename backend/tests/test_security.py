"""
Tests for core security module.
"""

import pytest
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)


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
