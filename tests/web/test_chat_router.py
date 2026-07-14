"""会话 CRUD REST 端到端测试。"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.web.server import app


async def _register_and_get_token(ac: AsyncClient) -> tuple[str, int]:
    username = f"chatapi_{uuid.uuid4().hex[:8]}"
    resp = await ac.post(
        "/api/auth/register",
        json={"username": username, "password": "pw123456"},
    )
    body = resp.json()
    return body["access_token"], body["id"]


@pytest.mark.asyncio
async def test_create_and_list_chat():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _register_and_get_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 创建
        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "data_analysis", "title": "分析报告"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        chat = resp.json()
        assert chat["agent_type"] == "data_analysis"
        assert chat["title"] == "分析报告"
        chat_id = chat["id"]

        # 列表
        resp = await ac.get("/api/chats", headers=headers)
        assert resp.status_code == 200
        chats = resp.json()
        assert any(c["id"] == chat_id for c in chats)


@pytest.mark.asyncio
async def test_create_chat_invalid_agent_type():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _register_and_get_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "not_a_real_agent"},
            headers=headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_chat():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _register_and_get_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chats", json={"agent_type": "general"}, headers=headers
        )
        chat_id = resp.json()["id"]

        resp = await ac.delete(f"/api/chats/{chat_id}", headers=headers)
        assert resp.status_code == 200

        resp = await ac.get(f"/api/chats/{chat_id}", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_access_others_chat():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token_a, _ = await _register_and_get_token(ac)
        token_b, _ = await _register_and_get_token(ac)

        # A 创建
        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "general"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        chat_id = resp.json()["id"]

        # B 访问，应 404（不暴露资源存在与否）
        resp = await ac.get(
            f"/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/chats")
        assert resp.status_code == 401
