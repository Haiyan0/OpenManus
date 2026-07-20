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


# ── 引擎配置 ────────────────────────────────────────────────
# pool_recycle=1800 远小于 MySQL wait_timeout（8h），确保连接在服务端超时前回收。
# pool_reset_on_return="rollback" 归还时回滚残留事务，配合 autoflush=False 避免
# session 跨请求状态污染。
# connect_args 设置读写超时 + 自动重连，应对云端 MySQL 间歇性断开。

engine = create_async_engine(
    config.web.mysql_url,
    echo=False,
    pool_size=10,                    # 常驻连接数上限
    max_overflow=20,                 # 超出 pool_size 时允许的临时连接数
    pool_pre_ping=True,              # 使用前发 ping 探测连接存活
    pool_recycle=1800,               # 每 30 分钟回收连接（远小于 MySQL 8h wait_timeout）
    pool_reset_on_return="rollback", # 归还连接时回滚事务，清理状态
    pool_timeout=30,                 # 等待可用连接的超时（秒）
    connect_args={
        "connect_timeout": 10,       # TCP 连接建立超时（aiomysql 支持）
        "autocommit": True,          # aiomysql 需要显式开启 autocommit
        "charset": "utf8mb4",
    },
)


async def dispose_engine() -> None:
    """释放引擎连接池中的所有连接。

    应在 event loop 关闭前调用（例如 pytest 的 session/fixture teardown），
    避免 Windows ProactorEventLoop 上 aiomysql 连接在 loop 已关后仍尝试发送
    COM_QUIT 导致 AttributeError: 'NoneType' object has no attribute 'send'。
    """
    await engine.dispose()

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
