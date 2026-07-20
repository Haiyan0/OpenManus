"""Sandbox 生命周期管理：用户目录 + Docker 容器。

每个用户 + 会话拥有独立的：
- 主机目录: <sandbox_data_root>/users/<user_id>/workspace/<chat_id>/
- 容器内路径: /workspace
- 容器名: sandbox_u<user_id>_c<chat_id>_<8位hex>
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Dict

from app.config import config
from app.logger import logger
from app.sandbox.core.sandbox import DockerSandbox

if TYPE_CHECKING:
    from app.config import SandboxSettings

# 简单的内存字典追踪活跃 sandbox: (user_id, chat_id) -> DockerSandbox
_active_sandboxes: dict[tuple[int, int], DockerSandbox] = {}


class WebDockerSandbox(DockerSandbox):
    """Web 层专用 Sandbox，避免 _prepare_volume_bindings 为 work_dir 生成临时目录挂载。

    父类 DockerSandbox._prepare_volume_bindings() 无条件把 work_dir 挂载到一个
    随机临时目录。Web 层通过 volume_bindings 显式指定了用户隔离目录到 work_dir
    的映射，这会造成两个不同的 host 路径都挂载到同一个容器路径，Docker 直接拒绝：
        "Duplicate mount point: /workspace"

    本子类在自定义 volume_bindings 已覆盖 work_dir 时，跳过父类的临时目录挂载。
    """

    def _prepare_volume_bindings(self) -> Dict[str, Dict[str, str]]:
        """与父类逻辑一致，但自定义绑定已覆盖 work_dir 时跳过自动临时目录。"""
        bindings: Dict[str, Dict[str, str]] = {}

        # 检查自定义 volume_bindings 是否已覆盖了 work_dir
        work_dir = self.config.work_dir
        already_bound = any(
            container_path == work_dir
            for container_path in self.volume_bindings.values()
        )

        if not already_bound:
            # 没有显式绑定 → 沿用父类行为：创建临时目录挂载到 work_dir
            host_work = self._ensure_host_dir(work_dir)
            bindings[host_work] = {"bind": work_dir, "mode": "rw"}

        # 添加自定义 volume bindings
        for host_path, container_path in self.volume_bindings.items():
            bindings[host_path] = {"bind": container_path, "mode": "rw"}

        return bindings


def _patch_terminal_for_windows() -> None:
    """修复 Windows Docker Desktop 上 DockerSession.create 无法获取 socket 的问题。

    在 Linux 上，docker SDK exec_start(socket=True) 返回 SocketIO 包装对象，
    真正的 socket 通过 ._sock 访问。但在 Windows 上，返回的是 NpipeSocket，
    它本身就是 socket（有 recv/sendall/setblocking），没有 _sock 属性。

    此函数在模块加载时执行一次，对 DockerSession.create 做 monkey-patch，
    使其同时兼容两种平台。
    """
    from app.sandbox.core.terminal import DockerSession as _DockerSession

    _original_create = _DockerSession.create

    async def _patched_create(self, working_dir, env_vars):
        startup_command = [
            "bash",
            "-c",
            f"cd {working_dir} && "
            "PROMPT_COMMAND='' "
            "PS1='$ ' "
            "exec bash --norc --noprofile",
        ]
        exec_data = self.api.exec_create(
            self.container_id,
            startup_command,
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
            privileged=True,
            user="root",
            environment={**env_vars, "TERM": "dumb", "PS1": "$ ", "PROMPT_COMMAND": ""},
        )
        self.exec_id = exec_data["Id"]

        socket_data = self.api.exec_start(
            self.exec_id, socket=True, tty=True, stream=True, demux=True
        )

        # 兼容 Linux (SocketIO._sock) 和 Windows (NpipeSocket 本身就是 socket)
        if hasattr(socket_data, "_sock") and socket_data._sock is not None:
            self.socket = socket_data._sock
        elif hasattr(socket_data, "recv") and hasattr(socket_data, "sendall"):
            # Windows: NpipeSocket 就是 socket，直接使用
            self.socket = socket_data
        else:
            raise RuntimeError("Failed to get socket connection")

        self.socket.setblocking(False)
        await self._read_until_prompt()

    _DockerSession.create = _patched_create  # type: ignore[method-assign]


# 模块加载时执行一次 Windows 终端兼容性修复
_patch_terminal_for_windows()


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

    # 构建 bind mount：用户 workspace + company_data_resource（只读）
    volume_bindings = {str(host_ws): container_ws}

    # 如果宿主机存在 company_data_resource 目录，挂载到容器内 workspace 下
    # Agent 的 python_execute 在容器内运行，需要能读取这些 CSV 数据文件
    from app.config import PROJECT_ROOT
    cdr_path = PROJECT_ROOT / "company_data_resource"
    if cdr_path.exists() and cdr_path.is_dir():
        cdr_container_path = f"{container_ws}/company_data_resource"
        volume_bindings[str(cdr_path)] = cdr_container_path
        logger.info(f"挂载 company_data_resource: {cdr_path} → {cdr_container_path}")

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

    # 创建并启动容器（使用 WebDockerSandbox 避免重复挂载 /workspace）
    sandbox = WebDockerSandbox(
        config=sandbox_config,
        volume_bindings=volume_bindings,
    )
    await sandbox.create()

    _active_sandboxes[key] = sandbox
    return sandbox


async def destroy_session_sandbox(
    sandbox: DockerSandbox | None,
    user_id: int,
    chat_id: int,
) -> None:
    """销毁 sandbox 容器并清理追踪。不删除 workspace 文件（用户可能还想下载）。"""
    key = (user_id, chat_id)
    if sandbox is not None:
        try:
            await sandbox.cleanup()
        except Exception:
            pass
    _active_sandboxes.pop(key, None)
    # 注：workspace 文件清理移至 cleanup_chat_workspace，
    # 仅当用户主动删除会话时调用，WebSocket 断开时保留文件。


def cleanup_chat_workspace(user_id: int, chat_id: int) -> None:
    """清理指定会话的 workspace 目录（用户上传 + Agent 生成产物）。

    仅在用户主动删除会话时调用，不在 WebSocket 断连时执行。
    这样用户可以在 Agent 结束后下载生成文件。
    """
    ws_dir = (
        config.web.sandbox_data_root
        / "users" / str(user_id) / "workspace" / str(chat_id)
    )
    if ws_dir.exists():
        try:
            shutil.rmtree(str(ws_dir), ignore_errors=True)
            logger.info(f"Workspace 已清理: {ws_dir}")
        except Exception:
            pass


def get_sandbox_for_chat(user_id: int, chat_id: int) -> DockerSandbox | None:
    """获取指定会话的活跃 sandbox（不创建）。"""
    return _active_sandboxes.get((user_id, chat_id))


async def _kill_orphan_sandboxes() -> int:
    """通过 Docker API 列出并强制清理所有 sandbox_* 前缀的孤儿容器。

    Web 层和通用 sandbox 都使用 sandbox_{hex} 命名格式。
    服务端重启时，残留容器不受内存 _active_sandboxes 追踪，必须从 Docker 层面扫。

    Returns:
        杀死的容器数量。
    """
    import docker as docker_lib

    try:
        client = docker_lib.from_env()
        containers = await asyncio.to_thread(
            client.containers.list,
            all=False,  # 只列运行中的
            filters={"name": "sandbox_"},
        )
    except Exception as exc:
        logger.warning(f"无法连接 Docker daemon，跳过孤儿清理: {exc}")
        return 0

    killed = 0
    for c in containers:
        name = c.name
        try:
            await asyncio.to_thread(c.kill)
            await asyncio.to_thread(c.remove)
            killed += 1
            logger.info(f"清理孤儿容器: {name}")
        except Exception as exc:
            logger.warning(f"清理孤儿失败 {name}: {exc}")
            # 最后手段：直接通过低层 API 删
            try:
                await asyncio.to_thread(
                    client.api.remove_container, c.id, force=True
                )
                killed += 1
                logger.info(f"强制清理孤儿容器: {name}")
            except Exception:
                pass

    if killed:
        logger.info(f"启动时清理了 {killed} 个孤儿 Sandbox 容器")
    return killed


async def startup_sandbox_cleanup() -> None:
    """启动时清理上一个进程残留的 Sandbox 容器。

    注册为 FastAPI startup 事件处理器。
    kill → remove 双保险确保容器不残留。
    """
    await _kill_orphan_sandboxes()


async def shutdown_all_sandboxes() -> None:
    """强制清理当前进程追踪的所有活跃 Sandbox + 兜底扫描所有 sandbox_* 容器。

    注册为 FastAPI shutdown 事件处理器。
    第一步：清理内存字典中的容器（正常流程）；
    第二步：兜底扫描，杀掉可能的漏网之鱼（如 ws_handler finally 未覆盖到的）。
    """
    # 第一步：清理已追踪的
    remaining = dict(_active_sandboxes)
    _active_sandboxes.clear()
    for (user_id, chat_id), sandbox in remaining.items():
        try:
            await sandbox.cleanup()
            logger.info(f"Shutdown 清理: user={user_id}, chat={chat_id}")
        except Exception as exc:
            logger.warning(f"Shutdown 清理失败 user={user_id} chat={chat_id}: {exc}")

    # 第二步：兜底——Docker 级全部扫杀
    killed = await _kill_orphan_sandboxes()
    if killed:
        logger.info(f"Shutdown 兜底清理完成: {killed} 个漏网容器")
