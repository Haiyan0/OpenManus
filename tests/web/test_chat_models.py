"""Chat / Message ORM 模型 CRUD 冒烟测试。"""
import uuid

import pytest
from sqlalchemy import select

from app.web.auth.models import User
from app.web.auth.service import hash_password
from app.web.chat.models import Chat, Message
from app.web.database import AsyncSessionLocal


@pytest.fixture
async def user():
    """在数据库中创建一个测试用户并返回。"""
    async with AsyncSessionLocal() as db:
        u = User(
            username=f"chatuser_{uuid.uuid4().hex[:8]}",
            password_hash=hash_password("pw"),
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        yield u


@pytest.mark.asyncio
async def test_chat_crud(user):
    async with AsyncSessionLocal() as db:
        chat = Chat(user_id=user.id, title="测试会话", agent_type="general")
        db.add(chat)
        await db.commit()
        await db.refresh(chat)
        assert chat.id > 0
        assert chat.status == "active"


@pytest.mark.asyncio
async def test_message_belongs_to_chat(user):
    async with AsyncSessionLocal() as db:
        chat = Chat(user_id=user.id, agent_type="data_analysis")
        db.add(chat)
        await db.commit()
        await db.refresh(chat)

        msg = Message(
            chat_id=chat.id,
            role="user",
            content="帮我分析",
            event_type=None,
        )
        db.add(msg)
        await db.commit()

        result = await db.execute(
            select(Message).where(Message.chat_id == chat.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].content == "帮我分析"
