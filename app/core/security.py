import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def hash_refresh_token(token: str) -> str:
    """Return a SHA-256 hex digest of *token* for safe DB storage."""
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    payload.update({"exp": expire})
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_access_token(data: Dict[str, Any]) -> str:
    """Create a short-lived JWT access token."""
    return _create_token(
        data,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a long-lived JWT refresh token with a unique jti to prevent collisions."""
    data_with_jti = {**data, "jti": secrets.token_hex(16)}
    return _create_token(
        data_with_jti,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT.  Raises HTTP 401 on any failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        raise _CREDENTIALS_EXCEPTION
