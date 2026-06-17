from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings


class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


db_instance = Database()


async def connect_to_mongo():
    db_instance.client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_instance.db = db_instance.client[settings.MONGODB_DB_NAME]
    await _create_indexes()
    print("Connected to MongoDB.")


async def _create_indexes():
    """Ensure collection indexes exist. Safe to call on every startup (idempotent)."""
    users = db_instance.db["users"]
    await users.create_index("email", unique=True)
    await users.create_index("username", unique=True)


async def close_mongo_connection():
    if db_instance.client:
        db_instance.client.close()
        print("Closed MongoDB connection.")


def get_database():
    return db_instance.db
