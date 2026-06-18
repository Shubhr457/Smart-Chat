import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.database import _create_indexes, db_instance
from app.main import app

TEST_DB_NAME = "smartchat_test"


@pytest_asyncio.fixture(scope="session")
async def test_client():
    # Point db_instance at the test database before the app handles any request
    db_instance.client = AsyncIOMotorClient("mongodb://localhost:27017")
    db_instance.db = db_instance.client[TEST_DB_NAME]

    # Create all indexes via the shared helper
    await _create_indexes()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # Teardown: drop test DB and close connection
    await db_instance.client.drop_database(TEST_DB_NAME)
    db_instance.client.close()
