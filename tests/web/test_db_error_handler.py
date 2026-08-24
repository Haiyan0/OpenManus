"""OperationalError → 503 优雅降级测试。

生产场景：RDS 空闲后首次请求连接超时（OperationalError 2003），
应返回 503 JSON 提示，而不是 500 traceback。
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.web.server import app


def _db_down():
    raise OperationalError("SELECT 1", {}, Exception("connection refused"))


@pytest.mark.asyncio
async def test_db_operational_error_returns_503_json():
    app.add_api_route("/_test_db_down", _db_down, methods=["GET"])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/_test_db_down")

    assert resp.status_code == 503
    assert "数据库" in resp.json()["detail"]
