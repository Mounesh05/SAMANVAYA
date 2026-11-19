"""The explicit demo setup must refuse an unapproved database or live AI flags."""

import pytest

from scripts.setup_taskflow_demo import require_safe_environment, settings


@pytest.fixture
def local_setup(monkeypatch):
    for key, value in {"DB_NAME": "samanvaya_test", "ENVIRONMENT": "development",
                       "MONGO_URI": "mongodb://localhost:27017", "GITHUB_TOKEN": "test-token",
                       "PR_MULTI_AGENT_INTERNAL_ENABLED": False, "PR_MULTI_AGENT_MANUAL_ENABLED": False}.items():
        monkeypatch.setattr(settings, key, value)


def test_explicit_approved_local_database_is_accepted(local_setup):
    require_safe_environment("samanvaya_test", True)


@pytest.mark.parametrize("database,approved", [("production", True), ("samanvaya_test", False)])
def test_unknown_or_unapproved_database_is_refused(local_setup, database, approved):
    with pytest.raises(RuntimeError):
        require_safe_environment(database, approved)


@pytest.mark.parametrize("key,value", [("ENVIRONMENT", "production"), ("MONGO_URI", "mongodb://remote.example.com"),
    ("PR_MULTI_AGENT_INTERNAL_ENABLED", True), ("PR_MULTI_AGENT_MANUAL_ENABLED", True), ("GITHUB_TOKEN", "")])
def test_unsafe_environment_is_refused(local_setup, monkeypatch, key, value):
    monkeypatch.setattr(settings, key, value)
    with pytest.raises(RuntimeError):
        require_safe_environment("samanvaya_test", True)
