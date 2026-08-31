"""
Shared test fixtures and configuration.
"""

import os
import sys
import pytest

# Ensure backend directory is in Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Set test environment variables before any imports
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-12345"
os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ["DB_NAME"] = "samanvaya_test"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["OLLAMA_MODEL"] = "llama3.2"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
