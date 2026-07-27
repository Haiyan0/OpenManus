"""QuickQuery 轻量数据查询智能体。

专注于快速数据查询与简单计算，不生成图表和报告。
工具集仅包含 CompanyDataLookup、PythonExecute、AskHuman、Terminate。
"""
from typing import Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.logger import logger
from app.prompt.quick_query import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ask_human import AskHuman
from app.tool.chart_visualization.python_execute import NormalPythonExecute
from app.tool.company_data_lookup import CompanyDataLookup


class QuickQuery(ToolCallAgent):
    """轻量数据查询智能体，专注快速数据查询与简单计算。

    与 DataAnalysis 的区别：
    - 无 VisualizationPrepare / DataVisualization 工具
    - 提示词强调「直接给答案」和「追问先行」
    - max_steps 限制为 15（对比 DataAnalysis 的 60）
    """

    name: str = "quick_query"
    description: str = "轻量数据查询智能体，专注快速数据查询与简单计算，不生成图表和报告"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 15

    # Sandbox 注入（由 Web 层设置，可选）
    sandbox: Optional[object] = None
    _sandbox_workspace: str = ""

    # 工具集合：公司数据查询 + Python 执行 + 人工询问 + 终止
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            CompanyDataLookup(),
            NormalPythonExecute(),
            AskHuman(),
            Terminate(),
        )
    )

    def set_sandbox(
        self, sandbox: object, workspace: str = "/workspace", host_workspace: str = ""
    ) -> None:
        """注入 Sandbox 并同步到所有执行类工具。

        与 DataAnalysis.set_sandbox() 逻辑完全一致。

        Args:
            sandbox: DockerSandbox 实例
            workspace: 容器内工作目录路径，默认 /workspace
            host_workspace: 宿主机工作目录绝对路径（保留参数兼容性）
        """
        self.sandbox = sandbox
        self._sandbox_workspace = workspace

        # 修正 system_prompt 中的目录路径为容器内路径
        self.system_prompt = SYSTEM_PROMPT.format(directory=workspace)

        # 遍历所有工具，注入 sandbox 和 workspace 属性
        for tool in self.available_tools:
            if hasattr(tool, "sandbox"):
                tool.sandbox = sandbox
                logger.debug(f"Sandbox 已注入工具: {tool.name}")
            if hasattr(tool, "workspace_dir") and workspace:
                tool.workspace_dir = workspace
                logger.debug(f"Workspace 已注入工具: {tool.name} → {workspace}")
            # 宿主机挂载源目录（CompanyDataLookup 写 CSV 用，容器经 bind mount 可见）
            if hasattr(tool, "host_workspace_dir") and host_workspace:
                tool.host_workspace_dir = host_workspace
                logger.debug(f"HostWorkspace 已注入工具: {tool.name} → {host_workspace}")
            # 修正发给 LLM 的工具描述中的宿主机路径 → 容器内路径
            if hasattr(tool, "parameters") and isinstance(tool.parameters, dict):
                code_desc = (
                    tool.parameters.get("properties", {})
                    .get("code", {})
                    .get("description", "")
                )
                if code_desc and str(config.workspace_root) in code_desc:
                    tool.parameters["properties"]["code"][
                        "description"
                    ] = code_desc.replace(str(config.workspace_root), workspace)
                    logger.debug(f"ToolDesc 已更新: {tool.name} → {workspace}")
