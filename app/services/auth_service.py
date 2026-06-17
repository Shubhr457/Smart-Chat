from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import hash_password, hash_refresh_token, verify_password
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
    """Hash password, insert a new user document, and return it."""
    doc = {
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": hash_password(user_data.password),
        "is_active": True,
        "refresh_tokens": [],
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


async def store_refresh_token(db: AsyncIOMotorDatabase, email: str, token: str) -> None:
    """Hash *token* and append it to the user's refresh_tokens array (multi-device)."""
    token_hash = hash_refresh_token(token)
    await db["users"].update_one(
        {"email": email},
        {"$push": {"refresh_tokens": token_hash}},
    )


async def rotate_refresh_token(
    db: AsyncIOMotorDatabase, email: str, old_token: str, new_token: str
) -> bool:
    """
    Atomically swap old_token hash for new_token hash in the user's array.
    Returns True on success, False if old_token was not found (replay attack / already rotated).

    Uses an aggregation-pipeline update (MongoDB 4.2+) to filter out the old hash
    and append the new one in a single stage, avoiding the MongoDB restriction that
    prohibits $pull and $push on the same field path in one update document.
    """
    old_hash = hash_refresh_token(old_token)
    new_hash = hash_refresh_token(new_token)
    result = await db["users"].update_one(
        {"email": email, "refresh_tokens": old_hash},
        [
            {
                "$set": {
                    "refresh_tokens": {
                        "$concatArrays": [
                            {
                                "$filter": {
                                    "input": "$refresh_tokens",
                                    "cond": {"$ne": ["$$this", old_hash]},
                                }
                            },
                            [new_hash],
                        ]
                    }
                }
            }
        ],
    )
    return result.matched_count > 0


async def revoke_refresh_token(
    db: AsyncIOMotorDatabase, email: str, token: str
) -> None:
    """Remove a single refresh token hash from the user's array (single-device logout)."""
    token_hash = hash_refresh_token(token)
    await db["users"].update_one(
        {"email": email},
        {"$pull": {"refresh_tokens": token_hash}},
    )


async def revoke_all_refresh_tokens(db: AsyncIOMotorDatabase, email: str) -> None:
    """Clear all refresh tokens for a user (logout from all devices)."""
    await db["users"].update_one(
        {"email": email},
        {"$set": {"refresh_tokens": []}},
    )
