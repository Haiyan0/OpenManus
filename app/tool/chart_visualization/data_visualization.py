import asyncio
import json
import os
import posixpath
from pathlib import Path
from typing import Any, Hashable, Optional

import pandas as pd
from pydantic import Field, model_validator

from app.config import config
from app.llm import LLM
from app.logger import logger
from app.tool.base import BaseTool


class DataVisualization(BaseTool):
    name: str = "data_visualization"
    description: str = """Visualize statistical chart or Add insights in chart with JSON info from visualization_preparation tool. You can do steps as follows:
1. Visualize statistical chart
2. Choose insights into chart based on step 1 (Optional)
Outputs:
1. Charts (png/html)
2. Charts Insights (.md)(Optional)"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "json_path": {
                "type": "string",
                "description": """file path of json info with ".json" in the end""",
            },
            "output_type": {
                "description": "Rendering format (html=interactive)",
                "type": "string",
                "default": "html",
                "enum": ["png", "html"],
            },
            "tool_type": {
                "description": "visualize chart or add insights",
                "type": "string",
                "default": "visualization",
                "enum": ["visualization", "insight"],
            },
            "language": {
                "description": "english(en) / chinese(zh)",
                "type": "string",
                "default": "en",
                "enum": ["zh", "en"],
            },
        },
        "required": ["code"],
    }
    llm: LLM = Field(default_factory=LLM, description="Language model instance")

    # Sandbox 注入（可选，由 Agent 的 set_sandbox() 设置）
    sandbox: Optional[object] = None
    # 工作目录（sandbox 模式下为 /workspace，本地模式下为 config.workspace_root）
    workspace_dir: str = ""
    # 宿主机工作目录（sandbox 模式下为宿主机隔离目录，供 npx ts-node 写文件用）
    _host_workspace_dir: str = ""

    def model_post_init(self, __context) -> None:
        """初始化默认工作目录。"""
        if not self.workspace_dir:
            self.workspace_dir = str(config.workspace_root)
        if not self._host_workspace_dir:
            self._host_workspace_dir = str(config.workspace_root)

    @model_validator(mode="after")
    def initialize_llm(self):
        """Initialize llm with default settings if not provided."""
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower())
        return self

    async def _read_json(self, json_path: str) -> list[dict[str, str]]:
        """读取 JSON 信息文件。

        有 sandbox 时：从容器内读取（文件由 visualization_preparation 在容器内生成）。
        无 sandbox 时：直接从宿主机读取（保持向后兼容）。
        """
        if self.sandbox is not None:
            # 智能路径解析：LLM 可能传 /workspace/viz_info.json 或 viz_info.json
            if not json_path.startswith("/"):
                json_path = f"{self.workspace_dir}/{json_path}"
            try:
                raw = await self.sandbox.run_command(f"cat {json_path}")
                return json.loads(raw)
            except Exception as e:
                logger.error(f"Sandbox 读取 JSON 失败: {json_path} → {e}")
                raise Exception(f"No such file or directory: {json_path}")
        else:
            resolved = json_path
            if not os.path.isabs(json_path):
                resolved = str(Path(self.workspace_dir) / json_path)
            with open(resolved, "r", encoding="utf-8") as f:
                return json.load(f)

    async def _read_csv(self, csv_path: str) -> pd.DataFrame:
        """读取 CSV 文件为 DataFrame。

        有 sandbox 时：通过 cat 读取内容 → pandas.read_csv(StringIO)。路径从容器内读。
        无 sandbox 时：直接 pd.read_csv 宿主机文件。
        """
        if self.sandbox is not None:
            # 容器内路径：/workspace/viz/chart_xxx.csv 或 /workspace/chart_xxx.csv
            if not csv_path.startswith("/"):
                csv_path = f"{self.workspace_dir}/{csv_path}"
            raw = await self.sandbox.run_command(f"cat {csv_path}")
            from io import StringIO

            return pd.read_csv(StringIO(raw))
        else:
            return pd.read_csv(csv_path, encoding="utf-8")

    def get_file_path(
        self,
        json_info: list[dict[str, str]],
        path_str: str,
        directory: str = None,
    ) -> list[str]:
        """解析 JSON 中指定的文件路径。

        有 sandbox 时：不做本地 os.path.exists 校验（文件在容器内），
        直接用 json 中声明的路径。
        无 sandbox 时：沿用原有逻辑——校验本地文件存在性并拼接 workspace_root。
        """
        if self.sandbox is not None:
            # sandbox 模式：直接信任 json_info 中的路径，不做宿主机校验
            return [item[path_str] for item in json_info]
        # 本地模式：原有逻辑
        res = []
        for item in json_info:
            if os.path.exists(item[path_str]):
                res.append(item[path_str])
            elif os.path.exists(
                os.path.join(f"{directory or config.workspace_root}", item[path_str])
            ):
                res.append(
                    os.path.join(
                        f"{directory or config.workspace_root}", item[path_str]
                    )
                )
            else:
                raise Exception(f"No such file or directory: {item[path_str]}")
        return res

    def _to_container_path(self, host_path: str) -> str:
        """sandbox 模式：宿主机 chart 路径 → 容器内路径（bind mount 映射）。

        Node 在宿主机写 chart（directory=_host_workspace_dir），返回的
        chart_path 是宿主机绝对路径；容器内 python_execute 只能读到
        bind mount 后的容器路径（/workspace/...），否则 FileNotFoundError。

        无 sandbox 时原样返回（本地模式读写同一路径空间）。
        """
        if self.sandbox is None or not self._host_workspace_dir:
            return host_path
        posix_host = str(host_path).replace("\\", "/")
        posix_root = self._host_workspace_dir.replace("\\", "/").rstrip("/")
        if posix_host.startswith(posix_root):
            rel = posix_host[len(posix_root) :].lstrip("/")
            return posixpath.join(self.workspace_dir, rel)
        return posix_host

    def success_output_template(self, result: list[dict[str, str]]) -> str:
        content = ""
        if len(result) == 0:
            return "Is EMPTY!"
        for item in result:
            content += f"""## {item['title']}\nChart saved in: {self._to_container_path(item['chart_path'])}"""
            if "insight_path" in item and item["insight_path"] and "insight_md" in item:
                content += "\n" + item["insight_md"]
            else:
                content += "\n"
        return f"Chart Generated Successful!\n{content}"

    async def data_visualization(
        self, json_info: list[dict[str, str]], output_type: str, language: str
    ) -> str:
        data_list = []
        csv_file_path = self.get_file_path(json_info, "csvFilePath")
        for index, item in enumerate(json_info):
            df = await self._read_csv(csv_file_path[index])
            df = df.astype(object)
            df = df.where(pd.notnull(df), None)
            data_dict_list = df.to_json(orient="records", force_ascii=False)

            data_list.append(
                {
                    "file_name": os.path.basename(csv_file_path[index]).replace(
                        ".csv", ""
                    ),
                    "dict_data": data_dict_list,
                    "chartTitle": item["chartTitle"],
                }
            )
        tasks = [
            self.invoke_vmind(
                dict_data=item["dict_data"],
                chart_description=item["chartTitle"],
                file_name=item["file_name"],
                output_type=output_type,
                task_type="visualization",
                language=language,
            )
            for item in data_list
        ]

        results = await asyncio.gather(*tasks)
        error_list = []
        success_list = []
        for index, result in enumerate(results):
            csv_path = csv_file_path[index]
            if "error" in result and "chart_path" not in result:
                error_list.append(f"Error in {csv_path}: {result['error']}")
            else:
                success_list.append(
                    {
                        **result,
                        "title": json_info[index]["chartTitle"],
                    }
                )
        if len(error_list) > 0:
            return {
                "observation": f"# Error chart generated{'\n'.join(error_list)}\n{self.success_output_template(success_list)}",
                "success": False,
            }
        else:
            return {"observation": f"{self.success_output_template(success_list)}"}

    async def add_insighs(
        self, json_info: list[dict[str, str]], output_type: str
    ) -> str:
        data_list = []
        chart_file_path = self.get_file_path(
            json_info, "chartPath", os.path.join(config.workspace_root, "visualization")
        )
        for index, item in enumerate(json_info):
            if "insights_id" in item:
                data_list.append(
                    {
                        "file_name": os.path.basename(chart_file_path[index]).replace(
                            f".{output_type}", ""
                        ),
                        "insights_id": item["insights_id"],
                    }
                )
        tasks = [
            self.invoke_vmind(
                insights_id=item["insights_id"],
                file_name=item["file_name"],
                output_type=output_type,
                task_type="insight",
            )
            for item in data_list
        ]
        results = await asyncio.gather(*tasks)
        error_list = []
        success_list = []
        for index, result in enumerate(results):
            chart_path = chart_file_path[index]
            if "error" in result and "chart_path" not in result:
                error_list.append(f"Error in {chart_path}: {result['error']}")
            else:
                success_list.append(self._to_container_path(chart_path))
        success_template = (
            f"# Charts Update with Insights\n{','.join(success_list)}"
            if len(success_list) > 0
            else ""
        )
        if len(error_list) > 0:
            return {
                "observation": f"# Error in chart insights:{'\n'.join(error_list)}\n{success_template}",
                "success": False,
            }
        else:
            return {"observation": f"{success_template}"}

    async def execute(
        self,
        json_path: str,
        output_type: str | None = "html",
        tool_type: str | None = "visualization",
        language: str | None = "en",
    ) -> str:
        try:
            logger.info(f"📈 data_visualization with {json_path} in: {tool_type} ")
            json_info = await self._read_json(json_path)
            if tool_type == "visualization":
                return await self.data_visualization(json_info, output_type, language)
            else:
                return await self.add_insighs(json_info, output_type)
        except Exception as e:
            logger.error(f"data_visualization 执行失败: {e}")
            return {
                "observation": f"Error: {e}",
                "success": False,
            }

    async def invoke_vmind(
        self,
        file_name: str,
        output_type: str,
        task_type: str,
        insights_id: list[str] = None,
        dict_data: list[dict[Hashable, Any]] = None,
        chart_description: str = None,
        language: str = "en",
    ):
        llm_config = {
            "base_url": self.llm.base_url,
            "model": self.llm.model,
            "api_key": self.llm.api_key,
        }
        vmind_params = {
            "llm_config": llm_config,
            "user_prompt": chart_description,
            "dataset": dict_data,
            "file_name": file_name,
            "output_type": output_type,
            "insights_id": insights_id,
            "task_type": task_type,
            "directory": self._host_workspace_dir or self.workspace_dir,
            "language": language,
        }
        # build async sub process
        process = await asyncio.create_subprocess_exec(
            "npx",
            "ts-node",
            "src/chartVisualize.ts",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(__file__),
        )
        input_json = json.dumps(vmind_params, ensure_ascii=False).encode("utf-8")
        try:
            stdout, stderr = await process.communicate(input_json)
            stdout_str = stdout.decode("utf-8")
            stderr_str = stderr.decode("utf-8")
            if process.returncode == 0:
                return json.loads(stdout_str)
            else:
                return {"error": f"Node.js Error: {stderr_str}"}
        except Exception as e:
            return {"error": f"Subprocess Error: {str(e)}"}
