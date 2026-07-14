"""Sandbox 目录创建与清理测试。

注意：这些测试需要 Docker Desktop 运行。
仅测试文件系统层面，不实际启动容器（除非 Docker 可用）。
"""
import shutil

from app.config import config
from app.web.sandbox.service import ensure_user_directories


def test_ensure_user_directories_creates_paths():
    """应创建正确的目录结构。"""
    host_dir, container_dir = ensure_user_directories(user_id=1, chat_id=42)

    assert host_dir.exists()
    assert str(container_dir) == "/workspace"
    # 验证目录路径符合预期（跨平台）
    assert host_dir.parts[-4:] == ("users", "1", "workspace", "42")

    # 清理
    shutil.rmtree(config.web.sandbox_data_root / "users" / "1", ignore_errors=True)
