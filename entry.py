"""多环境配置启动桥接：入口脚本在 import app.* 之前解析环境并写入 OPENMANUS_ENV。

约束：本模块只允许依赖标准库——app.config 的单例在首次 import 时完成加载，
若本模块 import app 包会先于环境变量写入触发配置加载，桥接即失效。
"""
import os
import sys
from typing import List, Optional


def parse_env(argv: Optional[List[str]] = None) -> Optional[str]:
    """从命令行位置参数解析环境名（可空）。

    argv 语义同 sys.argv[1:]（不含脚本名），未传时默认读 sys.argv[1:]。
    启动方式约定为 `python xxx.py dev`：env 紧跟脚本名，故仅当 argv
    首元素不是选项（不以 - 开头）时视为环境名。
    """
    if argv is None:
        argv = sys.argv[1:]
    if argv and not argv[0].startswith("-"):
        return argv[0]
    return None


def apply_env(env: Optional[str]) -> None:
    """若传入环境名，写入 OPENMANUS_ENV（参数优先，覆盖已设的环境变量）。

    不传参时不写环境变量，由 config 层默认走 dev（或读已有的 OPENMANUS_ENV）。
    """
    if env:
        os.environ["OPENMANUS_ENV"] = env
