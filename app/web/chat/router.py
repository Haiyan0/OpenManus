"""会话 CRUD 路由: /api/chats/*"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.web.auth.models import User
from app.web.chat.schemas import ChatCreate, ChatDetail, ChatOut, MessageOut
from app.web.chat.service import (
    create_chat,
    delete_chat,
    get_chat_or_404,
    get_user_chats,
    list_messages,
)
from app.web.database import get_db
from app.web.dependencies import get_current_user
from app.web.sandbox.service import (
    create_session_sandbox,
    destroy_session_sandbox,
    get_sandbox_for_chat,
)


router = APIRouter(prefix="/api/chats", tags=["chat"])


@router.get("", response_model=list[ChatOut])
async def api_list_chats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatOut]:
    chats = await get_user_chats(db, user.id)
    return [ChatOut.model_validate(c) for c in chats]


@router.post("", response_model=ChatOut)
async def api_create_chat(
    payload: ChatCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await create_chat(db, user.id, payload.agent_type, payload.title)

    # 后台创建 Sandbox
    try:
        network = payload.agent_type == "general"
        sandbox = await create_session_sandbox(user.id, chat.id, network_enabled=network)
        chat.sandbox_id = sandbox.container.id if sandbox.container else None
        await db.commit()
        await db.refresh(chat)  # commit 后 refresh，避免 MissingGreenlet
    except Exception:
        # Sandbox 创建失败不影响会话创建，会话仍可使用
        pass

    return ChatOut.model_validate(chat)


@router.get("/{chat_id}", response_model=ChatDetail)
async def api_get_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatDetail:
    chat = await get_chat_or_404(db, chat_id, user.id)
    msgs = await list_messages(db, chat_id, limit=50)
    detail = ChatDetail.model_validate(chat)
    detail.messages = [MessageOut.model_validate(m) for m in msgs]
    return detail


@router.delete("/{chat_id}")
async def api_delete_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chat = await get_chat_or_404(db, chat_id, user.id)
    # 清理 Sandbox
    sandbox = get_sandbox_for_chat(user.id, chat_id)
    await destroy_session_sandbox(sandbox, user.id, chat_id)
    await delete_chat(db, chat)
    return {"ok": True}


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def api_list_messages(
    chat_id: int,
    before_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    await get_chat_or_404(db, chat_id, user.id)   # 权限校验
    msgs = await list_messages(db, chat_id, before_id=before_id, limit=limit)
    return [MessageOut.model_validate(m) for m in msgs]
