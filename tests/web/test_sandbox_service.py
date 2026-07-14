"""Sandbox 目录创建与清理测试。

注意：这些测试需要 Docker Desktop 运行。
仅测试文件系统层面，不实际启动容器（除非 Docker 可用）。
"""
import shutil
from unittest.mock import MagicMock, patch

import pytest

from app.config import config
from app.web.sandbox import service as sandbox_service
from app.web.sandbox.service import ensure_user_directories, _patch_terminal_for_windows


def test_ensure_user_directories_creates_paths():
    """应创建正确的目录结构。"""
    host_dir, container_dir = ensure_user_directories(user_id=1, chat_id=42)

    assert host_dir.exists()
    assert str(container_dir) == "/workspace"
    # 验证目录路径符合预期（跨平台）
    assert host_dir.parts[-4:] == ("users", "1", "workspace", "42")

    # 清理
    shutil.rmtree(config.web.sandbox_data_root / "users" / "1", ignore_errors=True)


@pytest.mark.asyncio
async def test_create_session_sandbox_uses_user_workspace_as_only_workspace_mount(monkeypatch):
    """创建 Web Sandbox 时只应把用户工作目录挂载到容器 /workspace 一次。"""
    captured = {}

    class FakeDockerSandbox:
        def __init__(self, config, volume_bindings):
            captured["config"] = config
            captured["volume_bindings"] = volume_bindings
            self.container = None

        async def create(self):
            return self

    monkeypatch.setattr(sandbox_service, "WebDockerSandbox", FakeDockerSandbox)

    sandbox = await sandbox_service.create_session_sandbox(
        user_id=2,
        chat_id=43,
        network_enabled=False,
    )

    host_dir = config.web.sandbox_data_root / "users" / "2" / "workspace" / "43"
    assert sandbox is not None
    assert captured["config"].work_dir == "/workspace"
    assert captured["volume_bindings"] == {str(host_dir): "/workspace"}
    shutil.rmtree(config.web.sandbox_data_root / "users" / "2", ignore_errors=True)
    sandbox_service._active_sandboxes.pop((2, 43), None)


def test_web_sandbox_bindings_no_duplicate_mount():
    """WebDockerSandbox._prepare_volume_bindings 不应为 /workspace 生成重复挂载。"""
    from app.config import SandboxSettings
    from app.web.sandbox.service import WebDockerSandbox

    host_dir, container_dir = ensure_user_directories(user_id=3, chat_id=44)
    sandbox_config = SandboxSettings(
        image=config.sandbox.image,
        work_dir=container_dir,
        memory_limit=config.sandbox.memory_limit,
        cpu_limit=config.sandbox.cpu_limit,
        timeout=config.sandbox.timeout,
        network_enabled=False,
    )
    sandbox = WebDockerSandbox(
        config=sandbox_config,
        volume_bindings={str(host_dir): container_dir},
    )

    bindings = sandbox._prepare_volume_bindings()
    # 按容器内挂载目标分组，每个目标只应出现一次
    by_target: dict[str, list[dict]] = {}
    for host, binding in bindings.items():
        by_target.setdefault(binding["bind"], []).append(binding)

    assert by_target[container_dir] == [{"bind": container_dir, "mode": "rw"}], (
        f"容器路径 {container_dir} 不应出现重复挂载，实际: {by_target[container_dir]}"
    )
    shutil.rmtree(config.web.sandbox_data_root / "users" / "3", ignore_errors=True)


