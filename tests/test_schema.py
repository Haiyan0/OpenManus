"""schema.Memory 截断行为测试。

Bug：Memory.add_message 超过 max_messages 时从头部朴素截断，可能把
assistant(tool_calls) 丢弃而留下其 tool 响应，导致下一轮 API 调用报
"Messages with role 'tool' must be a response to a preceding message
with 'tool_calls'"（400），agent 运行中断。
"""
from app.schema import Function, Memory, Message, Role, ToolCall


def _round(k: int) -> list[Message]:
    """构造一轮 [user, assistant(tool_calls), tool] 消息（与 ToolCallAgent 一致）。"""
    call = ToolCall(
        id=f"call_{k}", function=Function(name="python_execute", arguments="{}")
    )
    return [
        Message.user_message(f"step {k}"),
        Message.from_tool_calls([call]),
        Message.tool_message(
            content=f"result {k}", tool_call_id=call.id, name="python_execute"
        ),
    ]


def _assert_tool_pairing(messages: list[Message]) -> None:
    """校验：每个 tool 消息紧跟其后没有前导 assistant tool_calls 即违规。"""
    for i, msg in enumerate(messages):
        if msg.role == Role.TOOL:
            assert i > 0, f"窗口首条是 tool 消息（孤儿）: {msg.tool_call_id}"
            prev = messages[i - 1]
            assert prev.role == Role.ASSISTANT
            ids = [tc.id for tc in prev.tool_calls or []]
            assert msg.tool_call_id in ids


class TestMemoryTrimKeepsToolPairing:
    def test_long_history_trim_never_starts_with_tool(self):
        """118 条消息截断到 100 后，窗口不得以 tool 消息开头。"""
        mem = Memory(max_messages=100)
        mem.add_message(Message.user_message("init"))
        for k in range(1, 40):  # 1 + 39*3 = 118 条
            for m in _round(k):
                mem.add_message(m)

        assert len(mem.messages) <= 100
        assert mem.messages[0].role != Role.TOOL
        _assert_tool_pairing(mem.messages)

    def test_small_window_drops_orphan_tool(self):
        """窗口截断点落在 tool 消息上时，孤儿 tool 必须被丢弃，从下一轮 user 开始。"""
        mem = Memory(max_messages=4)
        for m in _round(1) + _round(2):  # 6 条 → 保留 4 条，首条恰为 t1
            mem.add_message(m)

        assert [m.role for m in mem.messages] == [
            Role.USER,
            Role.ASSISTANT,
            Role.TOOL,
        ]
        assert mem.messages[0].content == "step 2"
        _assert_tool_pairing(mem.messages)

    def test_add_messages_same_protection(self):
        """add_messages 批量追加走同一截断保护。"""
        mem = Memory(max_messages=4)
        mem.add_messages(_round(1) + _round(2))

        assert mem.messages[0].role != Role.TOOL
        _assert_tool_pairing(mem.messages)

    def test_within_limit_untouched(self):
        """未超限时不发生任何截断。"""
        mem = Memory(max_messages=10)
        for m in _round(1) + _round(2):
            mem.add_message(m)

        assert len(mem.messages) == 6
        assert [m.content for m in mem.messages][0] == "step 1"
