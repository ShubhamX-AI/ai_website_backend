from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from src.core.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URL)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.MONGODB_DB_NAME]


async def init_db() -> None:
    db = get_database()
    await db["users"].create_index("email", unique=True)


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
