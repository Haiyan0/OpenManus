"""FastAPI 服务器 — OpenManus 多用户 Web 后端。

端点:
    GET  /                  → 聊天前端页面（Vue 构建产物）
    /static/                → 前端静态资源（JS/CSS/图片）
    WS  /ws/{chat_id}       → WebSocket 聊天端点
    /api/auth/*             → 认证路由
    /api/chats/*            → 会话 CRUD 路由
    /api/files/*            → 文件管理路由（Task 13）
"""
from pathlib import Path

from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import config
from app.web.auth.router import router as auth_router
from app.web.chat.router import router as chat_router
from app.web.chat.ws_handler import handle_chat_ws
from app.web.files.router import router as files_router


app = FastAPI(title="OpenManus Web", version="0.2.0")

# ── REST 路由 ────────────────────────────────

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(files_router)

# ── 前端静态文件 ─────────────────────────────

static_dir = Path(config.web.static_dir)
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """返回前端首页（Vue 构建产物 index.html）。"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    # 回退：简单 API 信息
    return {
        "message": "OpenManus Web API",
        "docs": "/docs",
        "note": "前端尚未构建，请运行: cd web_ui && npm run build",
    }


# ── WebSocket ────────────────────────────────

@app.websocket("/ws/{chat_id}")
async def websocket_chat(
    ws: WebSocket,
    chat_id: int,
    token: str = Query(...),
):
    """WebSocket 聊天端点。

    客户端连接: ws://host:8080/ws/{chat_id}?token={jwt}
    发送: {"type": "prompt", "content": "你的任务"}
    """
    await handle_chat_ws(ws, chat_id, token)
