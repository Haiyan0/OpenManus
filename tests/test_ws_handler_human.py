"""ws_handler 的 ask_human 死锁修复测试（Bug4）。

验证：agent 被 ask_human 阻塞期间，WS 上发来的 human_response
能被并发 reader 读到并投递给 ask_human.on_response，使 future resolve。
"""
import asyncio

import pytest
from fastapi import WebSocketDisconnect

from app.tool.ask_human import AskHuman
from app.web.chat.ws_handler import route_human_responses


class _FakeWS:
    """按预设序列返回消息，耗尽后抛 WebSocketDisconnect。"""

    def __init__(self, messages):
        self._msgs = list(messages)

    async def receive_json(self):
        if not self._msgs:
            raise WebSocketDisconnect()
        return self._msgs.pop(0)


class _FakeTools:
    def __init__(self, ask_human):
        self._ah = ask_human

    def get_tool(self, name):
        return self._ah if name == "ask_human" else None


class _FakeAgent:
    def __init__(self, ask_human):
        self.available_tools = _FakeTools(ask_human)


@pytest.mark.asyncio
async def test_human_response_resolves_ask_human_future():
    """human_response 到达后，ask_human 的 future 应被 resolve。"""
    ah = AskHuman()
    ah.event_queue = object()  # 标记为 Web 模式
    loop = asyncio.get_event_loop()
    ah._response_future = loop.create_future()

    ws = _FakeWS([{"type": "human_response", "content": "用去年数据"}])
    agent = _FakeAgent(ah)
    stop = asyncio.Event()

    await route_human_responses(ws, agent, stop)

    assert ah._response_future.done()
    assert ah._response_future.result() == "用去年数据"
    assert stop.is_set()  # WS 断开后应置位 stop


@pytest.mark.asyncio
async def test_non_human_response_ignored():
    """非 human_response 消息不应触发 on_response；但 reader 仍继续读到断开。"""
    ah = AskHuman()
    ah.event_queue = object()
    loop = asyncio.get_event_loop()
    ah._response_future = loop.create_future()

    ws = _FakeWS([{"type": "prompt", "content": "hello"}])
    agent = _FakeAgent(ah)
    stop = asyncio.Event()

    await route_human_responses(ws, agent, stop)

    assert not ah._response_future.done()
    assert stop.is_set()
