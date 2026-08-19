"""QuickQuery / DataAnalysis prompt 的项目文档引导测试。"""
from app.prompt.quick_query import SYSTEM_PROMPT as QUICK_QUERY_PROMPT
from app.prompt.visualization import SYSTEM_PROMPT as VISUALIZATION_PROMPT


class TestQuickQueryPromptDocGuidance:
    def test_guides_get_doc_first(self):
        assert "get_doc" in QUICK_QUERY_PROMPT
        assert "list_projects" in QUICK_QUERY_PROMPT

    def test_doc_priority_over_table_comment(self):
        assert "文档口径优先于表注释" in QUICK_QUERY_PROMPT

    def test_doc_failure_does_not_block(self):
        assert "不要反复重试" in QUICK_QUERY_PROMPT


class TestVisualizationPromptDocGuidance:
    def test_guides_get_doc_first(self):
        assert "get_doc" in VISUALIZATION_PROMPT
        assert "list_projects" in VISUALIZATION_PROMPT

    def test_doc_priority_over_table_comment(self):
        assert "文档口径优先于表注释" in VISUALIZATION_PROMPT

    def test_doc_failure_does_not_block(self):
        assert "不要反复重试" in VISUALIZATION_PROMPT
