"""Agent 工厂 + 事件发射包装器。

每种 Agent 类型对应一个 Observable* 子类，在关键生命周期节点
（step/think/execute_tool/run）推送事件到 asyncio.Queue。
"""

import asyncio
from typing import Any

from app.agent.manus import Manus
from app.agent.data_analysis import DataAnalysis
from app.agent.quick_query import QuickQuery
from app.schema import ToolCall


# ── 事件 Emit 辅助 ────────────────────────────────────


async def _emit(queue: asyncio.Queue, event_type: str, data: dict[str, Any]) -> None:
    """推送事件到 asyncio.Queue。"""
    payload = {"type": event_type, **data}
    await queue.put(payload)


# ── ObservableManus ────────────────────────────────────


class ObservableManus(Manus):
    """Manus 的事件注入子类。"""

    event_queue: asyncio.Queue | None = None

    async def step(self) -> str:
        await _emit(
            self.event_queue,
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        should_act = await super().think()
        last_msg = self.messages[-1] if self.messages else None
        thinking_content = ""
        tool_calls_data: list[dict] = []

        if last_msg and last_msg.role == "assistant":
            thinking_content = last_msg.content or ""
            if last_msg.tool_calls:
                tool_calls_data = [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in last_msg.tool_calls
                ]

        if thinking_content or tool_calls_data:
            await _emit(
                self.event_queue,
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        if not should_act and thinking_content and not tool_calls_data:
            await _emit(self.event_queue, "assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        await _emit(
            self.event_queue,
            "tool_start",
            {"tool": command.function.name, "args": command.function.arguments},
        )
        result = await super().execute_tool(command)
        ok = not str(result).startswith("Error:")
        await _emit(
            self.event_queue,
            "tool_end",
            {"tool": command.function.name, "result": str(result), "ok": ok},
        )
        return result

    async def run(self, request: str | None = None) -> str:
        try:
            result = await super().run(request)
            await _emit(self.event_queue, "done", {"reason": "completed"})
            return result
        except Exception as exc:
            await _emit(self.event_queue, "error", {"message": str(exc)})
            await _emit(self.event_queue, "done", {"reason": "error"})
            raise


# ── ObservableDataAnalysis ─────────────────────────────


class ObservableDataAnalysis(DataAnalysis):
    """DataAnalysis 的事件注入子类。

    与 ObservableManus 完全相同的 emit 逻辑。
    """

    event_queue: asyncio.Queue | None = None

    async def step(self) -> str:
        await _emit(
            self.event_queue,
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        should_act = await super().think()
        last_msg = self.messages[-1] if self.messages else None
        thinking_content = ""
        tool_calls_data: list[dict] = []

        if last_msg and last_msg.role == "assistant":
            thinking_content = last_msg.content or ""
            if last_msg.tool_calls:
                tool_calls_data = [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in last_msg.tool_calls
                ]

        if thinking_content or tool_calls_data:
            await _emit(
                self.event_queue,
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        if not should_act and thinking_content and not tool_calls_data:
            await _emit(self.event_queue, "assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        await _emit(
            self.event_queue,
            "tool_start",
            {"tool": command.function.name, "args": command.function.arguments},
        )
        result = await super().execute_tool(command)
        ok = not str(result).startswith("Error:")
        await _emit(
            self.event_queue,
            "tool_end",
            {"tool": command.function.name, "result": str(result), "ok": ok},
        )
        return result

    async def run(self, request: str | None = None) -> str:
        try:
            result = await super().run(request)
            await _emit(self.event_queue, "done", {"reason": "completed"})
            return result
        except Exception as exc:
            await _emit(self.event_queue, "error", {"message": str(exc)})
            await _emit(self.event_queue, "done", {"reason": "error"})
            raise


# ── ObservableQuickQuery ───────────────────────────────


class ObservableQuickQuery(QuickQuery):
    """QuickQuery 的事件注入子类。

    与 ObservableManus / ObservableDataAnalysis 完全相同的 emit 逻辑。
    """

    event_queue: asyncio.Queue | None = None

    async def step(self) -> str:
        await _emit(
            self.event_queue,
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        should_act = await super().think()
        last_msg = self.messages[-1] if self.messages else None
        thinking_content = ""
        tool_calls_data: list[dict] = []

        if last_msg and last_msg.role == "assistant":
            thinking_content = last_msg.content or ""
            if last_msg.tool_calls:
                tool_calls_data = [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in last_msg.tool_calls
                ]

        if thinking_content or tool_calls_data:
            await _emit(
                self.event_queue,
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        if not should_act and thinking_content and not tool_calls_data:
            await _emit(self.event_queue, "assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        await _emit(
            self.event_queue,
            "tool_start",
            {"tool": command.function.name, "args": command.function.arguments},
        )
        result = await super().execute_tool(command)
        ok = not str(result).startswith("Error:")
        await _emit(
            self.event_queue,
            "tool_end",
            {"tool": command.function.name, "result": str(result), "ok": ok},
        )
        return result

    async def run(self, request: str | None = None) -> str:
        try:
            result = await super().run(request)
            await _emit(self.event_queue, "done", {"reason": "completed"})
            return result
        except Exception as exc:
            await _emit(self.event_queue, "error", {"message": str(exc)})
            await _emit(self.event_queue, "done", {"reason": "error"})
            raise


# ── Agent 工厂 ─────────────────────────────────────────


async def create_observable_agent(
    agent_type: str,
    event_queue: asyncio.Queue,
    sandbox: object | None = None,
    host_workspace: str = "",
) -> Manus | DataAnalysis | QuickQuery:
    """根据 agent_type 创建已初始化的 Observable Agent 实例。

    Args:
        agent_type: "general" → ObservableManus, "data_analysis" → ObservableDataAnalysis
        event_queue: asyncio.Queue，Agent 执行时通过此队列推送事件
        sandbox: DockerSandbox 实例（可选），注入后 PythonExecute 工具在容器内执行
        host_workspace: 宿主机隔离 workspace 目录（供 DataVisualization 宿主机写文件用）

    Returns:
        已初始化（含 MCP 连接）的 Agent 实例

    Raises:
        ValueError: agent_type 不在支持列表中
    """
    if agent_type == "general":
        agent = await ObservableManus.create()
    elif agent_type == "data_analysis":
        agent = ObservableDataAnalysis()
    elif agent_type == "quick_query":
        agent = ObservableQuickQuery()
    else:
        raise ValueError(f"不支持的 agent_type: {agent_type}")

    agent.event_queue = event_queue

    # 注入 Sandbox → Agent 自动传播给所有执行类工具
    if sandbox is not None and hasattr(agent, "set_sandbox"):
        agent.set_sandbox(sandbox, host_workspace=host_workspace)

    # 注入 event_queue → AskHuman（用于前端交互）
    ask_human = agent.available_tools.get_tool("ask_human")
    if ask_human and hasattr(ask_human, "event_queue"):
        ask_human.event_queue = event_queue

    return agent
