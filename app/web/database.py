"""SQLAlchemy 2.0 异步引擎、Session 工厂、FastAPI 依赖注入。"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import config


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""


engine = create_async_engine(
    config.web.mysql_url,
    echo=False,
    pool_pre_ping=True,   # 自动检测断开的连接
    pool_recycle=3600,    # 每小时回收一次连接（避免云端超时）
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 用的异步 session 生成器。

    使用方式:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
