"""数据库连接冒烟测试。

要求 config.toml [web] 段填了真实凭据且 MySQL 可达，
且目标数据库已创建（CREATE DATABASE openmanus_web CHARACTER SET utf8mb4）。
"""
import asyncio

import pytest
from sqlalchemy import text

from app.web import database as db
from app.web.database import AsyncSessionLocal, engine


@pytest.mark.asyncio
async def test_engine_can_connect():
    """引擎应能建立到 MySQL 的实际连接。"""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_session_lifecycle():
    """AsyncSessionLocal 应能创建 session 并成功查询。"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 2 + 3"))
        assert result.scalar() == 5


# ── 心跳保活（不依赖真实 MySQL，用 fake engine） ─────────────


class _FakeConnection:
    """模拟 AsyncConnection：记录 execute 调用次数。"""

    def __init__(self, engine: "_FakeEngine"):
        self._engine = engine

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self._engine.pings += 1


class _FakeEngine:
    """模拟 AsyncEngine：connect() 返回假连接；dispose() 供 autouse fixture 调用。"""

    def __init__(self):
        self.pings = 0

    def connect(self):
        return _FakeConnection(self)

    async def dispose(self):
        pass


@pytest.mark.asyncio
async def test_heartbeat_pings_periodically_until_stopped(monkeypatch):
    """心跳应按间隔执行 SELECT 1，收到停止信号后退出。"""
    fake = _FakeEngine()
    monkeypatch.setattr(db, "engine", fake)

    stop = asyncio.Event()
    task = asyncio.create_task(db.db_heartbeat(interval=0.05, stop_event=stop))
    await asyncio.sleep(0.15)  # 约 3 轮
    stop.set()
    await task

    assert fake.pings >= 1


@pytest.mark.asyncio
async def test_heartbeat_survives_db_errors(monkeypatch):
    """数据库不可用时心跳只记日志不崩溃，且能正常停止（自愈重试）。"""

    class _BrokenEngine(_FakeEngine):
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(db, "engine", _BrokenEngine())

    stop = asyncio.Event()
    task = asyncio.create_task(db.db_heartbeat(interval=0.05, stop_event=stop))
    await asyncio.sleep(0.15)
    stop.set()
    await task  # 不抛异常即通过
