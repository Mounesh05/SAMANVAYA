"""Retain old verification keys explicitly; never rewrite signed historical rows."""

import copy
import pytest
from fastapi import HTTPException
from core import database
from core.config import settings

pytestmark = pytest.mark.anyio


async def test_rotation_retains_old_artifact_and_missing_key_fails_closed(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    from domain.services.performance_artifact_store import _read, _write
    first = await _write("performance_access_audit", {"action": "TEST"}, {"organization_id": "O"}, "tester")
    original = copy.deepcopy(await mock_db.ai_runs.find_one({"id": first["id"]}))
    assert first.get("signing_key_id"), "Signed artifacts need a retained verification key identity"
    old_key = settings.SECRET_KEY
    monkeypatch.setattr(settings, "PERFORMANCE_SIGNING_KEYS", {"old": old_key, "new": "new-test-key-material-at-least-32-characters"})
    monkeypatch.setattr(settings, "PERFORMANCE_SIGNING_KEY_ID", "new")
    monkeypatch.setattr(settings, "PERFORMANCE_LEGACY_SIGNING_KEY", old_key)
    monkeypatch.setattr(settings, "SECRET_KEY", "rotated-session-secret-unrelated-to-retained-signatures")
    # The original default identity is deliberately mapped to its retained key.
    monkeypatch.setattr(settings, "PERFORMANCE_SIGNING_KEYS", {first["signing_key_id"]: old_key, "new": "new-test-key-material-at-least-32-characters"})
    assert await _read(first["id"], "performance_access_audit") == first
    assert await mock_db.ai_runs.find_one({"id": first["id"]}) == original
    second = await _write("performance_access_audit", {"action": "TEST2"}, {"organization_id": "O"}, "tester")
    assert second["signing_key_id"] == "new"
    monkeypatch.setattr(settings, "PERFORMANCE_SIGNING_KEYS", {"new": "new-test-key-material-at-least-32-characters"})
    with pytest.raises(HTTPException) as error:
        await _read(first["id"], "performance_access_audit")
    assert error.value.status_code == 409


async def test_misconfigured_active_signing_key_fails_at_startup():
    from pydantic import ValidationError
    from core.config import Settings
    base = dict(SECRET_KEY="s" * 64, _env_file=None)
    with pytest.raises(ValidationError):
        Settings(**base, PERFORMANCE_SIGNING_KEY_ID="rotated")
    with pytest.raises(ValidationError):
        Settings(**base, PERFORMANCE_SIGNING_KEYS={"other": "k" * 40}, PERFORMANCE_SIGNING_KEY_ID="rotated")
    configured = Settings(**base, PERFORMANCE_SIGNING_KEYS={"rotated": "k" * 40}, PERFORMANCE_SIGNING_KEY_ID="rotated")
    assert configured.PERFORMANCE_SIGNING_KEY_ID == "rotated"
    assert Settings(**base).PERFORMANCE_SIGNING_KEY_ID == "application-secret"


async def test_original_v1_signature_survives_explicit_legacy_key_retention(mock_db, monkeypatch):
    import hashlib
    import hmac
    from domain.models.performance_evidence import canonical_digest
    from domain.services.performance_artifact_store import _read
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    original_key = settings.SECRET_KEY
    record = dict(schema_version="performance-claim-artifact-v1", signature_method="HMAC-SHA256-v1",
        id="legacy-v1", kind="performance_access_audit", context={"organization_id": "O"},
        payload={"action": "HISTORICAL"}, created_by="tester", created_at="2026-01-01T00:00:00+00:00")
    signature = hmac.new(original_key.encode(), canonical_digest(record).encode("ascii"), hashlib.sha256).hexdigest()
    await mock_db.ai_runs.insert_one(dict(id=record["id"], agent_type=record["kind"], output_data=record, signature=signature))
    monkeypatch.setattr(settings, "SECRET_KEY", "rotated-session-key")
    monkeypatch.setattr(settings, "PERFORMANCE_LEGACY_SIGNING_KEY", original_key)
    assert await _read("legacy-v1", "performance_access_audit") == record
    monkeypatch.setattr(settings, "PERFORMANCE_LEGACY_SIGNING_KEY", "")
    with pytest.raises(HTTPException) as error:
        await _read("legacy-v1", "performance_access_audit")
    assert error.value.status_code == 409
