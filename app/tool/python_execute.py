import asyncio
import multiprocessing
import os
import sys
import uuid
from io import StringIO
from typing import Dict, Optional

from app.config import config
from app.logger import logger
from app.tool.base import BaseTool


class PythonExecute(BaseTool):
    """Python 代码执行工具。

    支持两种执行模式：
    1. Sandbox 模式：代码写入 workspace 的临时 .py 文件 → 容器内 python 执行
    2. 本地模式（fallback）：通过 multiprocessing.Process 在宿主机执行
    """

    name: str = "python_execute"
    description: str = "执行 Python 代码进行数据分析、统计计算和报告生成。使用 print() 输出结果。"
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的 Python 代码。使用 print() 输出所有结果。使用 pandas 等库进行数据处理，使用 matplotlib/plotly 生成可视化图表。",
            },
        },
        "required": ["code"],
    }

    # Sandbox 注入（可选，由 Agent 或 Web 层设置）
    sandbox: Optional[object] = None
    # 工作目录（sandbox 模式下为 /workspace，本地模式下为 config.workspace_root）
    workspace_dir: str = ""

    def model_post_init(self, __context) -> None:
        """Pydantic 初始化后设置默认工作目录。"""
        if not self.workspace_dir:
            self.workspace_dir = str(config.workspace_root)

    def _run_code(self, code: str, result_dict: dict, safe_globals: dict) -> None:
        original_stdout = sys.stdout
        try:
            output_buffer = StringIO()
            sys.stdout = output_buffer
            exec(code, safe_globals, safe_globals)
            result_dict["observation"] = output_buffer.getvalue()
            result_dict["success"] = True
        except Exception as e:
            result_dict["observation"] = str(e)
            result_dict["success"] = False
        finally:
            sys.stdout = original_stdout

    async def execute(
        self,
        code: str,
        timeout: int = 30,
    ) -> Dict:
        """
        执行 Python 代码。

        有 sandbox 时：写入 workspace 的临时文件 → 容器内执行 → 返回结果。
        无 sandbox 时：通过 multiprocessing.Process 在本地执行（保持向后兼容）。
        """
        if self.sandbox is not None:
            return await self._execute_in_sandbox(code, timeout)
        return await self._execute_local(code, timeout)

    async def _execute_in_sandbox(self, code: str, timeout: int = 30) -> Dict:
        """在 Docker Sandbox 容器内执行 Python 代码。"""
        script_name = f"_sandbox_script_{uuid.uuid4().hex[:8]}.py"
        container_script_path = os.path.join(self.workspace_dir, script_name)

        try:
            await self.sandbox.write_file(container_script_path, code)

            result = await self.sandbox.run_command(
                f"cd {self.workspace_dir} && python {script_name}",
                timeout=timeout,
            )

            return {
                "observation": result,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Sandbox 执行出错: {e}")
            return {
                "observation": f"Sandbox execution error: {str(e)}",
                "success": False,
            }

    async def _execute_local(self, code: str, timeout: int = 30) -> Dict:
        """在本地通过 multiprocessing.Process 执行（向后兼容）。"""
        with multiprocessing.Manager() as manager:
            result = manager.dict({"observation": "", "success": False})
            if isinstance(__builtins__, dict):
                safe_globals = {"__builtins__": __builtins__}
            else:
                safe_globals = {"__builtins__": __builtins__.__dict__.copy()}
            proc = multiprocessing.Process(
                target=self._run_code, args=(code, result, safe_globals)
            )
            proc.start()
            proc.join(timeout)

            if proc.is_alive():
                proc.terminate()
                proc.join(1)
                return {
                    "observation": f"Execution timeout after {timeout} seconds",
                    "success": False,
                }
            return dict(result)
