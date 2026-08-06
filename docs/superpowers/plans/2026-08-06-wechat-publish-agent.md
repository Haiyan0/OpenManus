# 微信公众号发布 Agent 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 baoyu-post-to-wechat 的 API 发布能力集成进 OpenManus，作为 Web 端可选的独立 Agent（wechat_publish），发布文章到公众号草稿箱。

**Architecture:** 自包含脚本目录 `app/tool/wechat_publish/scripts/`（复制 wechat-api.ts 及依赖链 + bun install）；`WechatPublishTool`（BaseTool 子类）用 subprocess 调 `bun wechat-api.ts`；`WechatPublish` Agent（ToolCallAgent 子类）组合该工具 + python_execute/ask_human；Web 端注册 AGENT_TYPES + Observable 包装 + 前端对话框选项。凭据存仓库根 `.baoyu-skills/.env`（gitignore），脚本原生读取。

**Tech Stack:** Python 3.12 / pydantic / bun + TypeScript（wechat-api.ts）/ Vue3（web_ui）

**Spec:** `docs/superpowers/specs/2026-08-06-wechat-publish-agent-design.md`

## Global Constraints

- Python 解释器（本机固定）：`C:\Users\hyh\anaconda3\envs\open_manus\python.exe`，**不要用** `python`/`python3`
- Shell 为 PowerShell 5.1（Win11），不支持 `&&`，命令间用 `;` 衔接
- 跑测试用 `-m pytest` 形式避免入口被 `main.py` 拦截
- `config/config.toml` 被 gitignore 但历史被 git 跟踪：不要 `git add` 它，也不要 `git add -A`/`git commit -a`（会卷入无关改动，如 messages.xlsx / opencode.json）
- 提交前运行 pre-commit：`pre-commit run --all-files`（链路 black → autoflake → isort；.ts/.json 文件不受影响）
- 代码注释用简体中文，标识符英文
- 脚本源目录（全局 skill，只读引用，不改动）：`C:\Users\hyh\.claude\plugins\cache\baoyu-skills\baoyu-skills\441ca307a60c\skills\baoyu-post-to-wechat\scripts`
- bun 本机未安装，但 npm 11.6.2 可用；脚本运行走 `npx -y bun` 兜底
- 凭据（WECHAT_APP_ID/WECHAT_APP_SECRET）由用户手写进 `.baoyu-skills/.env`（gitignore），任务不生成真实凭据
- 工具执行 cwd 必须是仓库根 `PROJECT_ROOT`（wechat-api.ts 基于 `process.cwd()` 查找 `.baoyu-skills/.env`，见 spec §6）

---

### Task 1: 复制脚本子集 + 依赖安装 + gitignore

**Files:**
- Create: `app/tool/wechat_publish/scripts/`（10 个文件，见 Step 1 清单）
- Create: `.baoyu-skills/.gitkeep`（占位，保证目录进入 git）
- Modify: `.gitignore`（追加 `node_modules/` 与 `.baoyu-skills/` 规则）
- Modify: `app/tool/wechat_publish/__init__.py`（空包标记）

**Interfaces:**
- Consumes: 无（独立任务）
- Produces: `app/tool/wechat_publish/scripts/wechat-api.ts`（Task 2 的 subprocess 调用目标）

- [ ] **Step 1: 创建目录并复制脚本**

源目录 `SRC = C:\Users\hyh\.claude\plugins\cache\baoyu-skills\baoyu-skills\441ca307a60c\skills\baoyu-post-to-wechat\scripts`，目标 `DST = C:\Code\OpenManus\app\tool\wechat_publish\scripts`：

```powershell
New-Item -ItemType Directory -Path "app\tool\wechat_publish\scripts" -Force | Out-Null
$SRC = "C:\Users\hyh\.claude\plugins\cache\baoyu-skills\baoyu-skills\441ca307a60c\skills\baoyu-post-to-wechat\scripts"
$DST = "C:\Code\OpenManus\app\tool\wechat_publish\scripts"
$files = @(
  "wechat-api.ts", "md-to-wechat.ts", "wechat-extend-config.ts",
  "wechat-http.ts", "wechat-image-loader.ts", "wechat-image-processor.ts",
  "wechat-remote-publish.ts", "wechat-socks-http.ts",
  "package.json", "bun.lock"
)
foreach ($f in $files) { Copy-Item "$SRC\$f" "$DST\$f" }
```

验证：`Get-ChildItem app\tool\wechat_publish\scripts -Name` 应列出上述 10 个文件（**不含** node_modules、cdp.ts、wechat-article.ts、wechat-browser.ts、*.test.ts）。

- [ ] **Step 2: 创建 `app/tool/wechat_publish/__init__.py` 与 `.baoyu-skills/.gitkeep`**

```powershell
New-Item -ItemType File -Path "app\tool\wechat_publish\__init__.py" -Force | Out-Null
New-Item -ItemType Directory -Path ".baoyu-skills" -Force | Out-Null
New-Item -ItemType File -Path ".baoyu-skills\.gitkeep" -Force | Out-Null
```

`app/tool/wechat_publish/__init__.py` 内容留空。

- [ ] **Step 3: 更新 .gitignore**

读 `.gitignore`，在末尾追加：

```gitignore
# 公众号发布工具 bun 依赖与凭据
app/tool/wechat_publish/scripts/node_modules/
.baoyu-skills/
```

（若仓库已有 `.baoyu-skills/` 或 node_modules 规则，去重合并，不重复添加。）

- [ ] **Step 4: 安装 bun 依赖**

Run: `npx -y bun install`（cwd 为 `app\tool\wechat_publish\scripts`）
Expected: `node_modules/` 生成，安装成功（bun 自动下载，首次较慢）

验证：`Test-Path app\tool\wechat_publish\scripts\node_modules` 返回 True

- [ ] **Step 5: 验证脚本可运行（--help 冒烟）**

Run: `npx -y bun app\tool\wechat_publish\scripts\wechat-api.ts --help`（PowerShell）
Expected: 输出用法说明（含 `--title`、`--dry-run`、`Environment Variables` 等段落），退出码 0

若报缺依赖（如 baoyu-md 找不到），回 Step 4 检查安装输出。

- [ ] **Step 6: 提交**

```bash
git add app/tool/wechat_publish/scripts app/tool/wechat_publish/__init__.py .baoyu-skills/.gitkeep .gitignore
git commit -m "feat(tool): 复制公众号发布脚本子集进仓库，bun 依赖自包含"
```

注意：node_modules 已被 gitignore，不会进入提交。提交后 `git status` 应只剩预期的 config.toml/messages.xlsx/opencode.json。

---

### Task 2: `WechatPublishTool`（BaseTool 子类）

**Files:**
- Create: `app/tool/wechat_publish/wechat_publish.py`
- Test: `tests/tool/test_wechat_publish.py`

**Interfaces:**
- Consumes: `app/tool/wechat_publish/scripts/wechat-api.ts`（Task 1）；`app.config.PROJECT_ROOT`
- Produces: `WechatPublishTool`（name=`wechat_publish`，`async execute(action, file_path, title="", summary="", author="", theme="default", cover="") -> ToolResult`）；`_build_command(...) -> list[str]`；`_run_script(cmd) -> tuple[int, str, str]`（Task 3 的 Agent 组装该工具）

- [ ] **Step 1: 写失败测试**

`tests/tool/test_wechat_publish.py`：

```python
"""WechatPublishTool 单元测试（mock subprocess，无真实网络）。"""
from pathlib import Path

import pytest

from app.config import PROJECT_ROOT
from app.tool.wechat_publish.wechat_publish import WechatPublishTool


class TestBuildCommand:
    """_build_command 参数拼装测试。"""

    def test_publish_default_theme(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(
            action="publish",
            file_path="article.md",
            title="我的文章",
            summary="摘要",
            author="刻晴宇宙",
            theme="default",
            cover="",
        )
        joined = " ".join(cmd)
        assert "wechat-api.ts" in joined
        assert "article.md" in joined
        assert "--title" in joined and "我的文章" in joined
        assert "--summary" in joined and "摘要" in joined
        assert "--author" in joined and "刻晴宇宙" in joined
        assert "--theme" in joined and "default" in joined
        assert "--dry-run" not in joined

    def test_preview_includes_dry_run(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(action="preview", file_path="a.md")
        assert "--dry-run" in cmd

    def test_cover_passed_through(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(action="publish", file_path="a.md", cover="imgs/cover.png")
        assert "--cover" in cmd and "imgs/cover.png" in cmd

    def test_empty_optional_params_omitted(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(action="publish", file_path="a.md")
        joined = " ".join(cmd)
        assert "--title" not in joined
        assert "--summary" not in joined
        assert "--author" not in joined
        assert "--theme" in joined and "default" in joined  # theme 恒传


class TestRunScript:
    """_run_script 子进程执行测试。"""

    def test_success_returns_stdout(self, monkeypatch):
        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 0
            stdout = "OK output"
            stderr = ""

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        code, out, err = tool._run_script(["bun", "x.ts"])
        assert code == 0
        assert out == "OK output"

    def test_failure_returns_stderr(self, monkeypatch):
        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 2
            stdout = ""
            stderr = "boom"

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        code, out, err = tool._run_script(["bun", "x.ts"])
        assert code == 2
        assert err == "boom"

    def test_cwd_is_project_root(self, monkeypatch):
        tool = WechatPublishTool()
        captured = {}

        class _FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""

        def _fake_run(cmd, **kwargs):
            captured["cwd"] = kwargs.get("cwd")
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        tool._run_script(["bun", "x.ts"])
        assert Path(captured["cwd"]) == PROJECT_ROOT


class TestExecute:
    """execute 入口测试。"""

    def test_execute_publish_returns_success(self, monkeypatch):
        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 0
            stdout = '{"media_id": "abc123"}'
            stderr = ""

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        result = tool._run_script(["bun", "x.ts"])
        assert result[0] == 0
```

（`_run_script` 返回 (returncode, stdout, stderr)；`execute` 内部据此组 ToolResult，其组装逻辑由 Step 3 的 execute 实现后由 Task 2 Step 4 补充两个 execute 级断言测试，见 Step 4。）

- [ ] **Step 2: 跑测试确认失败**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/tool/test_wechat_publish.py -v`
Expected: FAIL，报 `ModuleNotFoundError: No module named 'app.tool.wechat_publish.wechat_publish'`

- [ ] **Step 3: 实现 WechatPublishTool**

`app/tool/wechat_publish/wechat_publish.py`：

```python
"""微信公众号发布工具。

通过 subprocess 调用自包含的 bun 脚本（scripts/wechat-api.ts）发布
markdown/html 文章到公众号草稿箱。凭据由脚本从 <cwd>/.baoyu-skills/.env
读取（cwd 必须是仓库根，见 spec §6）。
"""

import os
import shutil
import subprocess
from typing import Optional

from app.config import PROJECT_ROOT
from app.logger import logger
from app.tool.base import BaseTool, ToolResult

_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "scripts")
_SCRIPT_PATH = os.path.join(_SCRIPT_DIR, "wechat-api.ts")
_SUBPROCESS_TIMEOUT = 120


class WechatPublishTool(BaseTool):
    """发布文章到微信公众号草稿箱。"""

    name: str = "wechat_publish"
    description: str = (
        "微信公众号发布工具。两个 action：\n"
        "1. action='preview' — 本地渲染校验（--dry-run），不产生草稿，返回渲染结果或错误；"
        "发布前必须先用 preview 校验。\n"
        "2. action='publish' — 将 markdown 或 html 文件发布到公众号草稿箱，"
        "成功返回 media_id。\n"
        "参数：file_path 为文章文件绝对路径（markdown 优先，含 frontmatter 时标题/作者/摘要"
        "可自动读取）；title/summary/author/theme/cover 可选覆盖。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["preview", "publish"],
                "description": "preview=本地校验（推荐发布前先跑），publish=发布到草稿箱",
            },
            "file_path": {
                "type": "string",
                "description": "文章文件绝对路径（.md 或 .html）",
            },
            "title": {
                "type": "string",
                "description": "文章标题（可选，缺省读 frontmatter 或自动生成）",
            },
            "summary": {
                "type": "string",
                "description": "文章摘要（可选，最多 128 字符）",
            },
            "author": {
                "type": "string",
                "description": "作者名（可选，最多 16 字符）",
            },
            "theme": {
                "type": "string",
                "description": "渲染主题：default/grace/simple/modern（默认 default）",
            },
            "cover": {
                "type": "string",
                "description": "封面图片路径（可选，缺省用文章内第一张图）",
            },
        },
        "required": ["action", "file_path"],
    }

    def _resolve_runner(self) -> list[str]:
        """解析 bun 运行器：优先 bun，缺失时回退 npx -y bun。"""
        bun = shutil.which("bun")
        if bun:
            return [bun]
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if npx:
            return [npx, "-y", "bun"]
        raise RuntimeError(
            "未找到 bun 运行时。请安装 bun（https://bun.sh）或确保 npm 可用。"
        )

    def _build_command(
        self,
        action: str,
        file_path: str,
        title: str = "",
        summary: str = "",
        author: str = "",
        theme: str = "default",
        cover: str = "",
    ) -> list[str]:
        """拼装 wechat-api.ts 调用参数。"""
        cmd = self._resolve_runner() + [_SCRIPT_PATH, file_path]
        if title:
            cmd += ["--title", title]
        if summary:
            cmd += ["--summary", summary]
        if author:
            cmd += ["--author", author]
        cmd += ["--theme", theme]
        if cover:
            cmd += ["--cover", cover]
        if action == "preview":
            cmd += ["--dry-run"]
        return cmd

    def _run_script(self, cmd: list[str]) -> tuple[int, str, str]:
        """同步执行脚本（cwd 必须为仓库根，凭据 .baoyu-skills/.env 按 cwd 解析）。"""
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    async def execute(
        self,
        action: str,
        file_path: str,
        title: str = "",
        summary: str = "",
        author: str = "",
        theme: str = "default",
        cover: str = "",
    ) -> ToolResult:
        """执行发布操作。"""
        import asyncio

        if action not in ("preview", "publish"):
            return self.fail_response(
                f"不支持的 action: '{action}'，可选值为 'preview' 或 'publish'"
            )
        if not os.path.isfile(file_path):
            return self.fail_response(f"文章文件不存在: {file_path}")

        try:
            cmd = self._build_command(
                action, file_path, title, summary, author, theme, cover
            )
            code, stdout, stderr = await asyncio.to_thread(self._run_script, cmd)
        except subprocess.TimeoutExpired:
            return self.fail_response(
                f"发布脚本执行超时（>{_SUBPROCESS_TIMEOUT}s）。请重试或检查网络。"
            )
        except RuntimeError as e:
            return self.fail_response(str(e))
        except Exception as e:
            logger.error(f"发布脚本执行异常: {e}", exc_info=True)
            return self.fail_response(f"发布脚本执行异常: {e}")

        if code != 0:
            logger.error(f"发布脚本失败(exit={code}): {stderr}")
            return self.fail_response(
                f"发布失败（脚本退出码 {code}）:\n{stderr}\n"
                f"常见原因：凭据缺失/错误（检查仓库根 .baoyu-skills/.env），"
                f"或 IP 不在公众号白名单（公众号后台 → 设置与开发 → 基本配置 → IP 白名单）。"
            )

        logger.info(f"发布成功: {stdout.strip()[:500]}")
        return ToolResult(output=stdout.strip() or "(脚本执行成功，无输出)")
```

- [ ] **Step 4: 补 execute 级测试并跑全量**

在 `tests/tool/test_wechat_publish.py` 的 `TestExecute` 追加：

```python
    def test_execute_publish_success(self, monkeypatch):
        """execute 成功路径：透传脚本 stdout。"""
        import asyncio

        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 0
            stdout = '{"media_id": "abc123"}'
            stderr = ""

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        result = asyncio.run(tool.execute(action="publish", file_path="a.md"))
        assert result.error is None
        assert "abc123" in str(result.output)

    def test_execute_publish_failure(self, monkeypatch):
        """execute 失败路径：返回 error 且不含 crash。"""
        import asyncio

        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 1
            stdout = ""
            stderr = "access_token invalid"

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        result = asyncio.run(tool.execute(action="publish", file_path="a.md"))
        assert result.error is not None
        assert "access_token invalid" in result.error

    def test_execute_file_not_found(self):
        import asyncio

        tool = WechatPublishTool()
        result = asyncio.run(tool.execute(action="publish", file_path="no_such.md"))
        assert result.error is not None
        assert "不存在" in result.error
```

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/tool/test_wechat_publish.py -v`
Expected: 全部 PASS（前置的 TestExecute 首测为占位断言，若 `_run_script` 返回 tuple 则一致通过）

- [ ] **Step 5: pre-commit + 提交**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/tool/test_wechat_publish.py tests/tool/test_company_data_lookup.py -q`（回归，Expected: 全 PASS）

```powershell
& "C:\Users\hyh\anaconda3\envs\open_manus\Scripts\pre-commit.exe" run --files app/tool/wechat_publish/wechat_publish.py tests/tool/test_wechat_publish.py
```

修复格式问题后：

```bash
git add app/tool/wechat_publish/wechat_publish.py tests/tool/test_wechat_publish.py
git commit -m "feat(tool): 新增 WechatPublishTool 公众号发布工具"
```

---

### Task 3: `WechatPublish` Agent + 提示词

**Files:**
- Create: `app/prompt/wechat_publish.py`
- Create: `app/agent/wechat_publish.py`

**Interfaces:**
- Consumes: `WechatPublishTool`（Task 2）；`config.workspace_root`
- Produces: `WechatPublish`（name=`wechat_publish`，ToolCallAgent 子类，Task 4 注册用）

- [ ] **Step 1: 写提示词**

`app/prompt/wechat_publish.py`（参照 `app/prompt/quick_query.py` 的格式——先读它对齐结构）：

```python
"""公众号发布 Agent 提示词。"""

SYSTEM_PROMPT = """你是公众号文章发布助手，负责把内容发布到微信公众号草稿箱（不会直接发布正式文章）。

工作流程：
1. 明确内容来源：询问用户是要粘贴文本、提供文件路径，还是由你撰写。
2. 准备文章文件：把最终内容保存为 markdown 文件到工作目录 {directory}；
   优先使用 frontmatter 写入 title/author/digest，供脚本自动读取。
3. 发布前先调用 wechat_publish(action='preview') 本地校验渲染，确认无错误。
4. 校验通过后调用 wechat_publish(action='publish') 发布到草稿箱，向用户报告 media_id。
5. 发布完成后用 terminate 结束。

约束：
- 只发布用户明确要求的内容；内容模糊时先用 ask_human 澄清。
- 不修改公众号后台其它设置，仅创建草稿。
- 发布失败时把脚本返回的错误原因转述给用户，并给出可操作的修复建议
  （检查 .baoyu-skills/.env 凭据、IP 白名单等）。
"""

NEXT_STEP_PROMPT = (
    "请继续执行发布流程：内容就绪后先 preview 校验，再 publish 发布到草稿箱。"
)
```

- [ ] **Step 2: 写 Agent 类**

`app/agent/wechat_publish.py`（参照 `app/agent/quick_query.py` 的结构）：

```python
"""公众号发布智能体。"""

from typing import Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.logger import logger
from app.prompt.wechat_publish import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ask_human import AskHuman
from app.tool.chart_visualization.python_execute import NormalPythonExecute
from app.tool.wechat_publish.wechat_publish import WechatPublishTool


class WechatPublish(ToolCallAgent):
    """公众号发布智能体：把文章发布到微信公众号草稿箱。"""

    name: str = "wechat_publish"
    description: str = "公众号发布智能体，可将 markdown 内容发布到微信公众号草稿箱"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 30

    # Sandbox 注入（由 Web 层设置，可选）
    sandbox: Optional[object] = None
    _sandbox_workspace: str = ""

    # 工具集合：公众号发布 + Python 执行 + 人工询问 + 终止
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            WechatPublishTool(),
            NormalPythonExecute(),
            AskHuman(),
            Terminate(),
        )
    )

    def set_sandbox(
        self, sandbox: object, workspace: str = "/workspace", host_workspace: str = ""
    ) -> None:
        """注入 Sandbox 并同步到所有执行类工具（与 QuickQuery.set_sandbox 一致）。"""
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
                    logger.debug(f"ToolDesc 已更新: {tool.name} → {workspace}")
```

- [ ] **Step 3: 冒烟验证（导入 + 实例化）**

Run:

```powershell
& "C:\Users\hyh\anaconda3\envs\open_manus\python.exe" -c "from app.agent.wechat_publish import WechatPublish; a = WechatPublish(); print(a.name, [t.name for t in a.available_tools])"
```

Expected: 输出 `wechat_publish ['wechat_publish', 'python_execute', 'ask_human', 'terminate']`

- [ ] **Step 4: pre-commit + 提交**

```powershell
& "C:\Users\hyh\anaconda3\envs\open_manus\Scripts\pre-commit.exe" run --files app/prompt/wechat_publish.py app/agent/wechat_publish.py
```

修复格式问题后：

```bash
git add app/prompt/wechat_publish.py app/agent/wechat_publish.py
git commit -m "feat(agent): 新增 WechatPublish 公众号发布智能体"
```

---

### Task 4: Web 端注册（后端 + 前端）

**Files:**
- Modify: `app/web/chat/models.py:10`（AGENT_TYPES 加 `"wechat_publish"`）
- Modify: `app/web/agent_runner.py`（新增 `ObservableWechatPublish` + 工厂分支）
- Modify: `web_ui/src/components/NewChatDialog.vue:9`（加 option）
- Test: `tests/web/` 无新增（复用现有 chat 创建测试路径，见 Step 5）

**Interfaces:**
- Consumes: `WechatPublish`（Task 3）；现有 `ObservableQuickQuery` 模式（agent_runner.py）
- Produces: `create_observable_agent("wechat_publish", ...)` 可用；前端新建会话可选「公众号发布」

- [ ] **Step 1: AGENT_TYPES 注册**

`app/web/chat/models.py` 第 10 行改为：

```python
AGENT_TYPES = {"general", "data_analysis", "quick_query", "wechat_publish"}
```

- [ ] **Step 2: agent_runner 增加 Observable 包装与工厂分支**

读 `app/web/agent_runner.py` 中 `ObservableQuickQuery` 定义（约第 130-230 行），完全照其模式新增：

```python
class ObservableWechatPublish(WechatPublish):
    """WechatPublish 的事件注入子类。"""

    event_queue: asyncio.Queue | None = None

    async def step(self) -> str:
        await _emit(
            self.event_queue,
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        should_act = await super().think()
        last_msg = self.messages[-1] if self.messages else None
        thinking_content = ""
        tool_calls_data: list[dict] = []

        if last_msg and last_msg.role == "assistant":
            thinking_content = last_msg.content or ""
            if last_msg.tool_calls:
                tool_calls_data = [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in last_msg.tool_calls
                ]

        if thinking_content or tool_calls_data:
            await _emit(
                self.event_queue,
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        if not should_act and thinking_content and not tool_calls_data:
            await _emit(self.event_queue, "assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        await _emit(
            self.event_queue,
            "tool_start",
            {"tool": command.function.name, "args": command.function.arguments},
        )
        result = await super().execute_tool(command)
        ok = not str(result).startswith("Error:")
        await _emit(
            self.event_queue,
            "tool_end",
            {"tool": command.function.name, "result": str(result), "ok": ok},
        )
        return result
```

文件顶部 import 追加：`from app.agent.wechat_publish import WechatPublish`。

`create_observable_agent`（第 258-265 行）加分支：

```python
    elif agent_type == "wechat_publish":
        agent = ObservableWechatPublish()
```

（返回值类型注解 `-> Manus | DataAnalysis | QuickQuery` 同步加 `| WechatPublish`。）

- [ ] **Step 3: 前端对话框加选项**

`web_ui/src/components/NewChatDialog.vue` 第 9 行后追加：

```html
        <option value="wechat_publish">📰 公众号发布</option>
```

- [ ] **Step 4: 前端构建**

Run: `npm run build`（cwd 为 `web_ui`）
Expected: `web_ui/dist` 产物更新（该目录已被 git 追踪管理，见 AGENTS.md；若构建产物不应提交则仅本地生效并说明）

- [ ] **Step 5: 后端回归验证**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/web/ -q`
Expected: 全 PASS（依赖 [web] MySQL 配置，`data_lookup_mode="local"` 时走本地数据资源；chat 创建含 agent_type 校验，新类型应通过）

若 tests/web 有环境依赖失败（MySQL 不可达），跑最小集：

```powershell
& "C:\Users\hyh\anaconda3\envs\open_manus\python.exe" -c "from app.web.chat.models import AGENT_TYPES; assert 'wechat_publish' in AGENT_TYPES; print(AGENT_TYPES)"
```

Expected: 打印包含 wechat_publish 的集合。

- [ ] **Step 6: pre-commit + 提交**

```powershell
& "C:\Users\hyh\anaconda3\envs\open_manus\Scripts\pre-commit.exe" run --files app/web/chat/models.py app/web/agent_runner.py
```

（vue 文件不受 python pre-commit 影响）

```bash
git add app/web/chat/models.py app/web/agent_runner.py web_ui/src/components/NewChatDialog.vue
git commit -m "feat(web): 注册 wechat_publish Agent（后端工厂 + 前端入口）"
```

---

## Self-Review 记录

- **Spec 覆盖**：脚本复制自包含（Task 1）、工具（Task 2）、Agent+提示词（Task 3）、Web 注册+前端（Task 4）、凭据 .baoyu-skills/.env + gitignore（Task 1 Step 2/3）、cwd=PROJECT_ROOT（Task 2 `_run_script`）、preview 先于 publish（提示词 Task 3）、非目标未实现（无 browser/remote/工具形式）——全部覆盖
- **无占位符**：每个步骤含具体代码与命令；Task 2 的 execute 级测试在 Step 4 补齐（Step 1 未含是刻意拆分，非占位）
- **类型一致**：`_build_command(action, file_path, title="", summary="", author="", theme="default", cover="") -> list[str]`、`_run_script(cmd) -> tuple[int, str, str]` 在测试与实现中签名一致；`WechatPublish.name = "wechat_publish"` 贯穿 Agent/AGENT_TYPES/前端
