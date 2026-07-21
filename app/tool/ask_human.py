"""
AskHuman 工具 — 支持 WebSocket 事件驱动的用户交互。

有 event_queue 时：emit ask_human 事件到前端 → 等待 WebSocket 响应。
无 event_queue 时：回退到终端 input()（命令行模式）。
"""
import asyncio
from typing import Optional

from app.tool import BaseTool


class AskHuman(BaseTool):
    """向用户提问并等待回复。"""

    name: str = "ask_human"
    description: str = (
        "当你需要向用户确认、澄清需求或询问偏好时使用此工具。"
        "调用后等待用户回复，收到回复后继续执行。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "inquire": {
                "type": "string",
                "description": "你想问用户的问题",
            }
        },
        "required": ["inquire"],
    }

    # WebSocket 事件队列（由 Agent 注入）
    event_queue: Optional[object] = None
    # 等待用户响应的 Future
    _response_future: Optional[asyncio.Future] = None

    async def execute(self, inquire: str) -> str:
        """执行询问操作。

        Web 模式：将问题推送到前端 → 阻塞等待用户回复 → 返回回复内容。
        终端模式：通过 input() 获取用户输入。
        """
        if self.event_queue is not None:
            # Web 模式：emit 事件到前端，等待响应
            await self.event_queue.put({
                "type": "ask_human",
                "content": inquire,
            })
            # 创建 Future 等待前端回复
            self._response_future = asyncio.get_event_loop().create_future()
            try:
                result = await asyncio.wait_for(self._response_future, timeout=600)
                return result
            except asyncio.TimeoutError:
                return "用户未在 10 分钟内回复，请自行决定下一步操作。"
            finally:
                self._response_future = None

        # 终端模式：直接 input()
        return input(f"Bot: {inquire}\n\nYou: ").strip()

    def on_response(self, text: str) -> None:
        """接收来自前端的用户回复（由 ws_handler 调用）。"""
        if self._response_future and not self._response_future.done():
            self._response_future.set_result(text)
