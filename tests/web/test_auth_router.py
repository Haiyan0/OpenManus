"""注册与登录 API 端到端测试。"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.web.server import app


@pytest.fixture
def unique_username() -> str:
    """每次测试用唯一用户名，避免污染数据库。"""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_register_returns_token(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["username"] == unique_username
        assert "access_token" in data
        assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_fails(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        resp = await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_flow(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        resp = await ac.post(
            "/api/auth/login",
            json={"username": unique_username, "password": "pw123456"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        resp = await ac.post(
            "/api/auth/login",
            json={"username": unique_username, "password": "wrong_pw"},
        )
        assert resp.status_code == 401
