from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_auth_service, get_current_user
from app.core.errors import ErrorResponse
from app.domains.auth.model import User
from app.domains.auth.schemas import (
    LoginRequest,
    PurgeAccountRequest,
    PurgeAccountResponse,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.domains.auth.service import AuthService

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
def register(
    payload: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    return service.register(payload)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    return service.login(payload)


@router.get("/auth/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead(id=user.id, email=user.email, created_at=user.created_at)


@router.post(
    "/account/purge",
    response_model=PurgeAccountResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def purge_account(
    payload: PurgeAccountRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> PurgeAccountResponse:
    return service.purge(user=user, payload=payload)
