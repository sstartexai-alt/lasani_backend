import pytest

from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, auth

pytestmark = pytest.mark.asyncio


async def test_login_success(client, admin_token):
    assert admin_token


async def test_login_invalid_credentials(client):
    resp = await client.post("/auth/login", json={"username": ADMIN_USERNAME, "password": "wrong"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error_code"] == "INVALID_CREDENTIALS"


async def test_me_requires_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_refresh_rotates_token(client):
    login = await client.post(
        "/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    refresh = login.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_sales_entry_forbidden_on_admin_route(client, sales_token):
    resp = await client.get("/suppliers", headers=auth(sales_token))
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN"
