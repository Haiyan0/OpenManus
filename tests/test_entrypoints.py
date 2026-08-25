"""五个启动入口的 env 桥接接入验证。

用 importlib 以非 __main__ 模块名导入入口文件，只触发模块级桥接代码
（entry.apply_env(entry.parse_env())），不执行 if __name__ 块。导入会触发
真实 config 加载：config_dev.toml 缺失时回退 config.example.toml，均可成功。
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRY_FILES = [
    "main.py",
    "run_flow.py",
    "run_mcp.py",
    "run_mcp_server.py",
    "web_run.py",
]


@pytest.fixture(autouse=True)
def _clean_env():
    """每个用例前后清理 OPENMANUS_ENV，避免跨用例污染。"""
    os.environ.pop("OPENMANUS_ENV", None)
    yield
    os.environ.pop("OPENMANUS_ENV", None)


def _load_entry(name: str) -> None:
    """以非 __main__ 模块名导入入口文件，触发其模块级桥接代码。"""
    path = PROJECT_ROOT / name
    spec = importlib.util.spec_from_file_location(f"entry_mod_{name[:-3]}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


@pytest.mark.parametrize("name", ENTRY_FILES)
def test_entry_sets_env_from_positional_arg(name, monkeypatch):
    """python xxx.py test → 模块级桥接写入 OPENMANUS_ENV=test。"""
    monkeypatch.setattr(sys, "argv", [name, "test"])
    _load_entry(name)
    assert os.environ["OPENMANUS_ENV"] == "test"


@pytest.mark.parametrize("name", ENTRY_FILES)
def test_entry_without_arg_keeps_env_absent(name, monkeypatch):
    """python xxx.py（不带参）→ 不写 OPENMANUS_ENV，config 层默认走 dev。"""
    monkeypatch.setattr(sys, "argv", [name])
    _load_entry(name)
    assert "OPENMANUS_ENV" not in os.environ
