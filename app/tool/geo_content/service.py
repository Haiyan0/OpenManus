"""GEO 内容生产工具的确定性服务层。"""

import re
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_KNOWLEDGE_DIR = (
    Path(__file__).resolve().parents[2] / "knowledge" / "geo_content"
)

KNOWLEDGE_FILES = {
    "knowledge_geo": "knowledge-geo.md",
    "benchmark_data": "benchmark-data.md",
    "data_collection_fields": "data-collection-fields.md",
    "dimension_channel_matrix": "dimension-channel-matrix.md",
    "section_templates": "section-templates.md",
    "style_analysis": "style-analysis.md",
    "quality_checklist": "quality-checklist.md",
    "scoring_rubric": "scoring-rubric.md",
    "deliverable_spec": "deliverable-spec.md",
}

REQUIRED_MATERIAL_FIELDS = {
    "business": "业务/产品/服务说明",
    "authority": "权威来源、资质、真实数据或可验证背书",
    "experience": "真实经验、案例、流程或使用细节",
    "intent_words": "目标用户意图词或搜索问题",
    "sources": "可核验来源材料",
    "faq": "用户常见问题与回答",
}


class GeoContentService:
    """处理 GEO 状态、知识资产和交付文件。"""

    def __init__(
        self,
        workspace_dir: str | Path,
        knowledge_dir: str | Path | None = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.knowledge_dir = (
            Path(knowledge_dir).resolve() if knowledge_dir else DEFAULT_KNOWLEDGE_DIR
        )

    @property
    def state_path(self) -> Path:
        return self.workspace_dir / "_working-data.md"

    def load_knowledge(self, topic: str) -> dict[str, Any]:
        if topic not in KNOWLEDGE_FILES:
            return {"ok": False, "error": f"不支持的 GEO 知识主题: {topic}"}
        path = self.knowledge_dir / KNOWLEDGE_FILES[topic]
        if not path.exists():
            return {"ok": False, "error": f"GEO 知识资产缺失: {path.name}"}
        return {
            "ok": True,
            "topic": topic,
            "path": str(path),
            "content": path.read_text(encoding="utf-8"),
        }

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "ok": True,
                "exists": False,
                "path": str(self.state_path),
                "content": "",
            }
        return {
            "ok": True,
            "exists": True,
            "path": str(self.state_path),
            "content": self.state_path.read_text(encoding="utf-8"),
        }

    def save_state(self, content: str) -> dict[str, Any]:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(self.state_path)}

    def analyze_inputs(self, materials: dict[str, str]) -> dict[str, Any]:
        missing = [
            field
            for field in REQUIRED_MATERIAL_FIELDS
            if not str(materials.get(field, "")).strip()
        ]
        return {
            "ok": True,
            "complete": not missing,
            "missing_fields": missing,
            "missing_labels": [REQUIRED_MATERIAL_FIELDS[field] for field in missing],
        }

    def quality_check(self, article: str, source_notes: str = "") -> dict[str, Any]:
        risk_codes: list[str] = []
        if not article.strip():
            risk_codes.append("empty_article")
        has_sources = _has_verifiable_source_notes(source_notes)
        if not has_sources and re.search(r"\d+(?:\.\d+)?\s*(?:%|天|小时|倍|万|亿)", article):
            risk_codes.append("unsourced_precise_number")
        if not has_sources and re.search(
            r"[\u4e00-\u9fa5]{1,4}(?:总|经理|博士|教授|专家)", article
        ):
            risk_codes.append("unsourced_named_case")
        if not has_sources and re.search(r"(?:第一|领先|权威认证|官方认证|获奖|专利)", article):
            risk_codes.append("unsourced_authority_claim")
        return {
            "ok": True,
            "passed": not risk_codes,
            "risk_codes": risk_codes,
        }

    def save_deliverables(
        self,
        topic: str,
        article: str,
        publish_config: str,
        scorecard: str,
        date_str: str | None = None,
    ) -> dict[str, Any]:
        contents = {
            "article": article,
            "publish_config": publish_config,
            "scorecard": scorecard,
        }
        missing_fields = [
            name for name, content in contents.items() if not content.strip()
        ]
        if missing_fields:
            return {
                "ok": False,
                "error": "正文、发布配置单和评分卡均不能为空",
                "missing_fields": missing_fields,
            }
        safe_topic = _sanitize_topic(topic)
        day = _validate_date(date_str)
        if day is None:
            return {"ok": False, "error": "date 必须是有效的 YYYY-MM-DD 日期"}
        files = [
            (self.workspace_dir / f"{day}_{safe_topic}_正文.md", article),
            (self.workspace_dir / f"{day}_{safe_topic}_发布配置单.md", publish_config),
            (self.workspace_dir / f"{day}_{safe_topic}_评分卡.md", scorecard),
        ]
        if any(not _is_inside_workspace(path, self.workspace_dir) for path, _ in files):
            return {"ok": False, "error": "GEO 交付文件路径必须位于工作目录内"}
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        for path, content in files:
            path.write_text(content, encoding="utf-8")
        return {"ok": True, "files": [str(path) for path, _ in files]}


def _sanitize_topic(topic: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", topic.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "geo_content"


def _has_verifiable_source_notes(source_notes: str) -> bool:
    notes = source_notes.strip()
    if not notes:
        return False
    source_patterns = (
        r"https?://\S+",
        r"\[[^\]\r\n]+\]\([^)]+\)",
        r"(?:^|\s)(?:[A-Za-z]:[\\/]|\.{0,2}[\\/])?"
        r"[^\s]+\.(?:md|txt|html?|pdf|docx?|csv|xlsx?)(?:$|\s)",
        r"(?:\[\d+\]|【(?:来源|引用|参考)\d*】|" r"(?:来源|引用|参考文献|citation)\s*[:：])",
    )
    return any(re.search(pattern, notes, re.IGNORECASE) for pattern in source_patterns)


def _validate_date(date_str: str | None) -> str | None:
    if date_str is None:
        return date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        return None
    try:
        return date.fromisoformat(date_str).isoformat()
    except ValueError:
        return None


def _is_inside_workspace(path: Path, workspace_dir: Path) -> bool:
    try:
        path.resolve().relative_to(workspace_dir.resolve())
    except ValueError:
        return False
    return True
