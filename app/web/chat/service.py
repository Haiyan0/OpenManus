"""会话与消息业务逻辑。"""
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.web.chat.models import AGENT_TYPES, Chat, Message


async def create_chat(
    db: AsyncSession,
    user_id: int,
    agent_type: str,
    title: str | None = None,
) -> Chat:
    """创建新会话。agent_type 非法时抛 400。"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"agent_type 必须是 {sorted(AGENT_TYPES)} 之一",
        )
    chat = Chat(
        user_id=user_id,
        agent_type=agent_type,
        title=title or "新会话",
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


async def get_user_chats(db: AsyncSession, user_id: int) -> list[Chat]:
    """按更新时间倒序返回用户的所有活跃会话。"""
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user_id, Chat.status == "active")
        .order_by(desc(Chat.updated_at))
    )
    return list(result.scalars().all())


async def get_chat_or_404(
    db: AsyncSession, chat_id: int, user_id: int
) -> Chat:
    """获取指定会话，会话不存在或不属于该用户时抛 404。"""
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    chat = result.scalar_one_or_none()
    if chat is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return chat


async def delete_chat(db: AsyncSession, chat: Chat) -> None:
    """删除会话（级联删除 messages）。"""
    await db.delete(chat)
    await db.commit()


async def list_messages(
    db: AsyncSession,
    chat_id: int,
    before_id: int | None = None,
    limit: int = 50,
) -> list[Message]:
    """按 id 倒序分页返回消息，用于历史加载。"""
    query = select(Message).where(Message.chat_id == chat_id)
    if before_id is not None:
        query = query.where(Message.id < before_id)
    query = query.order_by(desc(Message.id)).limit(limit)

    result = await db.execute(query)
    rows = list(result.scalars().all())
    return list(reversed(rows))  # 返回给前端时按时间正序


async def save_message(
    db: AsyncSession,
    chat_id: int,
    role: str,
    content: str | None,
    event_type: str | None = None,
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    extra_data: dict[str, Any] | None = None,
) -> Message:
    """持久化一条消息并返回。"""
    msg = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        event_type=event_type,
        tool_name=tool_name,
        tool_args=tool_args,
        extra_data=extra_data,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg
