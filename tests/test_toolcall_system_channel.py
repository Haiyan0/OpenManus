"""ToolCallAgent 的 system 数据通道测试（Bug1：输出被截断）。

验证工具返回的 ToolResult.system（全量数据）会：
1. 被 execute_tool 收集到 pending_systems（不受 max_observe 截断）
2. 在下一轮 think() 作为 system message 注入给 LLM
3. 注入后清空，避免重复

这样模型能直接基于完整数据回答，无需复述被截断的 observation。
"""
from types import SimpleNamespace

import pytest

from app.agent.toolcall import ToolCallAgent
from app.schema import Function, ToolCall
from app.tool import ToolCollection
from app.tool.base import BaseTool, ToolResult


class _RecordingLLM:
    """记录 ask_tool 收到的 system_msgs，返回无 tool_calls 的回复。"""

    def __init__(self):
        self.captured_system_batches: list[list] = []

    async def ask_tool(
        self, *, messages, system_msgs=None, tools=None, tool_choice=None
    ):
        if system_msgs:
            self.captured_system_batches.append(list(system_msgs))
        return SimpleNamespace(tool_calls=None, content="done")


class _DataTool(BaseTool):
    """返回带 system 字段的 ToolResult（模拟 python_execute 全量 stdout）。"""

    name: str = "data_tool"
    description: str = "返回带 system 数据的工具"
    parameters: dict = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(output="摘要：1 行", system="完整数据：A=1,B=2,C=3")


class _StructuredOutputTool(BaseTool):
    """返回结构化 output 的工具。"""

    name: str = "structured_tool"
    description: str = "返回 dict output 的工具"
    parameters: dict = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(output={"ok": True, "items": ["a", "b"]})


class _CaptureArgsTool(BaseTool):
    """回显解析后的工具参数。"""

    name: str = "capture_args"
    description: str = "回显参数"
    parameters: dict = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(output=kwargs)


def _make_agent() -> tuple[ToolCallAgent, _RecordingLLM]:
    rec = _RecordingLLM()
    agent = ToolCallAgent(available_tools=ToolCollection(_DataTool()))
    agent.system_prompt = "你是助手"
    agent.next_step_prompt = "继续"
    agent.llm.ask_tool = rec.ask_tool
    return agent, rec


@pytest.mark.asyncio
async def test_think_injects_pending_systems_into_llm():
    """pending_systems 应作为 system message 注入给 LLM，注入后清空。"""
    agent, rec = _make_agent()
    agent.pending_systems = ["完整数据：A=1,B=2,C=3"]

    await agent.think()

    assert rec.captured_system_batches, "LLM 未收到任何 system_msgs"
    flat = [m.content for batch in rec.captured_system_batches for m in batch]
    assert any("完整数据" in (c or "") for c in flat), "system 数据未注入到 LLM 的 system message"
    assert agent.pending_systems == [], "注入后未清空 pending_systems"


@pytest.mark.asyncio
async def test_execute_tool_collects_system_from_tool_result():
    """工具返回 ToolResult.system 时，execute_tool 应收集到 pending_systems。"""
    agent, _rec = _make_agent()
    agent.pending_systems = []

    command = ToolCall(
        id="call_1",
        function=Function(name="data_tool", arguments="{}"),
    )
    await agent.execute_tool(command)

    assert agent.pending_systems == ["完整数据：A=1,B=2,C=3"]


@pytest.mark.asyncio
async def test_execute_tool_renders_structured_tool_result():
    """工具返回 dict/list 等结构化 output 时，execute_tool 也应能渲染 observation。"""
    agent = ToolCallAgent(available_tools=ToolCollection(_StructuredOutputTool()))

    command = ToolCall(
        id="call_structured",
        function=Function(name="structured_tool", arguments="{}"),
    )
    observation = await agent.execute_tool(command)

    assert observation.startswith("Observed output of cmd `structured_tool` executed:")
    assert '"ok": true' in observation
    assert '"items": [' in observation


@pytest.mark.asyncio
async def test_execute_tool_repairs_unkeyed_strings_in_object_arguments():
    """对象内误写裸字符串条目时，应修复为带自动键的合法 JSON 再执行工具。"""
    agent = ToolCallAgent(available_tools=ToolCollection(_CaptureArgsTool()))
    invalid_arguments = (
        '{"action": "analyze_inputs", '
        '"materials": {"C真实经验": {"平台用户20万", "缺口": "个人使用体验"}}}'
    )

    command = ToolCall(
        id="call_repair",
        function=Function(name="capture_args", arguments=invalid_arguments),
    )
    observation = await agent.execute_tool(command)

    assert not observation.startswith("Error:")
    assert "平台用户20万" in observation
    assert '"缺口": "个人使用体验"' in observation
