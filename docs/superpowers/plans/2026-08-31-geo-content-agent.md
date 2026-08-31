# GEO Content Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `geo_content` Web Agent that guides users through GEO content production and writes the final article, publish config, and scorecard files.

**Architecture:** Implement a hybrid `GeoContent` Agent plus a deterministic `GeoContentTool` service. The Agent handles conversation and writing decisions; the tool/service owns knowledge lookup, workspace-scoped state, input gap analysis, deliverable writes, and hard quality checks.

**Tech Stack:** Python 3.12 / pydantic / pytest / Vue3 + Vite / existing OpenManus ToolCallAgent, ToolCollection, AskHuman, WebSocket agent runner, and sandbox workspace.

**Spec:** `docs/superpowers/specs/2026-08-31-geo-content-agent-design.md`

## Global Constraints

- Python interpreter is fixed: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe`; do not use `python` or `python3`.
- Plans, progress, review, and logic explanations use Chinese.
- Code comments use simplified Chinese; code identifiers stay English.
- Keep edits scoped to GEO Agent integration and preserve unrelated dirty worktree changes.
- Do not expose sample-library, benchmark, or scoring-weight updates to ordinary users.
- `geo_content` sandbox network stays disabled in v1; URL inputs should ask users to paste or upload article text.
- GEO knowledge assets must live under the repository and must not depend on `C:\Users\hyh\.agents\skills\geo-content-sop\...` at runtime.
- TDD is required for code changes: write a failing test, run it, implement the smallest passing code, then verify.

---

## File Structure

- Create `app/knowledge/geo_content/*.md`: repository-owned read-only copies of GEO SOP reference files.
- Create `app/tool/geo_content/service.py`: deterministic helper functions for knowledge lookup, workspace path safety, state persistence, input gap analysis, quality checks, and deliverable writes.
- Create `app/tool/geo_content/geo_content.py`: `BaseTool` wrapper exposing the service to the Agent through action-based JSON parameters.
- Create `app/tool/geo_content/__init__.py`: package export for `GeoContentTool`.
- Create `app/prompt/geo_content.py`: `SYSTEM_PROMPT` and `NEXT_STEP_PROMPT`.
- Create `app/agent/geo_content.py`: `GeoContent` Agent class with sandbox propagation.
- Modify `app/web/agent_runner.py`: import `GeoContent`, add `ObservableGeoContent`, factory branch, and return type.
- Modify `app/web/chat/models.py`: add `"geo_content"` to `AGENT_TYPES`.
- Modify `app/web/chat/schemas.py`: update schema description.
- Modify `web_ui/src/components/NewChatDialog.vue`: add GEO option.
- Modify the upload accept location if present after inspection: allow `.txt`, `.md`, `.html` for reference article uploads.
- Create `tests/tool/test_geo_content.py`: service/tool unit tests.
- Create or modify `tests/web/test_agent_runner.py`: factory creation test for `geo_content`.
- Modify `tests/web/test_chat_models.py` or create a focused model test if needed: `AGENT_TYPES` includes `geo_content`.

---

### Task 1: Copy GEO Knowledge Assets Into The Repository

**Files:**
- Create: `app/knowledge/geo_content/knowledge-geo.md`
- Create: `app/knowledge/geo_content/benchmark-data.md`
- Create: `app/knowledge/geo_content/data-collection-fields.md`
- Create: `app/knowledge/geo_content/dimension-channel-matrix.md`
- Create: `app/knowledge/geo_content/section-templates.md`
- Create: `app/knowledge/geo_content/style-analysis.md`
- Create: `app/knowledge/geo_content/quality-checklist.md`
- Create: `app/knowledge/geo_content/scoring-rubric.md`
- Create: `app/knowledge/geo_content/deliverable-spec.md`

**Interfaces:**
- Consumes: `C:\Users\hyh\.agents\skills\geo-content-sop\references\*.md` as source material during development only.
- Produces: repository knowledge files read by `GeoContentService.load_knowledge(topic: str) -> dict[str, object]`.

- [ ] **Step 1: Verify source reference files exist**

Run:

```powershell
Get-ChildItem -LiteralPath C:\Users\hyh\.agents\skills\geo-content-sop\references -Filter *.md | Select-Object -ExpandProperty Name
```

Expected: output includes all nine files listed above.

- [ ] **Step 2: Copy reference files into `app/knowledge/geo_content`**

Use `Copy-Item` to copy the exact nine files. Do not copy sample annotation files or global sample update scripts.

Run:

```powershell
New-Item -ItemType Directory -Path app\knowledge\geo_content -Force
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\knowledge-geo.md app\knowledge\geo_content\knowledge-geo.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\benchmark-data.md app\knowledge\geo_content\benchmark-data.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\data-collection-fields.md app\knowledge\geo_content\data-collection-fields.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\dimension-channel-matrix.md app\knowledge\geo_content\dimension-channel-matrix.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\section-templates.md app\knowledge\geo_content\section-templates.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\style-analysis.md app\knowledge\geo_content\style-analysis.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\quality-checklist.md app\knowledge\geo_content\quality-checklist.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\scoring-rubric.md app\knowledge\geo_content\scoring-rubric.md
Copy-Item C:\Users\hyh\.agents\skills\geo-content-sop\references\deliverable-spec.md app\knowledge\geo_content\deliverable-spec.md
```

- [ ] **Step 3: Verify only expected files were copied**

Run:

```powershell
Get-ChildItem -LiteralPath app\knowledge\geo_content -File | Select-Object -ExpandProperty Name
```

Expected: exactly the nine reference files above.

---

### Task 2: Build The GEO Service And Tool With TDD

**Files:**
- Create: `app/tool/geo_content/service.py`
- Create: `app/tool/geo_content/geo_content.py`
- Create: `app/tool/geo_content/__init__.py`
- Test: `tests/tool/test_geo_content.py`

**Interfaces:**
- Produces: `GeoContentService(workspace_dir: str | Path, knowledge_dir: str | Path | None = None)`
- Produces: `GeoContentService.load_knowledge(topic: str) -> dict[str, object]`
- Produces: `GeoContentService.load_state() -> dict[str, object]`
- Produces: `GeoContentService.save_state(content: str) -> dict[str, object]`
- Produces: `GeoContentService.analyze_inputs(materials: dict[str, str]) -> dict[str, object]`
- Produces: `GeoContentService.quality_check(article: str, source_notes: str = "") -> dict[str, object]`
- Produces: `GeoContentService.save_deliverables(topic: str, article: str, publish_config: str, scorecard: str, date_str: str | None = None) -> dict[str, object]`
- Produces: `GeoContentTool.execute(action: str, **kwargs) -> ToolResult`

- [ ] **Step 1: Write failing tests for knowledge lookup and workspace state**

Create `tests/tool/test_geo_content.py` with these tests:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\tool\test_geo_content.py -v
```

Expected: import failure for `app.tool.geo_content` because implementation does not exist yet.

- [ ] **Step 3: Implement service knowledge and state methods**

Create `app/tool/geo_content/service.py`:

```python
"""GEO 内容生产工具的确定性服务层。"""

import re
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "geo_content"

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
        self.knowledge_dir = Path(knowledge_dir).resolve() if knowledge_dir else DEFAULT_KNOWLEDGE_DIR

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
            return {"ok": True, "exists": False, "path": str(self.state_path), "content": ""}
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
```

Create `app/tool/geo_content/__init__.py`:

```python
"""GEO 内容生产工具。"""

from app.tool.geo_content.geo_content import GeoContentTool


__all__ = ["GeoContentTool"]
```

Create a minimal `app/tool/geo_content/geo_content.py` so imports resolve:

```python
"""GEO 内容生产 Agent 专用工具。"""

from app.tool.base import BaseTool, ToolResult
from app.tool.geo_content.service import GeoContentService


class GeoContentTool(BaseTool):
    """暴露 GEO SOP 的确定性动作。"""

    name: str = "geo_content"
    description: str = "读取 GEO 知识、维护工作状态、检查素材缺口并保存交付文件"
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
        },
        "required": ["action"],
    }
    workspace_dir: str = "/workspace"

    async def execute(self, action: str, **kwargs) -> ToolResult:
        service = GeoContentService(self.workspace_dir)
        if action == "load_state":
            return ToolResult(output=service.load_state())
        if action == "save_state":
            return ToolResult(output=service.save_state(kwargs.get("content", "")))
        if action == "load_knowledge":
            return ToolResult(output=service.load_knowledge(kwargs.get("topic", "")))
        return ToolResult(error=f"不支持的 GEO action: {action}")
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\tool\test_geo_content.py -v
```

Expected: the first three tests pass.

- [ ] **Step 5: Add failing tests for input analysis, deliverables, quality checks, and forbidden actions**

Append to `tests/tool/test_geo_content.py`:

```python
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
```

- [ ] **Step 6: Run tests and verify new failures**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\tool\test_geo_content.py -v
```

Expected: failures for missing `analyze_inputs`, `save_deliverables`, and `quality_check`.

- [ ] **Step 7: Implement analysis, quality, and deliverable methods**

Add to `GeoContentService`:

```python
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
        has_sources = bool(source_notes.strip())
        if not has_sources and re.search(r"\d+(?:\.\d+)?\s*(?:%|天|小时|倍|万|亿)", article):
            risk_codes.append("unsourced_precise_number")
        if not has_sources and re.search(r"[\u4e00-\u9fa5]{1,4}(?:总|经理|博士|教授|专家)", article):
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
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        safe_topic = _sanitize_topic(topic)
        day = date_str or date.today().isoformat()
        files = [
            (self.workspace_dir / f"{day}_{safe_topic}_正文.md", article),
            (self.workspace_dir / f"{day}_{safe_topic}_发布配置单.md", publish_config),
            (self.workspace_dir / f"{day}_{safe_topic}_评分卡.md", scorecard),
        ]
        for path, content in files:
            path.write_text(content, encoding="utf-8")
        return {"ok": True, "files": [str(path) for path, _ in files]}


def _sanitize_topic(topic: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*\\s]+', "_", topic.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "geo_content"
```

- [ ] **Step 8: Expand `GeoContentTool` schema and action dispatch**

Update `parameters` in `app/tool/geo_content/geo_content.py` to include:

```python
"action": {
    "type": "string",
    "enum": [
        "load_knowledge",
        "load_state",
        "save_state",
        "analyze_inputs",
        "quality_check",
        "save_deliverables",
    ],
},
"topic": {"type": "string"},
"content": {"type": "string"},
"materials": {"type": "object"},
"article": {"type": "string"},
"source_notes": {"type": "string"},
"publish_config": {"type": "string"},
"scorecard": {"type": "string"},
"date": {"type": "string"},
```

Update dispatch:

```python
if action == "analyze_inputs":
    return ToolResult(output=service.analyze_inputs(kwargs.get("materials") or {}))
if action == "quality_check":
    return ToolResult(
        output=service.quality_check(
            article=kwargs.get("article", ""),
            source_notes=kwargs.get("source_notes", ""),
        )
    )
if action == "save_deliverables":
    return ToolResult(
        output=service.save_deliverables(
            topic=kwargs.get("topic", ""),
            article=kwargs.get("article", ""),
            publish_config=kwargs.get("publish_config", ""),
            scorecard=kwargs.get("scorecard", ""),
            date_str=kwargs.get("date"),
        )
    )
return ToolResult(error=f"不支持的 GEO action: {action}。样本库、benchmark 和评分权重更新仅面向开发者维护。")
```

- [ ] **Step 9: Run tool tests**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\tool\test_geo_content.py -v
```

Expected: all GEO tool tests pass.

---

### Task 3: Add GeoContent Agent And Prompt

**Files:**
- Create: `app/prompt/geo_content.py`
- Create: `app/agent/geo_content.py`
- Test: `tests/test_geo_content_agent.py`

**Interfaces:**
- Consumes: `GeoContentTool(workspace_dir: str = "/workspace")`
- Produces: `GeoContent.set_sandbox(sandbox: object, workspace: str = "/workspace", host_workspace: str = "") -> None`
- Produces: `GeoContent.available_tools` containing `geo_content`, `python_execute`, `ask_human`, and `terminate`.

- [ ] **Step 1: Write failing Agent tests**

Create `tests/test_geo_content_agent.py`:

```python
from app.agent.geo_content import GeoContent


def test_geo_content_agent_has_expected_tools():
    agent = GeoContent()

    assert agent.name == "geo_content"
    assert agent.available_tools.get_tool("geo_content") is not None
    assert agent.available_tools.get_tool("ask_human") is not None
    assert agent.available_tools.get_tool("terminate") is not None


def test_geo_content_set_sandbox_updates_tool_workspace():
    agent = GeoContent()
    fake_sandbox = object()

    agent.set_sandbox(fake_sandbox, workspace="/workspace", host_workspace="C:/tmp/chat")

    tool = agent.available_tools.get_tool("geo_content")
    assert agent.sandbox is fake_sandbox
    assert tool.workspace_dir == "/workspace"
    assert "/workspace" in agent.system_prompt
```

- [ ] **Step 2: Run Agent tests and verify failure**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\test_geo_content_agent.py -v
```

Expected: import failure for `app.agent.geo_content`.

- [ ] **Step 3: Create prompt**

Create `app/prompt/geo_content.py`:

```python
"""GEO 内容生产 Agent 提示词。"""

SYSTEM_PROMPT = """
你是 GEO 内容生产智能体，负责按 GEO SOP 帮用户生成正文、发布配置单和评分卡。

工作目录是：{directory}

必须遵守：
1. 先调用 geo_content(action="load_state") 恢复 _working-data.md；没有状态时创建新的工作记录。
2. 按 A-F 收集素材：business、authority、experience、intent_words、sources、faq。
3. 用户可以粘贴或上传参考文章，你只能分析结构、节奏、表达方式和板块组织，不得复制原文内容。
4. 不允许普通用户更新样本库、benchmark 或评分权重；遇到这类要求必须拒绝。
5. 首版不联网抓取 URL；用户给 URL 时，请要求其粘贴正文或上传文章文件。
6. 没有来源时，不得编造精确数字、人物故事、专家背书、获奖资质或行业排名。
7. 大纲需要用户确认后再写正文。
8. 写完正文后调用 geo_content(action="quality_check") 做硬性质量检查。
9. 通过检查后调用 geo_content(action="save_deliverables") 保存正文、发布配置单、评分卡三份文件。
10. 文件保存完成后，向用户说明文件名并调用 terminate。
"""

NEXT_STEP_PROMPT = """
请判断当前 GEO SOP 阶段并采取下一步：
- 若未加载状态，先加载状态。
- 若 A-F 素材不足，调用 geo_content(action="analyze_inputs") 并用 ask_human 追问缺口。
- 若需要用户确认大纲，先等待确认。
- 若已具备素材，生成正文、发布配置单和评分卡。
- 若质量检查失败，基于失败项补充追问或降级表达。
- 若三份交付文件已保存，报告结果并结束。
"""
```

- [ ] **Step 4: Create Agent class**

Create `app/agent/geo_content.py` following `WechatPublish` style:

```python
"""GEO 内容生产智能体。"""

from typing import Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.logger import logger
from app.prompt.geo_content import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ask_human import AskHuman
from app.tool.chart_visualization.python_execute import NormalPythonExecute
from app.tool.geo_content import GeoContentTool


class GeoContent(ToolCallAgent):
    """GEO 内容生产智能体：生成正文、发布配置单和评分卡。"""

    name: str = "geo_content"
    description: str = "GEO 内容生产智能体，可生成正文、发布配置单和评分卡"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 30

    sandbox: Optional[object] = None
    _sandbox_workspace: str = ""

    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            GeoContentTool(),
            NormalPythonExecute(),
            AskHuman(),
            Terminate(),
        )
    )

    def set_sandbox(
        self, sandbox: object, workspace: str = "/workspace", host_workspace: str = ""
    ) -> None:
        """注入 Sandbox 并同步到所有执行类工具。"""
        self.sandbox = sandbox
        self._sandbox_workspace = workspace
        self.system_prompt = SYSTEM_PROMPT.format(directory=workspace)
        for tool in self.available_tools:
            if hasattr(tool, "sandbox"):
                tool.sandbox = sandbox
            if hasattr(tool, "workspace_dir") and workspace:
                tool.workspace_dir = workspace
            if hasattr(tool, "host_workspace_dir") and host_workspace:
                tool.host_workspace_dir = host_workspace
            if hasattr(tool, "parameters") and isinstance(tool.parameters, dict):
                code_desc = (
                    tool.parameters.get("properties", {})
                    .get("code", {})
                    .get("description", "")
                )
                if code_desc and str(config.workspace_root) in code_desc:
                    tool.parameters["properties"]["code"][
                        "description"
                    ] = code_desc.replace(str(config.workspace_root), workspace)
                    logger.debug(f"ToolDesc 已更新: {tool.name} -> {workspace}")
```

- [ ] **Step 5: Run Agent tests**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\test_geo_content_agent.py -v
```

Expected: both tests pass.

---

### Task 4: Register Agent In Web Backend

**Files:**
- Modify: `app/web/chat/models.py`
- Modify: `app/web/chat/schemas.py`
- Modify: `app/web/agent_runner.py`
- Test: `tests/web/test_agent_runner.py`
- Test: `tests/web/test_chat_models.py` or a new lightweight test file

**Interfaces:**
- Consumes: `GeoContent`
- Produces: `create_observable_agent("geo_content", queue, sandbox, host_workspace) -> ObservableGeoContent`

- [ ] **Step 1: Write failing backend registration tests**

Create `tests/web/test_agent_runner.py` if it does not exist:

```python
import asyncio

import pytest

from app.web.agent_runner import create_observable_agent
from app.web.chat.models import AGENT_TYPES


def test_agent_types_include_geo_content():
    assert "geo_content" in AGENT_TYPES


@pytest.mark.asyncio
async def test_create_observable_geo_content_agent():
    queue = asyncio.Queue()

    agent = await create_observable_agent("geo_content", queue)

    assert agent.name == "geo_content"
    assert agent.event_queue is queue
    assert agent.available_tools.get_tool("geo_content") is not None
```

- [ ] **Step 2: Run backend registration tests and verify failure**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\web\test_agent_runner.py -v
```

Expected: failure because `geo_content` is not registered.

- [ ] **Step 3: Update chat model and schema**

In `app/web/chat/models.py`:

```python
AGENT_TYPES = {"general", "data_analysis", "quick_query", "wechat_publish", "geo_content"}
```

In `app/web/chat/schemas.py`, update the description string to include `geo_content`.

- [ ] **Step 4: Update agent runner**

In `app/web/agent_runner.py`:

Add import:

```python
from app.agent.geo_content import GeoContent
```

Add observable class. Copy the same event methods from `ObservableWechatPublish`, only changing the base class and docstring:

```python
class ObservableGeoContent(GeoContent):
    """GeoContent 的事件注入子类。"""

    event_queue: asyncio.Queue | None = None
```

If keeping duplicated methods, copy `step`, `think`, `execute_tool`, and `run` exactly as existing observable classes do. If extracting a mixin, keep the refactor limited to observable classes and run all agent runner tests.

Update return annotation:

```python
) -> Manus | DataAnalysis | QuickQuery | WechatPublish | GeoContent:
```

Add factory branch:

```python
elif agent_type == "geo_content":
    agent = ObservableGeoContent()
```

- [ ] **Step 5: Run backend registration tests**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\web\test_agent_runner.py -v
```

Expected: tests pass.

---

### Task 5: Add Frontend Entry And Upload Types

**Files:**
- Modify: `web_ui/src/components/NewChatDialog.vue`
- Modify: the upload accept component discovered by `rg -n "accept=|\\.csv|\\.xlsx|\\.txt|upload" web_ui/src`

**Interfaces:**
- Consumes: backend `geo_content` agent type.
- Produces: users can choose `geo_content` when creating a chat.

- [ ] **Step 1: Locate upload accept list**

Run:

```powershell
rg -n "accept=|\\.csv|\\.xlsx|\\.txt|upload" web_ui/src
```

Expected: identify the component that restricts uploaded file extensions.

- [ ] **Step 2: Add GEO option to new chat dialog**

In `web_ui/src/components/NewChatDialog.vue`, add:

```vue
<option value="geo_content">🧭 GEO 内容生产</option>
```

Place it near other business Agent options.

- [ ] **Step 3: Add text reference upload extensions**

If the upload accept list exists, ensure it includes:

```text
.txt,.md,.html
```

Do not add `.docx` unless a parser is implemented in this same change.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
npm --prefix web_ui run build
```

Expected: build succeeds.

---

### Task 6: Final Verification And Diff Review

**Files:**
- Verify all files touched by Tasks 1-5.

**Interfaces:**
- Consumes: completed implementation.
- Produces: validated `geo_content` Agent integration.

- [ ] **Step 1: Run focused Python tests**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\tool\test_geo_content.py tests\test_geo_content_agent.py tests\web\test_agent_runner.py -v
```

Expected: all pass.

- [ ] **Step 2: Run existing adjacent tests**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\test_quick_query_set_sandbox.py tests\tool\test_wechat_publish.py tests\web\test_chat_models.py -v
```

Expected: all pass, unless external database setup blocks `tests\web\test_chat_models.py`; if blocked, report the exact environment error.

- [ ] **Step 3: Run pre-commit on changed files**

Run:

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pre_commit run --files app\knowledge\geo_content\knowledge-geo.md app\knowledge\geo_content\benchmark-data.md app\knowledge\geo_content\data-collection-fields.md app\knowledge\geo_content\dimension-channel-matrix.md app\knowledge\geo_content\section-templates.md app\knowledge\geo_content\style-analysis.md app\knowledge\geo_content\quality-checklist.md app\knowledge\geo_content\scoring-rubric.md app\knowledge\geo_content\deliverable-spec.md app\tool\geo_content\service.py app\tool\geo_content\geo_content.py app\tool\geo_content\__init__.py app\prompt\geo_content.py app\agent\geo_content.py app\web\chat\models.py app\web\chat\schemas.py app\web\agent_runner.py tests\tool\test_geo_content.py tests\test_geo_content_agent.py tests\web\test_agent_runner.py web_ui\src\components\NewChatDialog.vue docs\superpowers\specs\2026-08-31-geo-content-agent-design.md docs\superpowers\plans\2026-08-31-geo-content-agent.md
```

Expected: all hooks pass. If hooks modify files, review diff and rerun the command.

- [ ] **Step 4: Review final diff**

Run:

```powershell
git diff -- app\knowledge\geo_content app\tool\geo_content app\prompt\geo_content.py app\agent\geo_content.py app\web\chat\models.py app\web\chat\schemas.py app\web\agent_runner.py tests\tool\test_geo_content.py tests\test_geo_content_agent.py tests\web\test_agent_runner.py web_ui\src\components\NewChatDialog.vue docs\superpowers\specs\2026-08-31-geo-content-agent-design.md docs\superpowers\plans\2026-08-31-geo-content-agent.md
```

Expected: diff contains only GEO Agent implementation, tests, knowledge assets, design, and implementation plan.

- [ ] **Step 5: Confirm dirty worktree separation**

Run:

```powershell
git status --short
```

Expected: unrelated pre-existing changes such as `.codegraph/daemon.pid`, `config/.gitignore`, `messages.xlsx`, removed `skills/tablestore/*`, `.claude/`, `app/agent/.claude/`, `opencode.json`, and `test_2.py` remain untouched unless the user explicitly changes scope.

---

## Self-Review

- Spec coverage: covered Agent type, Web registration, chat-style flow, state file, three deliverables, read-only knowledge assets, no sample/weight update for ordinary users, no URL network fetch, and verification.
- Placeholder scan: no placeholder or undefined future work appears in executable steps.
- Type consistency: `GeoContentService`, `GeoContentTool`, `GeoContent`, `geo_content`, and action names are consistent across tasks.
- Risk note: the service-level `quality_check` is a hard guardrail, not a full semantic score. The Agent prompt still performs rubric-based review using copied GEO knowledge.
