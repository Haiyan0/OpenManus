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
    A data analysis agent that uses planning to solve various data analysis tasks.

    This agent extends ToolCallAgent with a comprehensive set of tools and capabilities,
    including Data Analysis, Chart Visualization, Data Report.
    """

    name: str = "Data_Analysis"
    description: str = "An analytical agent that utilizes python and data visualization tools to solve diverse data analysis tasks"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 15000
    max_steps: int = 60

    # Sandbox 注入（由 Web 层设置，可选）
    sandbox: Optional[object] = None
    # Sandbox 模式下的工作目录（容器内路径，如 /workspace）
    _sandbox_workspace: str = ""

    # Add general-purpose tools to the tool collection
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

    def set_sandbox(self, sandbox: object, workspace: str = "/workspace", host_workspace: str = "") -> None:
        """注入 Sandbox 并同步到所有执行类工具。

        调用时机：Agent 创建后、run() 之前。

        Args:
            sandbox: DockerSandbox 实例
            workspace: 容器内工作目录路径，默认 /workspace
            host_workspace: 宿主机工作目录绝对路径（供 npx ts-node 写 chart 文件用）
        """
        self.sandbox = sandbox
        self._sandbox_workspace = workspace

        # 修正 system_prompt 中的目录路径为容器内路径
        self.system_prompt = SYSTEM_PROMPT.format(directory=workspace)

        # 遍历所有工具，有 sandbox 属性的都注入
        for tool in self.available_tools:
            if hasattr(tool, "sandbox"):
                tool.sandbox = sandbox
                logger.debug(f"Sandbox 已注入工具: {tool.name}")
            if hasattr(tool, "workspace_dir") and workspace:
                tool.workspace_dir = workspace
                logger.debug(f"Workspace 已注入工具: {tool.name} → {workspace}")
            # 修正发给 LLM 的工具描述中的宿主机路径 → 容器内路径
            # NormalPythonExecute/VisualizationPrepare 在类定义时硬编码了 config.workspace_root，
            # 不更新的话 LLM 会生成用宿主机路径的代码，容器内找不到文件，分析直接失败。
            if hasattr(tool, "parameters") and isinstance(tool.parameters, dict):
                code_desc = (
                    tool.parameters.get("properties", {}).get("code", {}).get("description", "")
                )
                if code_desc and str(config.workspace_root) in code_desc:
                    tool.parameters["properties"]["code"]["description"] = (
                        code_desc.replace(str(config.workspace_root), workspace)
                    )
                    logger.debug(f"ToolDesc 已更新: {tool.name} → {workspace}")
            # DataVisualization 的 invoke_vmind 用 npx ts-node 在宿主机写文件，
            # 需要宿主机路径而非容器内路径
            if hasattr(tool, "_host_workspace_dir") and host_workspace:
                tool._host_workspace_dir = host_workspace
                logger.debug(f"HostWorkspace 已注入工具: {tool.name} → {host_workspace}")
