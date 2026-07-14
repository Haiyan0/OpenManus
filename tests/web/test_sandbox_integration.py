"""Sandbox 与会话集成的端到端测试。

要求 Docker Desktop 正在运行。
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.web.sandbox.service import get_sandbox_for_chat
from app.web.server import app


@pytest.mark.asyncio
async def test_create_chat_creates_sandbox():
    """新建 general 会话应自动创建 Sandbox。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        username = f"sandbox_{uuid.uuid4().hex[:8]}"
        resp = await ac.post(
            "/api/auth/register",
            json={"username": username, "password": "pw123456"},
        )
        token = resp.json()["access_token"]
        user_id = resp.json()["id"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "general"},
            headers=headers,
        )
        assert resp.status_code == 200
        chat_id = resp.json()["id"]

        # 验证 Sandbox 已被创建
        sandbox = get_sandbox_for_chat(user_id, chat_id)
        assert sandbox is not None

        # 删除会话 → Sandbox 应被回收
        resp = await ac.delete(f"/api/chats/{chat_id}", headers=headers)
        assert resp.status_code == 200

        sandbox2 = get_sandbox_for_chat(user_id, chat_id)
        assert sandbox2 is None
