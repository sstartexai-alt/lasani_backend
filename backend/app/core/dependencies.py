from collections.abc import AsyncGenerator

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ACCESS_TOKEN, AppException, decode_token
from app.db.session import get_session
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    if not settings.AUTH_ENABLED:
        user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if user is None or not user.is_active:
            raise AppException(401, "Admin user is unavailable", "AUTH_DISABLED_USER_MISSING")
        return user
    if token is None:
        raise AppException(401, "Not authenticated", "NOT_AUTHENTICATED")
    payload = decode_token(token)
    if payload.get("type") != ACCESS_TOKEN:
        raise AppException(401, "Invalid token type", "INVALID_TOKEN_TYPE")
    user_id = payload.get("sub")
    if user_id is None:
        raise AppException(401, "Invalid token payload", "INVALID_TOKEN")
    user = await db.get(User, int(user_id))
    if user is None:
        raise AppException(401, "User not found", "USER_NOT_FOUND")
    if not user.is_active:
        raise AppException(401, "User account is deactivated", "USER_INACTIVE")
    return user


async def get_optional_or_system_user(
    token: str | None = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """Use the bearer user when present; otherwise the seeded admin for public sale entry."""
    if token:
        return await get_current_user(token, db)
    user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException(401, "Admin user is unavailable", "AUTH_DISABLED_USER_MISSING")
    return user


def require_role(*roles: str):
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise AppException(403, "You do not have permission to access this resource", "FORBIDDEN")
        return current_user

    return _checker


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-based)"),
        page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.limit = page_size
        self.offset = (page - 1) * page_size
