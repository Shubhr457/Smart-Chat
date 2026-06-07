from typing import Annotated

from fastapi import APIRouter, Depends

from app.routers.auth import _doc_to_response, get_current_user
from app.schemas.user import UserResponse

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the authenticated user's profile",
)
async def get_me(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UserResponse:
    return _doc_to_response(current_user)
