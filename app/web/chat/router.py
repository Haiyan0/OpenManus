"""会话 CRUD 路由: /api/chats/*"""
import os
import shutil
from pathlib import Path
from typing import Any

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.web.auth.models import User
from app.web.auth.service import decode_access_token
from app.web.chat.schemas import ChatCreate, ChatDetail, ChatOut, MessageOut, WorkspaceFile
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
    cleanup_chat_workspace,
    create_session_sandbox,
    destroy_session_sandbox,
    get_sandbox_for_chat,
)


async def _resolve_user_from_token(token: str, db: AsyncSession) -> User:
    """从 query token 解析用户（供 workspace 文件端点使用）。"""
    if not token:
        raise HTTPException(status_code=401, detail="请提供 token 参数")
    try:
        payload = decode_access_token(token)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效或过期的 token")
    result = await db.execute(select(User).where(User.id == payload["user_id"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


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
    # 清理 Sandbox 容器 + 追踪（不删文件，留给会话删除时统一清理）
    sandbox = get_sandbox_for_chat(user.id, chat_id)
    await destroy_session_sandbox(sandbox, user.id, chat_id)
    # 清理 workspace 文件（用户主动删除时才删）
    cleanup_chat_workspace(user.id, chat_id)
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


# ── Workspace 文件浏览与下载 ──────────────────────────

# 文件扩展名 → MIME 类型映射（常见生成产物）
_MIME_MAP: dict[str, str] = {
    ".csv": "text/csv",
    ".json": "application/json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".py": "text/x-python",
    ".html": "text/html",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
}


def _scan_workspace(root: Path, base: Path) -> list[WorkspaceFile]:
    """递归扫描 workspace 目录，跳过临时脚本和 __pycache__。"""
    files: list[WorkspaceFile] = []
    for entry in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if entry.name.startswith("_sandbox_script_") or entry.name == "__pycache__":
            continue
        rel = str(entry.relative_to(base)).replace("\\", "/")
        if entry.is_dir():
            files.append(WorkspaceFile(name=entry.name, path=rel, size=0, is_dir=True))
            files.extend(_scan_workspace(entry, base))
        else:
            size = entry.stat().st_size
            files.append(WorkspaceFile(name=entry.name, path=rel, size=size))
    return files


@router.get("/{chat_id}/workspace/files", response_model=list[WorkspaceFile])
async def api_list_workspace_files(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出会话 workspace 中的所有生成文件（含子目录）。

    使用标准 Bearer token 认证，与 API 其他端点保持一致。
    """
    await get_chat_or_404(db, chat_id, user.id)

    # workspace 目录: {sandbox_data_root}/users/{user_id}/workspace/{chat_id}/
    ws_root = config.web.sandbox_data_root / "users" / str(user.id) / "workspace" / str(chat_id)
    if not ws_root.exists():
        return []

    return _scan_workspace(ws_root, ws_root)


@router.get("/{chat_id}/workspace/download")
async def api_download_workspace_file(
    chat_id: int,
    path: str = Query(..., description="相对于 workspace 根目录的文件路径"),
    token: str = Query(..., description="JWT token（浏览器 a 标签下载时的认证方式）"),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """下载 workspace 中的指定文件。

    认证方式：?token=xxx query 参数（支持浏览器 <a> 标签直接点击下载）。

    安全限制：
        - 路径必须限定在用户 workspace 内（禁止 ../ 穿越）
        - 路径必须指向实际存在的文件
    """
    user = await _resolve_user_from_token(token, db)
    await get_chat_or_404(db, chat_id, user.id)

    ws_root = (
        config.web.sandbox_data_root
        / "users" / str(user.id) / "workspace" / str(chat_id)
    )

    # 安全：防路径穿越
    safe_path = Path(path).as_posix()
    if ".." in safe_path.split("/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="非法文件路径")

    file_path = ws_root / safe_path
    if not file_path.exists() or not file_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文件不存在")

    # MIME 类型推断
    suffix = file_path.suffix.lower()
    media_type = _MIME_MAP.get(suffix, "application/octet-stream")

    return FileResponse(
        str(file_path),
        filename=file_path.name,
        media_type=media_type,
    )


# ── 会话文件上传（上传到 workspace，Agent 立即可用）────────

@router.post("/{chat_id}/upload")
async def api_upload_to_workspace(
    chat_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文件到当前会话 workspace 目录。

    文件写入 Docker Sandbox 挂载的 workspace 目录，Agent 可立即读取。
    WebSocket 断开或会话删除时，整个 workspace 目录自动清理。
    """
    await get_chat_or_404(db, chat_id, user.id)

    ws_root = (
        config.web.sandbox_data_root
        / "users" / str(user.id) / "workspace" / str(chat_id)
    )
    ws_root.mkdir(parents=True, exist_ok=True)

    # 安全文件名：保留原始扩展名，去除非 ASCII 以外的不安全字符
    safe_name = file.filename or "uploaded_file"
    # 替换路径分隔符和空字符
    safe_name = safe_name.replace("/", "_").replace("\\", "_").replace("\0", "")

    dest_path = ws_root / safe_name
    # 同名文件直接覆盖（覆盖旧版）
    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    # 同时在 uploads 目录保留一份副本（供 /api/files 兼容）
    uploads_dir = config.web.sandbox_data_root / "users" / str(user.id) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    upload_path = uploads_dir / safe_name
    with open(upload_path, "wb") as f:
        f.write(content)

    return JSONResponse({
        "ok": True,
        "filename": safe_name,
        "size": len(content),
        "workspace_path": f"/workspace/{safe_name}",
    })
