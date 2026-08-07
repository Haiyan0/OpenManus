from typing import Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.logger import logger
from app.prompt.visualization import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ask_human import AskHuman
from app.tool.chart_visualization.chart_prepare import VisualizationPrepare
from app.tool.chart_visualization.data_visualization import DataVisualization
from app.tool.chart_visualization.python_execute import NormalPythonExecute
from app.tool.company_data_lookup import CompanyDataLookup


class DataAnalysis(ToolCallAgent):
    """
    数据分析智能体，使用规划来解决各类数据分析任务。

    此智能体继承 ToolCallAgent，拥有完整的数据分析、可视化与报告生成能力。
    """

    name: str = "data_analysis"
    description: str = "专为数据分析与可视化打造的分析型智能体，能调用 Python 执行、公司数据查询等工具完成数据任务"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 50000
    max_steps: int = 60

    # Sandbox 注入（由 Web 层设置，可选）
    sandbox: Optional[object] = None
    # Sandbox 模式下的工作目录（容器内路径，如 /workspace）
    _sandbox_workspace: str = ""

    # 工具集合：Python 执行 + 公司数据查询 + 人工询问 + 终止
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            CompanyDataLookup(),
            NormalPythonExecute(),
            VisualizationPrepare(),
            DataVisualization(),
            AskHuman(),
            Terminate(),
        )
    )

    def set_sandbox(
        self, sandbox: object, workspace: str = "/workspace", host_workspace: str = ""
    ) -> None:
        """注入 Sandbox 并同步到所有执行类工具。

        调用时机：Agent 创建后、run() 之前。

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
            # DataVisualization 的字段名带下划线前缀（npx ts-node 宿主机写 chart 用）
            if hasattr(tool, "_host_workspace_dir") and host_workspace:
                tool._host_workspace_dir = host_workspace
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
