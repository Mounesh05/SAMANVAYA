"""
Motor (async MongoDB) client and collection references.
Single client instance — collections accessed by name.
Client is created lazily on first use, not at import time.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import settings

_client: AsyncIOMotorClient = None


def get_client() -> AsyncIOMotorClient:
    """Get or create MongoDB client singleton."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Get the Samanvaya database."""
    return get_client()[settings.DB_NAME]


class _DatabaseProxy:
    """Lazy proxy so `db["collection"]` works without eager client creation."""
    def __getitem__(self, name: str):
        return get_db()[name]


db = _DatabaseProxy()


def col(name: str):
    """
    Get a named collection from the database.
    
    Args:
        name: Collection name
    
    Returns:
        AsyncIOMotorCollection
    
    Example:
        users = col("users")
        user = await users.find_one({"employee_id": "E001"})
    """
    return get_db()[name]


async def close_db():
    """Close the MongoDB client connection. Call on app shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
