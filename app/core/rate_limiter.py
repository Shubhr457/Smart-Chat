from fastapi import Request
from jose import jwt, JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

def rate_limit_key_func(request: Request) -> str:
    """
    Resolve the rate limit key.
    If authenticated via Bearer token, return the subject (email).
    Otherwise, fallback to client IP.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload.get("sub", "")
        except JWTError:
            pass
    return get_remote_address(request)


def is_admin_request(request: Request) -> bool:
    """Helper to check if the caller has the admin role, allowing bypass."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload.get("role") == "admin"
        except JWTError:
            pass
    return False

# Initialize Limiter
limiter = Limiter(key_func=rate_limit_key_func)
