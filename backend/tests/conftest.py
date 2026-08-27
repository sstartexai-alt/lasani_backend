import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.user import User

ADMIN_USERNAME = "testadmin"
ADMIN_PASSWORD = "testpass12345"
SALES_USERNAME = "testsales"
SALES_PASSWORD = "salespass12345"


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


async def _ensure_user(username: str, password: str, role: str) -> None:
    async with AsyncSessionLocal() as db:
        exists = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if exists is None:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    full_name=f"{role} test user",
                    role=role,
                )
            )
            await db.commit()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    await _ensure_user(ADMIN_USERNAME, ADMIN_PASSWORD, "admin")
    resp = await client.post("/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def sales_token(client: AsyncClient) -> str:
    await _ensure_user(SALES_USERNAME, SALES_PASSWORD, "sales_entry")
    resp = await client.post("/auth/login", json={"username": SALES_USERNAME, "password": SALES_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def unique() -> str:
    return uuid.uuid4().hex[:8]
