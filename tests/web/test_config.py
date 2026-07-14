"""测试 Web 配置加载。"""
from pathlib import Path

from app.config import config


def test_web_config_exists():
    """config.web 应返回 WebSettings 实例。"""
    assert config.web is not None
    assert hasattr(config.web, "mysql_host")


def test_web_config_types():
    """字段类型应正确。"""
    assert isinstance(config.web.mysql_host, str)
    assert isinstance(config.web.mysql_port, int)
    assert isinstance(config.web.jwt_expire_hours, int)
    assert isinstance(config.web.sandbox_data_root, Path)
    assert isinstance(config.web.static_dir, Path)


def test_mysql_url_format():
    """mysql_url 应为 SQLAlchemy 异步兼容格式。"""
    url = config.web.mysql_url
    assert url.startswith("mysql+aiomysql://")
    assert config.web.mysql_user in url
    assert config.web.mysql_database in url
