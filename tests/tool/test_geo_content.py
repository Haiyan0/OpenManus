from pathlib import Path

import pytest

from app.tool.geo_content.geo_content import GeoContentTool
from app.tool.geo_content.service import GeoContentService


def test_load_knowledge_reads_repository_file(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "quality-checklist.md").write_text("质量清单", encoding="utf-8")
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=knowledge_dir)

    result = service.load_knowledge("quality_checklist")

    assert result["topic"] == "quality_checklist"
    assert result["content"] == "质量清单"


def test_load_knowledge_rejects_unknown_topic(tmp_path):
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=tmp_path)

    result = service.load_knowledge("update_weights")

    assert result["ok"] is False
    assert "不支持" in result["error"]


def test_state_round_trip_stays_inside_workspace(tmp_path):
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=tmp_path)

    saved = service.save_state("# GEO Working Data\n\n## Stage\ncollecting")
    loaded = service.load_state()

    assert saved["ok"] is True
    assert Path(saved["path"]).name == "_working-data.md"
    assert loaded["exists"] is True
    assert "collecting" in loaded["content"]
    assert (tmp_path / "_working-data.md").exists()


def test_analyze_inputs_reports_missing_a_f_fields(tmp_path):
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=tmp_path)

    result = service.analyze_inputs({"business": "AI 搜索优化服务"})

    assert result["ok"] is True
    assert result["complete"] is False
    assert "authority" in result["missing_fields"]
    assert "sources" in result["missing_fields"]
    assert "faq" in result["missing_fields"]


def test_analyze_inputs_complete_when_all_required_fields_exist(tmp_path):
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=tmp_path)
    materials = {
        "business": "AI 搜索优化服务",
        "authority": "官网文档和客户授权案例",
        "experience": "三个月交付流程",
        "intent_words": "GEO 优化怎么做",
        "sources": "https://example.invalid/source-not-fetched",
        "faq": "Q: 多久见效 A: 视素材完整度而定",
    }

    result = service.analyze_inputs(materials)

    assert result["complete"] is True
    assert result["missing_fields"] == []


def test_save_deliverables_sanitizes_topic_and_writes_three_files(tmp_path):
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=tmp_path)

    result = service.save_deliverables(
        topic="GEO/内容:测试?",
        article="# 正文",
        publish_config="# 发布配置",
        scorecard="# 评分卡",
        date_str="2026-08-31",
    )

    assert result["ok"] is True
    names = {Path(path).name for path in result["files"]}
    assert names == {
        "2026-08-31_GEO_内容_测试_正文.md",
        "2026-08-31_GEO_内容_测试_发布配置单.md",
        "2026-08-31_GEO_内容_测试_评分卡.md",
    }


def test_save_deliverables_rejects_date_path_traversal(tmp_path):
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=tmp_path)
    outside_files = list(tmp_path.parent.glob("malicious_escape_date_*.md"))

    try:
        result = service.save_deliverables(
            topic="测试主题",
            article="# 正文",
            publish_config="# 发布配置",
            scorecard="# 评分卡",
            date_str="../malicious_escape_date",
        )

        assert result["ok"] is False
        assert list(tmp_path.parent.glob("malicious_escape_date_*.md")) == outside_files
    finally:
        for path in tmp_path.parent.glob("malicious_escape_date_*.md"):
            if path not in outside_files:
                path.unlink()


def test_quality_check_flags_unsourced_precise_claims(tmp_path):
    service = GeoContentService(workspace_dir=tmp_path, knowledge_dir=tmp_path)

    result = service.quality_check(
        article="张总用了 3 天提升 42.7% 转化率，并获得行业第一认证。",
        source_notes="",
    )

    assert result["ok"] is True
    assert result["passed"] is False
    assert "unsourced_precise_number" in result["risk_codes"]
    assert "unsourced_named_case" in result["risk_codes"]


@pytest.mark.asyncio
async def test_tool_rejects_user_sample_or_weight_update(tmp_path):
    tool = GeoContentTool(workspace_dir=str(tmp_path))

    result = await tool.execute(action="update_weights")

    assert result.error
    assert "仅面向开发者" in result.error or "不支持" in result.error
