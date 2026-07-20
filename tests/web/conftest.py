"""pytest 配置 — 每个异步测试后释放数据库引擎连接池。

pytest-asyncio (auto 模式) 为每个异步测试函数创建新 event loop。
模块级 engine 单例的连接池持有上一个 loop 创建的 aiomysql 连接，
旧连接在新 loop 上 GC 时因 Proactor 已关触发:
    AttributeError: 'NoneType' object has no attribute 'send'

本 fixture 在每个异步测试结束后，在同一 loop 上 dispose 引擎，
确保连接在 loop 仍存活时正常释放。
"""
import pytest_asyncio


@pytest_asyncio.fixture(scope="function", autouse=True)
async def _cleanup_engine_after_test():
    """每个异步测试函数 yield 后释放引擎连接池。"""
    yield
    from app.web.database import dispose_engine

    await dispose_engine()
