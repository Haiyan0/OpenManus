"""FastAPI 服务器 — OpenManus Web 聊天后端。

端点:
    GET  /        → 返回聊天前端页面
    GET  /static/ → 静态资源目录（挂载到 app/web/static/）
    WS   /ws      → WebSocket 端点，接收 prompt，流式推送 agent 事件
"""

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.web.agent_runner import ObservableManus


# ── FastAPI 应用 ──────────────────────────────────────────────

app = FastAPI(title="OpenManus Chat", version="0.1.0")

# 静态资源目录
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 路由 ──────────────────────────────────────────────────────

@app.get("/")
async def root():
    """返回聊天前端页面。"""
    index_path = STATIC_DIR / "index.html"
    return FileResponse(str(index_path))


# ── WebSocket 端点 ────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    """WebSocket 聊天端点。

    1. 接收客户端发来的 prompt 文本
    2. 创建 ObservableManus agent
    3. 并行：agent 执行 + 从 event_queue 消费事件推送客户端
    4. agent 完成后关闭连接
    """
    await ws.accept()

    try:
        # 接收 prompt
        prompt = await ws.receive_text()
        if not prompt or not prompt.strip():
            await ws.send_json(
                {"type": "error", "message": "Empty prompt"}
            )
            await ws.close()
            return
    except WebSocketDisconnect:
        return

    # 创建 agent 和事件队列
    agent = await ObservableManus.create()
    queue: asyncio.Queue = asyncio.Queue()
    agent.event_queue = queue

    # 启动 agent 执行任务
    agent_task = asyncio.create_task(agent.run(prompt))

    # 消费事件队列并推送给前端
    try:
        while not agent_task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                # 队列暂时为空，继续循环（除非 agent 已结束且队列空了）
                continue

        # 确保 agent 任务完成（可能已经 done）
        await agent_task
    except WebSocketDisconnect:
        # 客户端断开连接，取消 agent
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
    except Exception as exc:
        # 未预期的错误
        try:
            await ws.send_json(
                {"type": "error", "message": f"Server error: {str(exc)}"}
            )
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
