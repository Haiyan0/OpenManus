"""公众号发布智能体。"""

from typing import Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.logger import logger
from app.prompt.wechat_publish import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ask_human import AskHuman
from app.tool.chart_visualization.python_execute import NormalPythonExecute
from app.tool.wechat_publish.wechat_publish import WechatPublishTool


class WechatPublish(ToolCallAgent):
    """公众号发布智能体：把文章发布到微信公众号草稿箱。"""

    name: str = "wechat_publish"
    description: str = "公众号发布智能体，可将 markdown 内容发布到微信公众号草稿箱"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 30

    # Sandbox 注入（由 Web 层设置，可选）
    sandbox: Optional[object] = None
    _sandbox_workspace: str = ""

    # 工具集合：公众号发布 + Python 执行 + 人工询问 + 终止
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            WechatPublishTool(),
            NormalPythonExecute(),
            AskHuman(),
            Terminate(),
        )
    )

    def set_sandbox(
        self, sandbox: object, workspace: str = "/workspace", host_workspace: str = ""
    ) -> None:
        """注入 Sandbox 并同步到所有执行类工具（与 QuickQuery.set_sandbox 一致）。"""
        self.sandbox = sandbox
        self._sandbox_workspace = workspace
        self.system_prompt = SYSTEM_PROMPT.format(directory=workspace)
        for tool in self.available_tools:
            if hasattr(tool, "sandbox"):
                tool.sandbox = sandbox
            if hasattr(tool, "workspace_dir") and workspace:
                tool.workspace_dir = workspace
            if hasattr(tool, "host_workspace_dir") and host_workspace:
                tool.host_workspace_dir = host_workspace
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
