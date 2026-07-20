"""WebSocket 聊天端点处理器。

每建立一个 WebSocket = 一个 Agent 实例 + 一个 Sandbox 容器。
消息流: 接收 prompt → Agent 执行 → 事件推流 → 消息持久化 → 完成。
"""
from __future__ import annotations

import asyncio

import jwt as pyjwt
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.logger import logger
from app.web.agent_runner import create_observable_agent
from app.web.auth.models import User
from app.web.auth.service import decode_access_token
from app.web.chat.models import Chat
from app.web.chat.service import get_chat_or_404, save_message
from app.web.database import AsyncSessionLocal
from app.web.sandbox.service import (
    create_session_sandbox,
    destroy_session_sandbox,
    ensure_user_directories,
)


async def handle_chat_ws(
    ws: WebSocket,
    chat_id: int,
    token: str,
) -> None:
    """处理单个 WebSocket 聊天连接。

    1. 校验 JWT → 查出 User
    2. 校验 chat 归属
    3. 创建 Sandbox + Agent
    4. 接收 prompt → agent.run() → 事件推流 + 持久化
    5. 清理
    """
    # ── 认证 ──────────────────────────────────────
    try:
        payload = decode_access_token(token)
    except pyjwt.PyJWTError:
        await ws.accept()
        await ws.send_json({"type": "error", "message": "认证失败，请重新登录"})
        await ws.close()
        return

    async with AsyncSessionLocal() as db:
        user_id = payload["user_id"]
        try:
            chat = await get_chat_or_404(db, chat_id, user_id)
        except Exception:
            await ws.accept()
            await ws.send_json({"type": "error", "message": "会话不存在"})
            await ws.close()
            return

        await ws.accept()

        event_queue: asyncio.Queue = asyncio.Queue()
        sandbox = None
        agent = None
        agent_task = None
        host_ws = ""   # 宿主机隔离 workspace 目录

        try:
            # ── 多轮对话循环 ──────────────────────
            # Agent 完成一轮后不立即销毁 Sandbox，
            # 而是等待下一个 prompt（或超时）以便追问。
            while True:
                # 接收 prompt
                data = await ws.receive_json()
                if data.get("type") != "prompt" or not data.get("content"):
                    await ws.send_json(
                        {"type": "error", "message": "请发送有效的 prompt"}
                    )
                    return

                prompt_text = data["content"]

                # 持久化用户消息
                await save_message(
                    db, chat_id, role="user", content=prompt_text
                )

                # ── Sandbox（首次或沙箱已被清理时创建）──
                network = chat.agent_type == "general"
                if sandbox is None:
                    sandbox = await create_session_sandbox(
                        user_id, chat_id, network_enabled=network
                    )
                    # 保存宿主机 workspace 路径（供 DataVisualization npx ts-node 写文件用）
                    host_ws = str(
                        config.web.sandbox_data_root
                        / "users" / str(user_id) / "workspace" / str(chat_id)
                    )
                    logger.info(
                        f"Sandbox 就绪: user={user_id}, chat={chat_id}, "
                        f"type={chat.agent_type}"
                    )

                # ── Agent（每次新对话重新创建）─────
                if agent is not None:
                    try:
                        await agent.cleanup()
                    except Exception:
                        pass
                agent = await create_observable_agent(
                    chat.agent_type, event_queue, sandbox=sandbox,
                    host_workspace=str(host_ws),
                )

                # 启动 Agent（后台执行）
                async def run_agent():
                    await agent.run(prompt_text)
                    await event_queue.put(None)  # 哨兵

                agent_task = asyncio.create_task(run_agent())

                # ── 事件推流 + 持久化循环 ──────────
                while True:
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=30)
                    except asyncio.TimeoutError:
                        try:
                            await ws.send_json({"type": "heartbeat"})
                        except Exception:
                            break
                        continue
                    if event is None:
                        break

                    # 持久化到 MySQL
                    try:
                        await save_message(
                            db,
                            chat_id=chat_id,
                            role=_event_role(event),
                            content=event.get("content"),
                            event_type=event["type"],
                            tool_name=event.get("tool"),
                            tool_args=_parse_args(event.get("args")),
                        )
                    except Exception as db_err:
                        logger.warning(f"消息持久化失败: {db_err}")

                    await ws.send_json(event)

                await agent_task

        except WebSocketDisconnect:
            logger.info(f"WS 断开: user={user_id}, chat={chat_id}")
            if agent_task and not agent_task.done():
                agent_task.cancel()
        except Exception as exc:
            logger.error(f"WS 错误: {exc}")
            try:
                await ws.send_json(
                    {"type": "error", "message": f"服务器错误: {str(exc)}"}
                )
            except Exception:
                pass
        finally:
            if agent:
                try:
                    await agent.cleanup()
                except Exception:
                    pass
            await destroy_session_sandbox(sandbox, user_id, chat_id)
            try:
                await ws.close()
            except Exception:
                pass


def _event_role(event: dict) -> str:
    """根据事件类型映射消息角色。"""
    if event["type"] in ("assistant", "thinking"):
        return "assistant"
    if event["type"] in ("tool_start", "tool_end"):
        return "tool"
    if event["type"] in ("done", "error"):
        return "system"
    return "assistant"


def _parse_args(raw_args) -> dict | None:
    """将工具参数从 JSON 字符串转为 dict（可能已是 dict）。"""
    if raw_args is None:
        return None
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            import json
            return json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw_args}
    return {"raw": str(raw_args)}
