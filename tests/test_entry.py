"""entry.py 启动桥接逻辑测试：位置参数 env → OPENMANUS_ENV 环境变量。

entry.py 必须在 import app.* 之前运行，故自身不得依赖 app 包
（只依赖标准库），测试也仅验证 argv 解析与 os.environ 写入。
"""
import os

import pytest

import entry


@pytest.fixture(autouse=True)
def _clean_env():
    """每个用例前后清理 OPENMANUS_ENV，避免跨用例污染。"""
    os.environ.pop("OPENMANUS_ENV", None)
    yield
    os.environ.pop("OPENMANUS_ENV", None)


def test_parse_env_positional():
    """位置参数 env 正常解析：["test"] → "test"（argv 语义同 sys.argv[1:]）。"""
    assert entry.parse_env(["test"]) == "test"


def test_parse_env_absent_returns_none():
    """未传位置参数 → None。"""
    assert entry.parse_env([]) is None


def test_parse_env_ignores_other_args():
    """parse_known_args 忽略入口自身参数（如 --prompt），不影响 env 解析。"""
    assert entry.parse_env(["test", "--prompt", "hi"]) == "test"
    assert entry.parse_env(["--prompt", "hi"]) is None


def test_apply_env_sets_and_overrides():
    """传入 env 写入 OPENMANUS_ENV；已有环境变量时参数优先覆盖。"""
    entry.apply_env("test")
    assert os.environ["OPENMANUS_ENV"] == "test"

    os.environ["OPENMANUS_ENV"] = "test"
    entry.apply_env("dev")
    assert os.environ["OPENMANUS_ENV"] == "dev"


def test_apply_env_none_keeps_environment():
    """env 为空不写环境变量：已有值保留，无值则不设置。"""
    os.environ["OPENMANUS_ENV"] = "test"
    entry.apply_env(None)
    assert os.environ["OPENMANUS_ENV"] == "test"

    os.environ.pop("OPENMANUS_ENV", None)
    entry.apply_env(None)
    assert "OPENMANUS_ENV" not in os.environ
