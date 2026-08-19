"""project_docs 模块（项目业务文档检索）单元测试。"""
from pathlib import Path

import pytest

from app.tool.project_docs import DOCS_DIR, get_doc, list_projects


@pytest.fixture
def docs_tree(tmp_path: Path) -> Path:
    """搭建 project_docs 目录树：
    甲企业/项目A（1 个 md）、甲企业/项目B（无 md）、乙企业/项目C（2 个 md）
    """
    root = tmp_path / DOCS_DIR
    (root / "甲企业" / "项目A").mkdir(parents=True)
    (root / "甲企业" / "项目B").mkdir(parents=True)
    (root / "乙企业" / "项目C").mkdir(parents=True)
    (root / "甲企业" / "项目A" / "业务说明.md").write_text(
        "# 项目A 业务数据说明\n\n## 3. 字段口径说明\n合同金额用 amount 字段",
        encoding="utf-8",
    )
    (root / "乙企业" / "项目C" / "01-字段.md").write_text(
        "# C 字段口径", encoding="utf-8"
    )
    (root / "乙企业" / "项目C" / "02-SQL.md").write_text(
        "# C 查询示例", encoding="utf-8"
    )
    return root


class TestListProjects:
    def test_lists_all_companies_and_doc_status(self, docs_tree):
        result = list_projects(root=docs_tree)
        assert result.error is None
        assert "甲企业" in result.output
        assert "乙企业" in result.output
        assert "项目A" in result.output
        assert "项目C" in result.output
        assert "业务说明.md" in result.output
        assert "01-字段.md" in result.output
        assert "[无文档]" in result.output  # 项目B 无文档

    def test_missing_dir_degrades_with_hint(self, tmp_path):
        result = list_projects(root=tmp_path / "nope")
        assert result.error is not None
        assert "list_tables" in result.error

    def test_empty_query_lists_all(self, docs_tree):
        result = list_projects(query="", root=docs_tree)
        assert result.error is None
        assert "甲企业" in result.output and "乙企业" in result.output

    def test_company_filter(self, docs_tree):
        result = list_projects(query="乙企业", root=docs_tree)
        assert result.error is None
        assert "乙企业" in result.output
        assert "甲企业" not in result.output

    def test_company_matched_but_no_projects(self, tmp_path):
        root = tmp_path / DOCS_DIR
        (root / "空企业").mkdir(parents=True)
        result = list_projects(query="空企业", root=root)
        assert result.error is None
        assert "空企业" in result.output
        assert "[无项目目录]" in result.output

    def test_no_company_match_returns_available_list(self, docs_tree):
        result = list_projects(query="不存在的企业", root=docs_tree)
        assert result.error is not None
        assert "甲企业" in result.error
        assert "乙企业" in result.error


class TestGetDocMatch:
    def test_exact_path_hit(self, docs_tree):
        result = get_doc("甲企业/项目A", root=docs_tree)
        assert result.error is None
        assert "字段口径说明" in result.output
        assert "amount" in result.output

    def test_project_name_unique_hit(self, docs_tree):
        result = get_doc("项目A", root=docs_tree)
        assert result.error is None
        assert "amount" in result.output

    def test_case_insensitive(self, docs_tree):
        result = get_doc("项目a", root=docs_tree)
        assert result.error is None

    def test_ambiguous_returns_candidates(self, docs_tree):
        # "项目" 同时命中 项目A/项目B/项目C
        result = get_doc("项目", root=docs_tree)
        assert result.error is not None
        assert "甲企业/项目A" in result.error
        assert "甲企业/项目B" in result.error
        assert "乙企业/项目C" in result.error

    def test_no_match_returns_available_list(self, docs_tree):
        result = get_doc("不存在", root=docs_tree)
        assert result.error is not None
        assert "项目A" in result.error

    def test_company_hit_without_project_lists_projects(self, docs_tree):
        result = get_doc("甲企业", root=docs_tree)
        assert result.error is not None
        assert "项目A" in result.error

    def test_empty_query_asks_for_name(self, docs_tree):
        result = get_doc("", root=docs_tree)
        assert result.error is not None
        assert "list_projects" in result.error

    def test_missing_dir_degrades(self, tmp_path):
        result = get_doc("项目A", root=tmp_path / "nope")
        assert result.error is not None
        assert "list_tables" in result.error


class TestGetDocContent:
    def test_multiple_md_joined_in_name_order(self, docs_tree):
        result = get_doc("项目C", root=docs_tree)
        assert result.error is None
        assert "C 字段口径" in result.output
        assert "C 查询示例" in result.output
        # 01 在 02 之前
        assert result.output.index("C 字段口径") < result.output.index("C 查询示例")

    def test_project_without_doc_reports(self, docs_tree):
        result = get_doc("项目B", root=docs_tree)
        assert result.error is not None
        assert "尚未维护" in result.error
