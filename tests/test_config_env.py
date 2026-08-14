"""多环境配置加载单元测试（不依赖真实密钥文件）。

config.llm 的 "default" 键由 [llm] 段顶层标量构成（见 app/config.py
_load_initial_config 的 default_settings 合并逻辑），因此假 toml 只需
[llm] 顶层字段 + [daytona] 最小段（daytona_api_key 必填）即可断言
config.llm["default"].model。
"""
import os

import pytest

import app.config as config_module
from app.config import Config


@pytest.fixture(autouse=True)
def _reset_singleton():
    """每个用例前后重置单例与环境变量，避免跨用例污染。

    注意：重置只清空类属性，模块级 config 仍指向已加载真实配置的旧实例，
    故用例内需用 Config() 新建实例触发重新加载（见 fake_config_dir 用途）。
    """
    config_module.Config._instance = None
    config_module.Config._initialized = False
    os.environ.pop("OPENMANUS_ENV", None)
    yield
    config_module.Config._instance = None
    config_module.Config._initialized = False
    os.environ.pop("OPENMANUS_ENV", None)


@pytest.fixture
def fake_config_dir(tmp_path, monkeypatch):
    """构造带 dev/test/example 三文件（或按 need 定制）的假 config 目录。"""
    cfg = tmp_path / "config"
    cfg.mkdir()
    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
    return cfg


def _write(cfg_dir, name, model):
    (cfg_dir / name).write_text(
        f'[llm]\nmodel = "{model}"\nbase_url = "u"\napi_key = "k"\n'
        'api_type = "openai"\napi_version = ""\n'
        '[daytona]\ndaytona_api_key = "k"\n',
        encoding="utf-8",
    )


def test_env_var_selects_test_config(fake_config_dir):
    """OPENMANUS_ENV=test → 加载 config_test.toml。"""
    _write(fake_config_dir, "config_dev.toml", "dev-model")
    _write(fake_config_dir, "config_test.toml", "test-model")
    os.environ["OPENMANUS_ENV"] = "test"

    assert Config().llm["default"].model == "test-model"


def test_defaults_to_dev(fake_config_dir):
    """未设置环境变量 → 默认加载 config_dev.toml。"""
    _write(fake_config_dir, "config_dev.toml", "dev-model")
    _write(fake_config_dir, "config_test.toml", "test-model")

    assert Config().llm["default"].model == "dev-model"


def test_empty_env_var_means_dev(fake_config_dir):
    """OPENMANUS_ENV 为空串/空白 → 视为未设置，走 dev。"""
    _write(fake_config_dir, "config_dev.toml", "dev-model")
    os.environ["OPENMANUS_ENV"] = "   "

    assert Config().llm["default"].model == "dev-model"


def test_missing_env_file_raises_with_available_list(fake_config_dir):
    """指定环境文件缺失 → FileNotFoundError，报错含可用环境清单。"""
    _write(fake_config_dir, "config_dev.toml", "dev-model")
    _write(fake_config_dir, "config_test.toml", "test-model")
    os.environ["OPENMANUS_ENV"] = "prod"

    with pytest.raises(FileNotFoundError) as exc:
        Config._get_config_path()
    msg = str(exc.value)
    assert "prod" in msg
    assert "dev" in msg and "test" in msg


def test_dev_missing_falls_back_to_example(fake_config_dir):
    """dev 文件缺失 → 回退 config.example.toml（现有行为）。"""
    _write(fake_config_dir, "config.example.toml", "example-model")

    assert Config().llm["default"].model == "example-model"


def test_get_env_priority_default(fake_config_dir):
    """get_env 直接返回解析结果：设了返回值，否则 dev。"""
    assert config_module.get_env() == "dev"
    os.environ["OPENMANUS_ENV"] = "test"
    assert config_module.get_env() == "test"
    os.environ["OPENMANUS_ENV"] = ""
    assert config_module.get_env() == "dev"
