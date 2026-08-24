"""FastAPI 服务器 — OpenManus 多用户 Web 后端。

端点:
    GET  /                  → 聊天前端页面（Vue 构建产物）
    /static/                → 前端静态资源（JS/CSS/图片）
    WS  /ws/{chat_id}       → WebSocket 聊天端点
    /api/auth/*             → 认证路由
    /api/chats/*            → 会话 CRUD 路由
    /api/files/*            → 文件管理路由（Task 13）
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app.config import PROJECT_ROOT, config
from app.logger import logger
from app.web.auth.router import router as auth_router
from app.web.chat.router import router as chat_router
from app.web.chat.ws_handler import handle_chat_ws
from app.web.database import db_heartbeat
from app.web.files.router import router as files_router


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """FastAPI lifespan — 启动/关闭钩子。"""
    # 启动：数据库保活心跳（防止空闲断连与 RDS Serverless 冷启动超时）
    heartbeat_stop = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        db_heartbeat(stop_event=heartbeat_stop), name="db-heartbeat"
    )
    # 启动：清理上一个进程残留的孤儿 Sandbox 容器
    from app.web.sandbox.service import startup_sandbox_cleanup, shutdown_all_sandboxes

    await startup_sandbox_cleanup()
    yield
    # 关闭：停止心跳
    heartbeat_stop.set()
    heartbeat_task.cancel()
    # 关闭：清理当前进程的 Sandbox + 兜底扫描
    logger.info("正在清理所有 Sandbox 容器...")
    await shutdown_all_sandboxes()
    logger.info("所有 Sandbox 容器已清理完毕")


app = FastAPI(title="OpenManus Web", version="0.2.0", lifespan=_lifespan)


@app.exception_handler(OperationalError)
async def _db_operational_error_handler(request, exc: OperationalError):
    """数据库不可用（连接超时/断连）→ 503 JSON，避免 500 traceback。"""
    logger.error(
        f"数据库不可用: {exc.__class__.__name__}: "
        f"{getattr(exc, 'orig', None) or exc}"
    )
    return JSONResponse(
        status_code=503, content={"detail": "数据库暂时不可用，请稍后重试"}
    )

# ── REST 路由 ────────────────────────────────

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(files_router)

# ── 前端静态文件 ─────────────────────────────
# 将相对路径（如 "web_ui/dist"）相对于 PROJECT_ROOT 解析为绝对路径
# 避免因 uvicorn 工作目录不同导致 404

static_dir = Path(config.web.static_dir)
if not static_dir.is_absolute():
    static_dir = Path(PROJECT_ROOT) / static_dir
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
