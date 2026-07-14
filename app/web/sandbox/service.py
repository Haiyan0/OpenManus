"""Sandbox 生命周期管理：用户目录 + Docker 容器。

每个用户 + 会话拥有独立的：
- 主机目录: <sandbox_data_root>/users/<user_id>/workspace/<chat_id>/
- 容器内路径: /workspace
- 容器名: sandbox_u<user_id>_c<chat_id>_<8位hex>
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import config
from app.sandbox.core.sandbox import DockerSandbox

if TYPE_CHECKING:
    from app.config import SandboxSettings

# 简单的内存字典追踪活跃 sandbox: (user_id, chat_id) -> DockerSandbox
_active_sandboxes: dict[tuple[int, int], DockerSandbox] = {}


def ensure_user_directories(user_id: int, chat_id: int) -> tuple[Path, str]:
    """确保用户 + 会话的隔离目录存在。

    返回:
        (host_workspace, "/workspace")
    """
    host_ws = (
        config.web.sandbox_data_root
        / "users"
        / str(user_id)
        / "workspace"
        / str(chat_id)
    )
    host_ws.mkdir(parents=True, exist_ok=True)
    uploads = config.web.sandbox_data_root / "users" / str(user_id) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return host_ws, "/workspace"


async def create_session_sandbox(
    user_id: int,
    chat_id: int,
    network_enabled: bool = False,
) -> DockerSandbox:
    """为用户创建一个新的会话 Sandbox。

    Args:
        user_id: 用户 ID
        chat_id: 会话 ID
        network_enabled: 是否开启网络（general agent 需要）

    Returns:
        已就绪的 DockerSandbox 实例

    若已有运行中的 sandbox (同一用户+会话)，先销毁旧的。
    """
    key = (user_id, chat_id)
    if key in _active_sandboxes:
        try:
            await _active_sandboxes[key].cleanup()
        except Exception:
            pass

    host_ws, container_ws = ensure_user_directories(user_id, chat_id)

    # 构建 sandbox 配置（注意：需要导入 SandboxSettings，在函数内延迟导入避免循环）
    from app.config import SandboxSettings as _SandboxSettings

    sandbox_config = _SandboxSettings(
        image=config.sandbox.image,
        work_dir=container_ws,
        memory_limit=config.sandbox.memory_limit,
        cpu_limit=config.sandbox.cpu_limit,
        timeout=config.sandbox.timeout,
        network_enabled=network_enabled,
    )

    # 创建并启动容器
    sandbox = DockerSandbox(
        config=sandbox_config,
        volume_bindings={str(host_ws): container_ws},
    )
    await sandbox.create()

    _active_sandboxes[key] = sandbox
    return sandbox


async def destroy_session_sandbox(
    sandbox: DockerSandbox | None,
    user_id: int,
    chat_id: int,
) -> None:
    """销毁 sandbox 容器并清理追踪。"""
    key = (user_id, chat_id)
    if sandbox is not None:
        try:
            await sandbox.cleanup()
        except Exception:
            pass
    _active_sandboxes.pop(key, None)


def get_sandbox_for_chat(user_id: int, chat_id: int) -> DockerSandbox | None:
    """获取指定会话的活跃 sandbox（不创建）。"""
    return _active_sandboxes.get((user_id, chat_id))
