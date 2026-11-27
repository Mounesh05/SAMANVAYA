"""Shared fixtures and environment for backend tests."""

import os
import sys
from uuid import uuid4

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Application settings read these values during test module imports.
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-12345"
os.environ["MONGO_URI"] = "mongodb://localhost:27017"
# A few legacy singleton services bind a real collection during import. Never
# let those writes target the populated pilot database, even when most tests
# replace their repositories with in-memory doubles.
os.environ["DB_NAME"] = "samanvaya_pytest_" + uuid4().hex
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["OLLAMA_MODEL"] = "llama3.2"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def python_dependency_project(tmp_path):
    """Isolated manifest for mocked pip-audit and Safety command tests."""
    (tmp_path / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
async def mock_db():
    """Give each test its own in-memory database."""
    client = AsyncMongoMockClient()
    try:
        yield client[os.getenv("DB_NAME", "samanvaya_test")]
    finally:
        client.close()
