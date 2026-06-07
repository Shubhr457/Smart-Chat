from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import hash_password, verify_password
from app.schemas.user import UserRegister


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    """Return the raw MongoDB document for the user with *email*, or None."""
    return await db["users"].find_one({"email": email})


async def get_user_by_username(
    db: AsyncIOMotorDatabase, username: str
) -> Optional[dict]:
    """Return the raw MongoDB document for the user with *username*, or None."""
    return await db["users"].find_one({"username": username})


async def create_user(db: AsyncIOMotorDatabase, user_data: UserRegister) -> dict:
    """Hash password, insert a new user document, and return it (with str id)."""
    doc = {
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": hash_password(user_data.password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db["users"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


async def authenticate_user(
    db: AsyncIOMotorDatabase, email: str, password: str
) -> Optional[dict]:
    """Return the user doc if credentials are valid, else None."""
    user = await get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user
