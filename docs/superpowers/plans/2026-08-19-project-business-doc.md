# 按项目分档的业务数据说明文档 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 DataAnalysis / QuickQuery 智能体引入按项目分档的业务说明文档（markdown），通过 CompanyDataLookup 新增的 list_projects / get_doc action 按需读取，降低 SQL 与字段口径错误率。

**Architecture:** 新增纯函数模块 `app/tool/project_docs.py`（list_projects / get_doc），CompanyDataLookup.execute 顶部分发这两个 action（与 local/mysql 数据模式无关）；文档存于项目根 `project_docs/企业/项目/*.md`；大文档沿用 output 摘要 + system 全文双通道；两个 agent 的 system prompt 流程插入"文档优先"步骤。

**Tech Stack:** Python 3.12（conda 环境 `C:\Users\hyh\anaconda3\envs\open_manus\python.exe`）、pytest（`asyncio_mode=auto`）、Pydantic v2、标准库 pathlib。

**Spec:** `docs/superpowers/specs/2026-08-19-project-business-doc-design.md`

## Global Constraints

- 匹配规则：企业/项目名**子串匹配、忽略大小写**；query 含 `/` 且目录存在 → 精确命中
- 双通道阈值：文档 ≤ 8000 字符（按 `len(str)` 计）全文走 output；> 8000 → 前 2000 字符摘要走 output，全文走 `ToolResult.system`
- 降级原则：project_docs 缺失 / 项目无文档 / 多命中 / 零命中均**不阻塞**，提示中引导 list_tables
- 文档编写约定（模板头部固化）：文档只描述表/字段/SQL 口径，**不包含任何文件路径**
- `parameters.required` 从 `["action", "query_or_sql"]` 放宽为 `["action"]`；`execute` 签名 `query_or_sql: str = ""`
- 只允许修改 spec §10 列出的文件
- 中文注释与提交信息、英文标识符；提交格式 `feat(tool): ...`（对齐仓库风格）
- 测试运行：`pytest <file> -v`（pytest.ini 已启用 asyncio_mode=auto，异步测试无需标记）

---

## 文件结构

| 文件 | 责任 |
|------|------|
| `app/tool/project_docs.py`（新增） | 项目业务文档检索纯函数模块：DOCS_DIR 常量、list_projects、get_doc、_match_project |
| `tests/tool/test_project_docs.py`（新增） | 上述模块的单元测试（tmp_path 注入 root）+ 资产检查 |
| `app/tool/company_data_lookup.py`（修改） | execute 分发新 action、docs_root 字段、description/parameters 更新 |
| `tests/tool/test_company_data_lookup.py`（修改） | 追加 execute 分发与 schema 测试（现有测试不动） |
| `app/prompt/quick_query.py`、`app/prompt/visualization.py`（修改） | 使用流程插入"文档优先"步骤 |
| `tests/test_project_doc_prompt.py`（新增） | prompt 引导语防回归测试 |
| `project_docs/TEMPLATE.md`、`project_docs/示例企业/示例项目/业务说明.md`（新增） | 文档模板与示例（静态资产） |

---

### Task 1: project_docs 模块骨架 + list_projects（TDD）

**Files:**
- Create: `app/tool/project_docs.py`
- Create: `tests/tool/test_project_docs.py`

**Interfaces:**
- Produces: `DOCS_DIR: str = "project_docs"`、`list_projects(query: str = "", root: Optional[Path] = None) -> ToolResult`、`_doc_root(root: Optional[Path]) -> Path`、`_subdirs(path: Path) -> list[Path]`（后两者供 Task 2 复用）

- [ ] **Step 1: 写失败测试**

创建 `tests/tool/test_project_docs.py`：

```python
"""project_docs 模块（项目业务文档检索）单元测试。"""
from pathlib import Path

import pytest

from app.tool.project_docs import DOCS_DIR, list_projects


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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/tool/test_project_docs.py -v`
Expected: FAIL（`ModuleNotFoundError: app.tool.project_docs`）

- [ ] **Step 3: 写最小实现**

创建 `app/tool/project_docs.py`（本任务只写 list_projects 部分）：

```python
"""项目业务文档检索模块。

从 project_docs/ 目录树（企业/项目 两级）按需读取业务说明文档，
供 CompanyDataLookup 的 list_projects / get_doc action 分发调用。

约束：只依赖标准库与 ToolResult；无状态纯函数；root 参数可注入（测试用 tmp_path）。
"""
from pathlib import Path
from typing import Optional

from app.config import PROJECT_ROOT
from app.tool.base import ToolResult

# 文档根目录名（相对项目根；对齐 company_data_lookup.DATA_DIR 的常量先例）
DOCS_DIR = "project_docs"

# output 通道全文上限：超出时摘要走 output、全文走 system（对齐 list_tables 双通道惯例）
_DOC_OUTPUT_MAX = 8000
# 大文档时 output 通道摘要长度
_DOC_SUMMARY_MAX = 2000


def _doc_root(root: Optional[Path]) -> Path:
    """解析文档根目录：root 显式传入时用之（测试注入），否则用项目根下 DOCS_DIR。"""
    return Path(root) if root is not None else PROJECT_ROOT / DOCS_DIR


def _subdirs(path: Path) -> list[Path]:
    """目录下按名称排序的子目录列表。"""
    return sorted([p for p in path.iterdir() if p.is_dir()], key=lambda p: p.name)


def list_projects(query: str = "", root: Optional[Path] = None) -> ToolResult:
    """列出 project_docs 下所有企业/项目及文档状态。

    Args:
        query: 可选企业名过滤（子串、忽略大小写），空串列全部
        root: 文档根目录（默认 PROJECT_ROOT / DOCS_DIR）
    """
    doc_root = _doc_root(root)
    if not doc_root.is_dir():
        return ToolResult(
            error=(
                f"未配置项目业务文档（目录不存在: {doc_root}）。"
                f"可直接使用 list_tables 查询数据库表结构。"
            )
        )
    companies = _subdirs(doc_root)
    if not companies:
        return ToolResult(
            error=f"项目文档目录 '{doc_root}' 为空，可直接使用 list_tables 查询。"
        )
    q = (query or "").lower()
    lines = ["📁 项目业务文档清单:"]
    total = 0
    for comp in companies:
        if q and q not in comp.name.lower():
            continue
        projects = _subdirs(comp)
        lines.append(f"企业「{comp.name}」:")
        for proj in projects:
            total += 1
            mds = sorted(proj.glob("*.md"), key=lambda p: p.name)
            if mds:
                lines.append(
                    f"  - 项目「{proj.name}」文档: {', '.join(p.name for p in mds)}"
                )
            else:
                lines.append(f"  - 项目「{proj.name}」[无文档]")
    if total == 0:
        return ToolResult(
            error=f"未找到匹配 '{query}' 的企业。可用企业：\n"
            + "\n".join(f"  - {c.name}" for c in companies)
        )
    return ToolResult(output="\n".join(lines))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/tool/test_project_docs.py -v`
Expected: PASS（4 个用例全绿）

- [ ] **Step 5: 提交**

```bash
git add app/tool/project_docs.py tests/tool/test_project_docs.py
git commit -m "feat(tool): project_docs 模块 list_projects 列企业/项目文档清单"
```

---

### Task 2: get_doc 匹配与读取（TDD）

**Files:**
- Modify: `app/tool/project_docs.py`
- Modify: `tests/tool/test_project_docs.py`（追加测试类）

**Interfaces:**
- Consumes: Task 1 的 `_doc_root`、`_subdirs`、`DOCS_DIR`
- Produces: `get_doc(query: str, root: Optional[Path] = None) -> ToolResult`、`_match_project(doc_root: Path, query: str) -> tuple[str, Path | str]`（Task 3 复用 get_doc）

- [ ] **Step 1: 写失败测试**

在 `tests/tool/test_project_docs.py` 顶部 import 行改为 `from app.tool.project_docs import DOCS_DIR, get_doc, list_projects`，文件末尾追加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/tool/test_project_docs.py -v`
Expected: FAIL（`ImportError: cannot import name 'get_doc'`）

- [ ] **Step 3: 写最小实现**

在 `app/tool/project_docs.py` 末尾追加（list_projects 之后）：

```python
def _match_project(doc_root: Path, query: str):
    """按 query 匹配项目目录。

    匹配规则（与 company_data_lookup local 模式同构）：
    1. query 含 / 且对应目录存在 → 精确命中
    2. 企业名 in query（子串、忽略大小写）→ 企业内再项目名 in query：
       唯一 → 命中；多个 → 候选清单；零个 → 该企业可用项目
    3. 未命中企业名 → 全树项目名 in query：
       唯一 → 命中；多个 → 候选清单；零个 → 全量可用清单

    Returns:
        (status, data)：status 为 "hit" 时 data 是 Path；
        为 "ambiguous"/"none" 时 data 是提示文本
    """
    companies = _subdirs(doc_root)
    q = query.strip().lower()
    # 1. 精确路径：query 本身是 企业/项目 目录
    direct = doc_root / query.strip().replace("\\", "/")
    if direct.is_dir():
        return "hit", direct
    # 2. 企业名 in query
    for comp in companies:
        if comp.name.lower() in q:
            projects = _subdirs(comp)
            hits = [p for p in projects if p.name.lower() in q]
            if len(hits) == 1:
                return "hit", hits[0]
            if len(hits) > 1:
                return "ambiguous", "\n".join(
                    f"  - {comp.name}/{p.name}" for p in hits
                )
            return "none", (
                f"企业「{comp.name}」匹配但未指定项目，该企业可用项目：\n"
                + "\n".join(f"  - {p.name}" for p in projects)
                + "\n请用「企业名/项目名」或项目名精确重试。"
            )
    # 3. 全树项目名 in query
    hits = [(c, p) for c in companies for p in _subdirs(c) if p.name.lower() in q]
    if len(hits) == 1:
        return "hit", hits[0][1]
    if len(hits) > 1:
        return "ambiguous", "\n".join(f"  - {c.name}/{p.name}" for c, p in hits)
    available = "\n".join(
        f"  - {c.name}/{p.name}" for c in companies for p in _subdirs(c)
    )
    return "none", f"未找到匹配 '{query}' 的项目。可用清单：\n{available}"


def get_doc(query: str, root: Optional[Path] = None) -> ToolResult:
    """读取指定项目的业务文档（企业/项目 目录下所有 .md 按文件名拼接）。

    Args:
        query: 企业名/项目名自由文本（如 "甲企业/项目A" 或 "项目A"）
        root: 文档根目录（默认 PROJECT_ROOT / DOCS_DIR）
    """
    doc_root = _doc_root(root)
    if not doc_root.is_dir():
        return ToolResult(
            error=(
                f"未配置项目业务文档（目录不存在: {doc_root}）。"
                f"可直接使用 list_tables 查询数据库表结构。"
            )
        )
    if not query or not query.strip():
        return ToolResult(
            error="get_doc 需要企业名/项目名，可先用 list_projects 查看可用项目。"
        )
    status, data = _match_project(doc_root, query)
    if status == "ambiguous":
        return ToolResult(error=f"匹配到多个项目，请精确指定：\n{data}")
    if status == "none":
        return ToolResult(error=data)
    proj_dir: Path = data
    mds = sorted(proj_dir.glob("*.md"), key=lambda p: p.name)
    if not mds:
        return ToolResult(
            error=(
                f"项目「{proj_dir.parent.name}/{proj_dir.name}」尚未维护业务文档。"
                f"请改用 list_tables 了解表结构。"
            )
        )
    parts = []
    for f in mds:
        try:
            parts.append(f.read_text(encoding="utf-8"))
        except Exception as e:
            return ToolResult(error=f"读取文档失败: {f} → {e}")
    full = "\n\n".join(parts)
    source = f"{proj_dir.parent.name}/{proj_dir.name}"
    return ToolResult(
        output=(
            f"已读取项目业务文档：{source}（{len(mds)} 个文件，共 {len(full)} 字符）\n"
            f"{'─' * 60}\n{full}"
        )
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/tool/test_project_docs.py -v`
Expected: PASS（全部用例）

- [ ] **Step 5: 提交**

```bash
git add app/tool/project_docs.py tests/tool/test_project_docs.py
git commit -m "feat(tool): get_doc 按企业/项目名匹配读取业务文档"
```

---

### Task 3: 大文档双通道返回（TDD）

**Files:**
- Modify: `app/tool/project_docs.py`（get_doc 尾部加截断逻辑）
- Modify: `tests/tool/test_project_docs.py`（追加测试类）

**Interfaces:**
- Consumes: Task 2 的 `get_doc`
- Produces: 无新接口（行为增强：>8000 字符时 output 摘要 + system 全文）

- [ ] **Step 1: 写失败测试**

`tests/tool/test_project_docs.py` 末尾追加：

```python
class TestGetDocLargeDoc:
    def _make_large_doc(self, docs_tree: Path) -> None:
        """丁企业/项目D：单文档约 18000 字符。"""
        (docs_tree / "丁企业" / "项目D").mkdir(parents=True)
        doc = docs_tree / "丁企业" / "项目D" / "业务说明.md"
        doc.write_text("字段口径说明\n" + "口径" * 9000, encoding="utf-8")

    def test_large_doc_summary_output_full_system(self, docs_tree):
        self._make_large_doc(docs_tree)
        result = get_doc("项目D", root=docs_tree)
        assert result.error is None
        # 全文走 system 通道
        assert result.system is not None
        assert "口径" * 9000 in result.system
        assert result.system.startswith("# 项目业务文档全文")
        # output 只给摘要
        assert "摘要" in result.output
        assert "system 通道" in result.output
        assert len(result.output) < 3000
        assert "口径" * 9000 not in result.output

    def test_read_error_reports(self, docs_tree, monkeypatch):
        def boom(self, *args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "read_text", boom)
        result = get_doc("项目A", root=docs_tree)
        assert result.error is not None
        assert "读取文档失败" in result.error
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/tool/test_project_docs.py -v`
Expected: FAIL（`test_large_doc_summary_output_full_system`：当前实现全文走 output，`result.system is None`；`test_read_error_reports` 应已通过）

- [ ] **Step 3: 写最小实现**

`app/tool/project_docs.py` 中 get_doc 的尾部（`full = "\n\n".join(parts)` 之后）替换为：

```python
    full = "\n\n".join(parts)
    source = f"{proj_dir.parent.name}/{proj_dir.name}"
    if len(full) <= _DOC_OUTPUT_MAX:
        return ToolResult(
            output=(
                f"已读取项目业务文档：{source}（{len(mds)} 个文件，共 {len(full)} 字符）\n"
                f"{'─' * 60}\n{full}"
            )
        )
    # 大文档：output 给摘要，全文走 system 通道（对齐 list_tables 双通道惯例）
    summary = full[:_DOC_SUMMARY_MAX]
    return ToolResult(
        output=(
            f"已读取项目业务文档：{source}（{len(mds)} 个文件，共 {len(full)} 字符）\n"
            f"文档较长，以下为开头摘要；完整内容已通过 system 通道提供，请直接据此分析。\n"
            f"{'─' * 60}\n{summary}..."
        ),
        system=f"# 项目业务文档全文（{source}）\n{full}",
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/tool/test_project_docs.py -v`
Expected: PASS（全部用例）

- [ ] **Step 5: 提交**

```bash
git add app/tool/project_docs.py tests/tool/test_project_docs.py
git commit -m "feat(tool): get_doc 大文档摘要走 output、全文走 system 通道"
```

---

### Task 4: CompanyDataLookup 集成分发（TDD）

**Files:**
- Modify: `app/tool/company_data_lookup.py`
- Modify: `tests/tool/test_company_data_lookup.py`（末尾追加测试类，现有测试不动）

**Interfaces:**
- Consumes: Task 1/2 的 `list_projects`、`get_doc`
- Produces: `CompanyDataLookup.docs_root: Optional[Path]`（测试注入用）、`execute(action: str, query_or_sql: str = "") -> ToolResult`

- [ ] **Step 1: 写失败测试**

`tests/tool/test_company_data_lookup.py` 末尾追加：

```python
class TestExecuteProjectDocActions:
    """execute 对 list_projects / get_doc 的分发测试。"""

    async def test_execute_get_doc_routes(self, tmp_path):
        root = tmp_path / "docs"
        (root / "甲企业" / "项目A").mkdir(parents=True)
        (root / "甲企业" / "项目A" / "业务说明.md").write_text(
            "字段口径示例", encoding="utf-8"
        )
        tool = CompanyDataLookup(docs_root=root)

        result = await tool.execute("get_doc", "项目A")

        assert result.error is None
        assert "字段口径示例" in result.output

    async def test_execute_list_projects_routes(self, tmp_path):
        root = tmp_path / "docs"
        (root / "甲企业" / "项目A").mkdir(parents=True)
        (root / "甲企业" / "项目A" / "业务说明.md").write_text("x", encoding="utf-8")
        tool = CompanyDataLookup(docs_root=root)

        result = await tool.execute("list_projects", "")

        assert result.error is None
        assert "甲企业" in result.output


class TestToolSchemaDocActions:
    """description / parameters 应暴露新 action。"""

    def test_description_mentions_doc_actions(self):
        tool = CompanyDataLookup()
        assert "get_doc" in tool.description
        assert "list_projects" in tool.description

    def test_parameters_include_doc_actions(self):
        tool = CompanyDataLookup()
        enum = tool.parameters["properties"]["action"]["enum"]
        assert enum == ["list_projects", "get_doc", "list_tables", "query"]
        assert tool.parameters["required"] == ["action"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/tool/test_company_data_lookup.py -v`
Expected: FAIL（分发测试：`get_doc` 落到 `_execute_mysql` 返回"不支持的 action"，`result.error` 非 None；schema 测试：`enum` 不含新 action。注意 `CompanyDataLookup(docs_root=...)` 在字段未声明时值被忽略，不影响 FAIL 判定）

- [ ] **Step 3: 写最小实现**

`app/tool/company_data_lookup.py` 做 4 处修改：

**3a. 顶部 import 区（`from datetime import datetime` 之后）追加：**

```python
from pathlib import Path

from app.tool import project_docs
```

**3b. 类体中 `DATA_DIR` 常量之后追加 docs_root 字段：**

```python
    # 项目业务文档根目录（测试注入用；None 时走 project_docs 默认 PROJECT_ROOT / DOCS_DIR）
    docs_root: Optional[Path] = None
```

**3c. `description` 整体替换为：**

```python
    description: str = (
        "公司数据查询与项目业务文档工具。有四个 action：\n"
        "1. action='get_doc' — 读取指定企业/项目的业务说明文档（字段口径、表关联、SQL 示例）。"
        "用户提到明确的企业/项目名时优先调用，文档口径优先于表注释。"
        "参数 query_or_sql 传入企业名/项目名。\n"
        "2. action='list_projects' — 列出所有可用企业/项目及其业务文档状态。"
        "不确定项目归属时调用。参数 query_or_sql 可传企业名过滤（可空）。\n"
        "3. action='list_tables' — 获取数据库中所有表的表名、字段名、字段类型、注释，"
        "用于理解哪些数据维度可用。参数 query_or_sql 传入用户的数据分析需求描述。\n"
        "4. action='query' — 在确认表结构能支撑用户需求后，传入 SELECT SQL 执行查询，"
        "结果保存为 CSV 文件到工作目录。参数 query_or_sql 传入完整的 SELECT 语句。\n"
        "使用流程：用户提到企业/项目名 → 先 get_doc 读项目业务文档 "
        "→ list_tables 核对表结构 → query 执行查询 → 用 python_execute 读取 CSV 继续分析。"
    )
```

**3d. `parameters` 整体替换为：**

```python
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_projects", "get_doc", "list_tables", "query"],
                "description": (
                    "操作类型: 'get_doc' 读取项目业务文档；'list_projects' 列出可用项目；"
                    "'list_tables' 获取数据库全部表结构（表名+字段+注释）；"
                    "'query' 执行 SELECT 语句并将结果保存为 CSV"
                ),
            },
            "query_or_sql": {
                "type": "string",
                "description": (
                    "当 action='get_doc' 时，传入企业名/项目名（如 '甲企业/项目A' 或 '项目A'）；"
                    "当 action='list_projects' 时，可传企业名过滤（可空）；"
                    "当 action='list_tables' 时，传入用户的数据分析需求描述；"
                    "当 action='query' 时，传入完整的 SELECT SQL 语句"
                ),
            },
        },
        "required": ["action"],
    }
```

**3e. `execute` 方法整体替换为：**

```python
    async def execute(self, action: str, query_or_sql: str = "") -> ToolResult:
        """执行数据查询操作。

        根据 config.web.data_lookup_mode 分发到 local 或 mysql 模式。
        list_projects / get_doc 为项目业务文档 action，与数据模式无关，优先分发。

        Args:
            action: "list_tables"、"query"、"list_projects" 或 "get_doc"
            query_or_sql: 用户需求描述（list_tables）或 SELECT 语句（query）；
                或企业/项目名（get_doc）、可空（list_projects）

        Returns:
            ToolResult: 成功时 output 包含数据，失败时 error 包含原因
        """
        # ── 项目业务文档 action：与数据模式无关，优先分发 ──
        if action == "list_projects":
            return project_docs.list_projects(query_or_sql or "", root=self.docs_root)
        if action == "get_doc":
            return project_docs.get_doc(query_or_sql or "", root=self.docs_root)

        mode = getattr(config.web, "data_lookup_mode", "local")

        if mode == "local":
            return await self._execute_local(query_or_sql)
        else:
            return await self._execute_mysql(action, query_or_sql)
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `pytest tests/tool/test_company_data_lookup.py tests/tool/test_project_docs.py -v`
Expected: PASS（新增 4 用例 + 现有用例全绿）

- [ ] **Step 5: 提交**

```bash
git add app/tool/company_data_lookup.py tests/tool/test_company_data_lookup.py
git commit -m "feat(tool): CompanyDataLookup 接入 list_projects/get_doc 分发与描述"
```

---

### Task 5: prompt 流程插入"文档优先"步骤（TDD）

**Files:**
- Create: `tests/test_project_doc_prompt.py`
- Modify: `app/prompt/quick_query.py`
- Modify: `app/prompt/visualization.py`

**Interfaces:**
- Consumes: 无
- Produces: 无（prompt 纯文本，防回归靠内容断言测试）

- [ ] **Step 1: 写失败测试**

创建 `tests/test_project_doc_prompt.py`：

```python
"""QuickQuery / DataAnalysis prompt 的项目文档引导测试。"""
from app.prompt.quick_query import SYSTEM_PROMPT as QUICK_QUERY_PROMPT
from app.prompt.visualization import SYSTEM_PROMPT as VISUALIZATION_PROMPT


class TestQuickQueryPromptDocGuidance:
    def test_guides_get_doc_first(self):
        assert "get_doc" in QUICK_QUERY_PROMPT
        assert "list_projects" in QUICK_QUERY_PROMPT

    def test_doc_priority_over_table_comment(self):
        assert "文档口径优先于表注释" in QUICK_QUERY_PROMPT


class TestVisualizationPromptDocGuidance:
    def test_guides_get_doc_first(self):
        assert "get_doc" in VISUALIZATION_PROMPT
        assert "list_projects" in VISUALIZATION_PROMPT

    def test_doc_priority_over_table_comment(self):
        assert "文档口径优先于表注释" in VISUALIZATION_PROMPT
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_project_doc_prompt.py -v`
Expected: FAIL（4 个断言均不成立）

- [ ] **Step 3: 写最小实现**

**3a. `app/prompt/quick_query.py`：** 把"3. company_data_lookup 使用流程："整段（原 a-d 四条）替换为：

```
3. company_data_lookup 使用流程：
   a. 用户提到明确的企业/项目名 → 先调用 action="get_doc" 读取该项目业务文档
      （含字段口径、表关联、SQL 示例；文档口径优先于表注释）
   b. 文档未命中或用户未提及项目 → 必要时调用 action="list_projects" 确认项目归属
      （纯通用查询可直接跳过本步）
   c. 调用 action="list_tables" 获取数据库全部表结构（表名、字段名、字段类型、注释）
   d. **反驳自省**（必须执行，不可跳过）：
      - 逐一比对用户需要的数据维度与现有表字段的覆盖情况（结合文档口径）
      - 部分缺失时调用 ask_human 告知用户，确认后再继续
      - 完全无法支撑时直接 terminate，不要强行查询
   e. 确认可继续后编写 SELECT SQL（参考文档中的 SQL 示例），调用 action="query" 执行
   f. 查询结果 CSV 用 python_execute 读取并计算
```

**3b. `app/prompt/visualization.py`：** 把"3. company_data_lookup 使用流程："整段（原 a-d 四条）替换为：

```
3. company_data_lookup 使用流程：
   a. 用户提到明确的企业/项目名 → 先调用 action="get_doc" 读取该项目业务文档
      （含字段口径、表关联、SQL 示例；文档口径优先于表注释）
   b. 文档未命中或用户未提及项目 → 必要时调用 action="list_projects" 确认项目归属
      （纯通用查询可直接跳过本步）
   c. 调用 action="list_tables" 获取数据库全部表结构（表名、字段名、字段类型、注释）
   d. **反驳自省**（必须执行，不可跳过）：
      - 将用户的分析需求拆解为数据维度清单（时间、地域、指标、分类等）
      - 逐一比对每个维度是否在现有表字段中有对应（结合文档口径）
      - 覆盖充分 → 继续编写 SQL
      - 部分缺失 → 调用 ask_human 告知用户"现有数据能分析 X，但缺少 Y 维度，无法分析 Z"，询问是否在当前约束下继续
      - 完全无法支撑 → 直接告知用户原因，调用 terminate 结束，**绝不强行分析**
   e. 确认可继续后，基于表结构编写精准的 SELECT SQL（参考文档中的 SQL 示例），调用 action="query" 执行
   f. 查询结果 CSV 用 python_execute (pandas.read_csv) 加载并分析
```

（两处均为纯文本替换：原 a 条变为 c 条，原 b/c/d 条顺延为 d/e/f 条，新增 a/b 两条。其余 prompt 内容不动。）

- [ ] **Step 4: 跑测试确认通过 + prompt 相关回归**

Run: `pytest tests/test_project_doc_prompt.py tests/test_prompt_preview_rules.py tests/test_toolcall_system_channel.py -v`
Expected: PASS（新增 4 用例 + 既有 prompt/通道相关测试全绿）

- [ ] **Step 5: 提交**

```bash
git add app/prompt/quick_query.py app/prompt/visualization.py tests/test_project_doc_prompt.py
git commit -m "feat(prompt): QuickQuery/DataAnalysis 流程插入项目文档优先步骤"
```

---

### Task 6: 文档模板与示例资产（TDD）

**Files:**
- Create: `project_docs/TEMPLATE.md`
- Create: `project_docs/示例企业/示例项目/业务说明.md`
- Modify: `tests/tool/test_project_docs.py`（追加资产测试类）

**Interfaces:**
- Consumes: 无
- Produces: 静态资产（`PROJECT_ROOT / "project_docs"` 下模板与示例文档）

- [ ] **Step 1: 写失败测试**

`tests/tool/test_project_docs.py` 顶部 import 区追加 `from app.config import PROJECT_ROOT`，末尾追加：

```python
class TestExampleDocAssets:
    """项目根 project_docs/ 下的模板与示例文档资产检查。"""

    def test_example_doc_has_all_sections(self):
        doc = PROJECT_ROOT / DOCS_DIR / "示例企业" / "示例项目" / "业务说明.md"
        assert doc.exists()
        content = doc.read_text(encoding="utf-8")
        sections = [
            "项目概述",
            "涉及数据表",
            "字段口径说明",
            "表关联关系",
            "常用查询 SQL 示例",
            "注意事项",
        ]
        for i, section in enumerate(sections, start=1):
            assert f"## {i}. {section}" in content

    def test_example_doc_forbids_file_paths(self):
        doc = PROJECT_ROOT / DOCS_DIR / "示例企业" / "示例项目" / "业务说明.md"
        content = doc.read_text(encoding="utf-8")
        assert "不包含任何文件路径" in content

    def test_template_exists_with_sections(self):
        tpl = PROJECT_ROOT / DOCS_DIR / "TEMPLATE.md"
        assert tpl.exists()
        content = tpl.read_text(encoding="utf-8")
        assert "## 1. 项目概述" in content
        assert "## 3. 字段口径说明" in content
        assert "不包含任何文件路径" in content
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/tool/test_project_docs.py -v`
Expected: FAIL（3 个资产用例：文件不存在）

- [ ] **Step 3: 创建资产文件**

创建 `project_docs/TEMPLATE.md`：

```markdown
# {项目名} 业务数据说明

> 本文档只描述表、字段、SQL 口径与业务规则，**不包含任何文件路径**
> （数据获取统一走 company_data_lookup 的 query action，路径由工具自动告知）。

## 1. 项目概述

（一段话：项目是什么、核心业务对象、数据从哪来）

## 2. 涉及数据表

| 表名 | 用途 | 备注 |
|------|------|------|
|      |      |      |

（只列本项目相关的表，注明主键、时间字段）

## 3. 字段口径说明

（核心章节。按表列出关键字段：字段名 → 业务含义、枚举值、单位；
特别写明容易用错的字段与正确替代，如"合同金额用 xxx 字段，勿用 yyy"）

## 4. 表关联关系

（表间 JOIN 键、一对多/多对一、关联时的坑，如去重、时间对齐）

## 5. 常用查询 SQL 示例

（2-5 个本项目高频查询的完整 SQL 模板，模型可参考改写）

## 6. 注意事项

（数据更新频率、脏数据、特殊业务规则）
```

创建 `project_docs/示例企业/示例项目/业务说明.md`：

```markdown
# 示例项目 业务数据说明

> 本文档只描述表、字段、SQL 口径与业务规则，**不包含任何文件路径**
> （数据获取统一走 company_data_lookup 的 query action，路径由工具自动告知）。

## 1. 项目概述

示例项目是示例企业的线上销售业务，核心数据为订单、用户与商品三张表，
数据每日凌晨同步一次。

## 2. 涉及数据表

| 表名 | 用途 | 备注 |
|------|------|------|
| fa_orders | 订单表 | 主键 id；时间字段 create_time |
| fa_user | 用户表 | 主键 id |
| fa_goods | 商品表 | 主键 id |

## 3. 字段口径说明

- fa_orders.amount：订单实际支付金额（元，decimal(10,2)），**统计销售额用此字段**
- fa_orders.total_amount：订单原价（含优惠抵扣），勿用于销售额统计
- fa_orders.status：订单状态枚举：1=待支付 2=已支付 3=已发货 4=已完成 5=已退款；
  统计有效销售额需 status IN (2,3,4)
- fa_orders.user_id：下单用户 id，关联 fa_user.id
- fa_user.reg_time：用户注册时间
- fa_user.level：用户等级：1=普通 2=白银 3=黄金 4=钻石

## 4. 表关联关系

- 订单 → 用户：fa_orders.user_id = fa_user.id（多对一）
- 订单 → 商品：fa_orders.goods_id = fa_goods.id（多对一）
- 统计用户维度数据时按 fa_user.id 去重后聚合，勿直接对 fa_orders 聚合（一个用户多单）

## 5. 常用查询 SQL 示例

-- 按月统计有效销售额
SELECT DATE_FORMAT(create_time, '%Y-%m') AS month,
       SUM(amount) AS sales
FROM fa_orders
WHERE status IN (2, 3, 4)
GROUP BY DATE_FORMAT(create_time, '%Y-%m')
ORDER BY month;

-- 各用户等级消费 TOP10 用户
SELECT u.id, u.level, SUM(o.amount) AS total
FROM fa_orders o
JOIN fa_user u ON o.user_id = u.id
WHERE o.status IN (2, 3, 4)
GROUP BY u.id, u.level
ORDER BY total DESC
LIMIT 10;

## 6. 注意事项

- 数据每日 02:00 同步，当日数据次日才完整
- fa_orders 中偶有测试订单（user_id = 0），统计时排除 user_id = 0
- 退款订单（status=5）不计入任何金额统计
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `pytest tests/tool/test_project_docs.py -v` 然后 `pytest tests/tool/ tests/test_prompt_preview_rules.py tests/test_project_doc_prompt.py -v`
Expected: PASS（全部用例）

- [ ] **Step 5: 提交**

```bash
git add project_docs/TEMPLATE.md project_docs/示例企业/示例项目/业务说明.md tests/tool/test_project_docs.py
git commit -m "docs(project): 项目业务文档模板与示例（project_docs/）"
```

---

## 收尾验证

全部任务完成后执行一次全量回归：

```bash
pytest tests/tool/test_project_docs.py tests/tool/test_company_data_lookup.py tests/test_project_doc_prompt.py tests/test_prompt_preview_rules.py tests/test_toolcall_system_channel.py -v
```

Expected: 全部 PASS，无既有用例回归。
