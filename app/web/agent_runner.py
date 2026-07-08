"""ObservableManus — Manus agent 的事件注入包装器。

通过在关键生命周期节点覆写父类方法，将执行过程以事件流形式
推送到 asyncio.Queue，供 WebSocket 服务消费。
"""

import asyncio
from typing import Any, Optional

from app.agent.manus import Manus
from app.schema import AgentState, ToolCall


class ObservableManus(Manus):
    """Manus 的子类，在执行循环关键节点推送事件。

    用法:
        queue = asyncio.Queue()
        agent = await ObservableManus.create()
        agent.event_queue = queue
        asyncio.create_task(agent.run(prompt))
        # 另一个协程从 queue 中消费事件
    """

    event_queue: Optional[asyncio.Queue] = None

    async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """推送事件到队列。event_queue 为 None 时静默跳过。"""
        if self.event_queue is not None:
            payload = {"type": event_type, **data}
            await self.event_queue.put(payload)

    async def step(self) -> str:
        """执行一步：先推送 step_start 事件，再委托父类。"""
        await self._emit(
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        """思考阶段：调用父类 think() 后，推送 thinking 或 assistant 事件。"""
        should_act = await super().think()

        # 从最后一条 assistant 消息中提取思考内容
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

        # 有思考内容或工具调用时才推送
        if thinking_content or tool_calls_data:
            await self._emit(
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        # 无工具调用但有内容 → agent 的最终回复
        if not should_act and thinking_content and not tool_calls_data:
            await self._emit("assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        """执行工具：推送 tool_start → 执行 → 推送 tool_end。"""
        await self._emit(
            "tool_start",
            {
                "tool": command.function.name,
                "args": command.function.arguments,
            },
        )
        result = await super().execute_tool(command)
        ok = not str(result).startswith("Error:")
        await self._emit(
            "tool_end",
            {"tool": command.function.name, "result": str(result), "ok": ok},
        )
        return result

    async def run(self, request: Optional[str] = None) -> str:
        """运行 agent，推送 done 事件。异常时推送 error。"""
        try:
            result = await super().run(request)
            await self._emit("done", {"reason": "completed"})
            return result
        except Exception as exc:
            await self._emit("error", {"message": str(exc)})
            await self._emit("done", {"reason": "error"})
            raise
