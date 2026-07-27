from app.config import config
from app.tool.base import ToolResult
from app.tool.python_execute import PythonExecute


class NormalPythonExecute(PythonExecute):
    """数据分析专用 Python 执行工具，支持超时与安全限制。"""

    name: str = "python_execute"
    description: str = """执行 Python 代码用于深入数据分析、生成报告、数据可视化等任务。"""

    parameters: dict = {
        "type": "object",
        "properties": {
            "code_type": {
                "description": "代码类型: process(数据处理)、report(生成报告)、visualization(生成可视化图表)、others(其他)",
                "type": "string",
                "default": "process",
                "enum": ["process", "report", "visualization", "others"],
            },
            "code": {
                "type": "string",
                "description": """要执行的 Python 代码。

## 注意事项
1. 使用 print() 输出所有结果，确保分析过程（如"数据概览"、"预处理结果"等）清晰可见
2. 将处理后的数据和报告文件保存到工作目录: {directory}
3. 报告需要内容丰富，包含完整的分析过程和对应的数据可视化
4. 可分步调用此工具，从汇总到深入进行分析

## 可视化生成
- 使用 matplotlib 或 plotly 生成图表
- 图表保存为 PNG 或 HTML 文件到 {directory} 目录
- 用 print() 输出图表文件的完整路径，如 print("图表已保存: {directory}/chart_trend.png")
- 根据数据特征选择合适的图表类型（折线图适合趋势，柱状图适合对比，饼图适合占比）""".format(
                    directory=config.workspace_root
                ),
            },
        },
        "required": ["code"],
    }

    async def execute(self, code: str, code_type: str | None = None, timeout=30):
        """执行 Python 代码，返回 ToolResult。

        Bug1：stdout 全量进 ToolResult.system（不截断，由 ToolCallAgent
        以 system message 形式注入下一轮 think），output 只留短摘要，
        使模型能基于完整数据回答、无需复述被截断的 observation。
        """
        raw = await super().execute(code, timeout)
        observation = raw.get("observation", "")
        success = raw.get("success", False)

        if not success:
            return ToolResult(error=observation)

        n = len(observation)
        return ToolResult(
            output=f"脚本执行成功，stdout 已载入 system（{n} 字符）",
            system=observation,
        )
