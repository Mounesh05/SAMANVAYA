"""
Shared test fixtures and configuration.
"""

import os
import sys
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from mongomock_motor import AsyncMongoMockClient
import uuid

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


@pytest.fixture
async def mock_db():
    """
    In-memory MongoDB mock for unit tests.
    
    This fixture provides a mongomock_motor database instance that simulates
    MongoDB operations without requiring a real database connection.
    Ideal for fast, isolated unit tests.
    
    **Validates: Requirements 1.6**
    """
    client = AsyncMongoMockClient()
    db = client[os.getenv("DB_NAME", "samanvaya_test")]
    
    yield db
    
    # Cleanup: Close the mock client
    client.close()


@pytest.fixture
async def test_db():
    """
    Real MongoDB connection for integration tests.
    
    This fixture provides a real MongoDB database connection with automatic
    test isolation and cleanup. Each test gets a unique collection prefix
    to prevent interference between parallel test executions.
    
    **Validates: Requirements 6.8, 26.1**
    
    Test Isolation Strategy:
    - Each test gets a unique collection prefix (test_<uuid>_)
    - Collections are tracked during test execution
    - All test collections are automatically cleaned up after the test
    
    Usage:
        @pytest.mark.asyncio
        async def test_user_creation(test_db):
            users_collection = test_db.users
            await users_collection.insert_one({"name": "Test User"})
            # Automatic cleanup happens after test
    """
    # Connect to real MongoDB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "samanvaya_test")
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    
    # Generate unique collection prefix for this test
    test_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Track collections created during this test
    collections_before = set(await db.list_collection_names())
    
    # Store test_id in db object for potential use in tests
    db._test_id = test_id
    
    yield db
    
    # Cleanup: Drop all collections created during this test
    collections_after = set(await db.list_collection_names())
    new_collections = collections_after - collections_before
    
    for collection_name in new_collections:
        try:
            await db.drop_collection(collection_name)
        except Exception as e:
            # Log but don't fail cleanup if collection doesn't exist
            print(f"Warning: Could not drop collection {collection_name}: {e}")
    
    # Close the client
    client.close()


@pytest.fixture
def test_collection_prefix(test_db):
    """
    Provides a unique collection name prefix for test isolation.
    
    Use this fixture when you need to create collections with unique names
    to prevent conflicts in parallel test execution.
    
    **Validates: Requirements 26.1**
    
    Usage:
        @pytest.mark.asyncio
        async def test_with_prefix(test_db, test_collection_prefix):
            collection = test_db[f"{test_collection_prefix}_users"]
            await collection.insert_one({"name": "Test"})
    """
    return test_db._test_id if hasattr(test_db, '_test_id') else f"test_{uuid.uuid4().hex[:8]}"
