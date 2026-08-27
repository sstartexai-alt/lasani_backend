from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.security import (
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    AppException,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    limiter,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import Message
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if settings.AUTH_ENABLED:
        if user is None or not verify_password(payload.password, user.password_hash):
            raise AppException(401, "Invalid username or password", "INVALID_CREDENTIALS")
    else:
        # Auth is off: issue tokens for the named user, or fall back to seeded admin.
        if user is None:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if user is None:
            raise AppException(401, "Admin user is unavailable", "AUTH_DISABLED_USER_MISSING")
    if not user.is_active:
        raise AppException(401, "User account is deactivated", "USER_INACTIVE")

    return TokenResponse(
        access_token=create_access_token(user.user_id, user.role),
        refresh_token=create_refresh_token(user.user_id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if data.get("type") != REFRESH_TOKEN:
        raise AppException(401, "Invalid token type", "INVALID_TOKEN_TYPE")
    user = await db.get(User, int(data["sub"]))
    if user is None or not user.is_active:
        raise AppException(401, "User not found or deactivated", "USER_INACTIVE")
    return TokenResponse(
        access_token=create_access_token(user.user_id, user.role),
        refresh_token=create_refresh_token(user.user_id),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", response_model=Message)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise AppException(400, "Current password is incorrect", "INVALID_CREDENTIALS")
    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return Message(detail="Password updated successfully")
