from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.database import get_database
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.schemas.token import Token
from app.schemas.user import UserLogin, UserRegister, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Dependency: get current authenticated user
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    db=Depends(get_database),
) -> dict:
    """Decode the Bearer token and return the corresponding user document."""
    payload = decode_token(credentials.credentials)  # raises 401 on failure

    email: Optional[str] = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await auth_service.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(user_data: UserRegister, db=Depends(get_database)):
    # Uniqueness checks
    if await auth_service.get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    if await auth_service.get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    created = await auth_service.create_user(db, user_data)
    return _doc_to_response(created)


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive tokens",
)
async def login(credentials: UserLogin, db=Depends(get_database)):
    user = await auth_service.authenticate_user(
        db, credentials.email, credentials.password
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = {"sub": user["email"]}
    return Token(
        access_token=create_access_token(token_payload),
        refresh_token=create_refresh_token(token_payload),
    )


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post(
    "/refresh",
    response_model=Token,
    summary="Exchange a refresh token for a new token pair",
)
async def refresh(body: RefreshRequest, db=Depends(get_database)):
    payload = decode_token(body.refresh_token)  # raises 401 on failure

    email: Optional[str] = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await auth_service.get_user_by_email(db, email)
    if user is None or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = {"sub": email}
    return Token(
        access_token=create_access_token(token_payload),
        refresh_token=create_refresh_token(token_payload),
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _doc_to_response(doc: dict) -> UserResponse:
    """Convert a raw MongoDB doc to a UserResponse, mapping _id -> id."""
    return UserResponse(
        id=str(doc.get("_id", "")),
        username=doc["username"],
        email=doc["email"],
        is_active=doc.get("is_active", True),
        created_at=doc["created_at"],
    )
