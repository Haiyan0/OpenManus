"""GEO 内容生产 Agent 专用工具。"""

from app.tool.base import BaseTool, ToolResult
from app.tool.geo_content.service import GeoContentService


class GeoContentTool(BaseTool):
    """暴露 GEO SOP 的确定性动作。"""

    name: str = "geo_content"
    description: str = "读取 GEO 知识、维护工作状态、检查素材缺口并保存交付文件"
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "load_knowledge",
                    "load_state",
                    "save_state",
                    "analyze_inputs",
                    "quality_check",
                    "save_deliverables",
                ],
            },
            "topic": {"type": "string"},
            "content": {"type": "string"},
            "materials": {"type": "object"},
            "article": {"type": "string"},
            "source_notes": {"type": "string"},
            "publish_config": {"type": "string"},
            "scorecard": {"type": "string"},
            "date": {"type": "string"},
        },
        "required": ["action"],
    }
    workspace_dir: str = "/workspace"

    async def execute(self, action: str, **kwargs) -> ToolResult:
        service = GeoContentService(self.workspace_dir)
        if action == "load_state":
            return ToolResult(output=service.load_state())
        if action == "save_state":
            return ToolResult(output=service.save_state(kwargs.get("content", "")))
        if action == "load_knowledge":
            return ToolResult(output=service.load_knowledge(kwargs.get("topic", "")))
        if action == "analyze_inputs":
            return ToolResult(
                output=service.analyze_inputs(kwargs.get("materials") or {})
            )
        if action == "quality_check":
            return ToolResult(
                output=service.quality_check(
                    article=kwargs.get("article", ""),
                    source_notes=kwargs.get("source_notes", ""),
                )
            )
        if action == "save_deliverables":
            return ToolResult(
                output=service.save_deliverables(
                    topic=kwargs.get("topic", ""),
                    article=kwargs.get("article", ""),
                    publish_config=kwargs.get("publish_config", ""),
                    scorecard=kwargs.get("scorecard", ""),
                    date_str=kwargs.get("date"),
                )
            )
        return ToolResult(
            error=(f"不支持的 GEO action: {action}。" "样本库、benchmark 和评分权重更新仅面向开发者维护。")
        )
