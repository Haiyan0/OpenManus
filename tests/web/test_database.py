"""数据库连接冒烟测试。

要求 config.toml [web] 段填了真实凭据且 MySQL 可达，
且目标数据库已创建（CREATE DATABASE openmanus_web CHARACTER SET utf8mb4）。
"""
import pytest
from sqlalchemy import text

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
