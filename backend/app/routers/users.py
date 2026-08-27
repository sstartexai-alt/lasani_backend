from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_db, require_role
from app.core.security import AppException, hash_password
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])
admin_only = require_role("admin")


@router.get("", response_model=Page[UserResponse])
async def list_users(
    pg: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    rows = (
        await db.execute(select(User).order_by(User.user_id).limit(pg.limit).offset(pg.offset))
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    payload: UserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    exists = (
        await db.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if exists:
        raise AppException(400, "Username already exists", "DUPLICATE_USERNAME")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    user = await db.get(User, user_id)
    if user is None:
        raise AppException(404, "User not found", "USER_NOT_FOUND")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    user = await db.get(User, user_id)
    if user is None:
        raise AppException(404, "User not found", "USER_NOT_FOUND")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    if "is_active" in data:
        user.is_active = 1 if data.pop("is_active") else 0
    for key, value in data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=Message)
async def deactivate_user(
    user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    user = await db.get(User, user_id)
    if user is None:
        raise AppException(404, "User not found", "USER_NOT_FOUND")
    user.is_active = 0
    await db.commit()
    return Message(detail="User deactivated")
