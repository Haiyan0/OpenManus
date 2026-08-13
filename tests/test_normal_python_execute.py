"""NormalPythonExecute 返回 ToolResult 的测试（Bug1）。

验证 stdout 全量进 ToolResult.system（不截断），output 只留短摘要，
使 ToolCallAgent 把数据以 system message 形式注入下一轮 think，
模型无需复述被截断的 observation。
"""
import pytest

from app.tool.base import ToolResult
from app.tool.chart_visualization.python_execute import NormalPythonExecute


@pytest.mark.asyncio
async def test_normal_python_execute_wraps_stdout_into_system():
    """成功执行：stdout 进 system，output 是短摘要。"""
    tool = NormalPythonExecute()
    tool.sandbox = None  # 本地执行，避免依赖 Docker

    result = await tool.execute(code="print('A=1'); print('B=2')")

    assert isinstance(result, ToolResult)
    assert result.error is None
    # 全量 stdout 进 system
    assert result.system is not None
    assert "A=1" in result.system
    assert "B=2" in result.system
    # output 应是短摘要，不含原始数据行（避免模型复述被截断的输出）
    assert result.output is not None
    assert "A=1" not in str(result.output)
    assert "B=2" not in str(result.output)
    assert "system" in str(result.output)


@pytest.mark.asyncio
async def test_normal_python_execute_error_goes_to_error_field():
    """执行失败：异常信息进 error 字段。"""
    tool = NormalPythonExecute()
    tool.sandbox = None

    result = await tool.execute(code="raise ValueError('boom')")

    assert isinstance(result, ToolResult)
    assert result.error is not None
    assert "boom" in result.error


def test_code_description_contains_preview_rules():
    """工具描述必须包含「数据读取规范」关键约束（回归防误删）。"""
    tool = NormalPythonExecute()
    desc = tool.parameters["properties"]["code"]["description"]
    assert "前 5 行" in desc
    assert "严禁打印全量数据" in desc
    assert "df.head(5)" in desc
    assert "df.to_string" in desc
