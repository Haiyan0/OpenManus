"""数据读取上下文精简：Agent system prompt 数据读取规范回归测试。

防止未来编辑提示词时误删「只打印预览、禁全量数据」约束。
"""
from app.prompt.quick_query import SYSTEM_PROMPT as QQ_PROMPT
from app.prompt.visualization import SYSTEM_PROMPT as VIZ_PROMPT


def test_quick_query_prompt_contains_preview_rules():
    assert "前 5 行" in QQ_PROMPT
    assert "严禁打印全量数据" in QQ_PROMPT
    assert "df.to_string" in QQ_PROMPT


def test_visualization_prompt_contains_preview_rules():
    assert "前 5 行" in VIZ_PROMPT
    assert "严禁打印全量数据" in VIZ_PROMPT
    assert "df.to_string" in VIZ_PROMPT
