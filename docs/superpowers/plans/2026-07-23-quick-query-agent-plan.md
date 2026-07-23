# QuickQuery Agent 轻量数据查询智能体 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 QuickQuery Agent，让用户在前端选择「快速查询」模式，直接返回数据查询结果，不生成图表和报告。

**Architecture:** 新建 QuickQuery Agent 类（继承 ToolCallAgent），复用 CompanyDataLookup + NormalPythonExecute + AskHuman + Terminate 四个工具，通过 agent_runner 工厂注册，前端 NewChatDialog 新增选项。Sandbox 层和 WebSocket 层无需改动。

**Tech Stack:** Python 3.12, Pydantic, Vue 3 + TypeScript, Docker Sandbox

## Global Constraints

- Python 路径：`C:\Users\hyh\anaconda3\envs\open_manus\python.exe`
- 工作目录：`C:\Code\OpenManus`
- 当前分支：`feat/web-chat`
- 系统：Windows 11，Shell：PowerShell
- 代码注释：简体中文
- max_steps: 15，工具集 4 个
- 不复用 VisualizationPrepare / DataVisualization

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `app/prompt/quick_query.py` | SYSTEM_PROMPT + NEXT_STEP_PROMPT | **新建** |
| `app/agent/quick_query.py` | QuickQuery Agent 类（继承 ToolCallAgent） | **新建** |
| `app/web/agent_runner.py` | ObservableQuickQuery + 工厂分支 + 导入 | **修改** |
| `app/web/chat/models.py` | AGENT_TYPES 新增 `"quick_query"` | **修改** |
| `web_ui/src/components/NewChatDialog.vue` | 下拉菜单新增「快速查询」选项 | **修改** |
| `web_ui/src/views/ChatView.vue` | 可选：显示当前 Agent 类型标签 | **修改** |

---

### Task 1: 新增 QuickQuery 系统提示词

**Files:**
- Create: `app/prompt/quick_query.py`

**Interfaces:**
- Produces: `SYSTEM_PROMPT: str` — 含 `{directory}` 占位符，由 Agent 初始化时 format
- Produces: `NEXT_STEP_PROMPT: str` — 纯文本，无占位符

- [ ] **Step 1: 创建 `app/prompt/quick_query.py`**

```python
SYSTEM_PROMPT = """你是 QuickQuery，一个轻量数据查询助手，运行在 Sandbox 环境中。

## 核心行为准则

1. **直接给答案**：用户问什么数据，你就查什么。查完直接回复，不要延伸出图表或报告。
   如果用户明确要求图表，告知用户切换到「完整分析」模式更合适。

2. **追问先行**：遇到以下情况，**主动调用 ask_human 确认，不要猜测**：
   - 指标口径不清（如"销售额"是含税还是不含税）
   - 时间范围模糊（如"最近"、"上一段"）
   - 企业/项目名称不完整或存在歧义
   - 用户上传了文件但未说明要分析什么

3. **最少步骤**：目标是一次查询 + 一次 Python 计算即交付结果。
   确认需求后立即读取数据并计算，完成后立即 Terminate。

4. **数据溯源**：回复时说明数据来源（文件路径、筛选条件），让用户知道数据来自哪里。

# 数据与环境

1. 工作目录: {directory}；在此目录下读写文件
2. 公司数据目录: company_data_resource/；用户提到公司/企业/业务数据分析时，
   优先调用 company_data_lookup 工具检查是否有匹配的本地 CSV 数据
3. 如果 company_data_lookup 返回了匹配的数据文件，先告知用户找到了哪些文件，
   然后自动用 python_execute (pandas.read_csv) 加载并分析

## 工作流程

1. 收到用户查询 → 判断是否需要澄清
2. 如需澄清 → ask_human 询问
3. 如有公司数据需求 → CompanyDataLookup 查找本地文件
4. 用 python_execute 执行 pandas 读取+计算
5. 将计算结果清晰呈现给用户（文字描述或 Markdown 表格）→ Terminate

## 约束

- 不生成图表（你没有可视化工具）
- 不写分析报告，只返回查询结果
- 如果用户需求超出纯查询范围（要求趋势分析、预测、多维对比等），
  告知用户切换「完整分析」模式
"""

NEXT_STEP_PROMPT = """基于用户需求，直接查数据、给答案。

# 流程
1. 每一步主动选择最合适的工具（每次只选一个）。
2. 每次使用工具后，清晰解释执行结果并建议下一步。
3. 当 observation 中出现 Error 时，检查并修复。
4. 遇到不确定的信息，**立即调用 ask_human 询问用户**，不要猜测。
5. 查询结果清晰呈现后，调用 Terminate 结束任务。

# 注意
- 你是一个轻量查询助手，不要主动生成图表或分析报告
- 优先直接回答用户的数据问题，不要过度展开
- 如用户真的需要图表或多维分析，建议切换到「完整分析」模式
"""
```

- [ ] **Step 2: 验证文件语法**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "from app.prompt.quick_query import SYSTEM_PROMPT, NEXT_STEP_PROMPT; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add app/prompt/quick_query.py
git commit -m "feat(agent): 新增 QuickQuery 系统提示词"
```

---

### Task 2: 新增 QuickQuery Agent 类

**Files:**
- Create: `app/agent/quick_query.py`

**Interfaces:**
- Consumes: `SYSTEM_PROMPT`, `NEXT_STEP_PROMPT` from `app.prompt.quick_query`
- Consumes: `ToolCallAgent` from `app.agent.toolcall`
- Consumes: `CompanyDataLookup` from `app.tool.company_data_lookup`
- Consumes: `NormalPythonExecute` from `app.tool.chart_visualization.python_execute`
- Consumes: `AskHuman` from `app.tool.ask_human`
- Consumes: `Terminate`, `ToolCollection` from `app.tool`
- Produces: `QuickQuery` class — 供 `agent_runner.py` 实例化

- [ ] **Step 1: 创建 `app/agent/quick_query.py`**

```python
"""QuickQuery 轻量数据查询智能体。

专注于快速数据查询与简单计算，不生成图表和报告。
工具集仅包含 CompanyDataLookup、PythonExecute、AskHuman、Terminate。
"""
from typing import Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.logger import logger
from app.prompt.quick_query import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ask_human import AskHuman
from app.tool.chart_visualization.python_execute import NormalPythonExecute
from app.tool.company_data_lookup import CompanyDataLookup


class QuickQuery(ToolCallAgent):
    """轻量数据查询智能体，专注快速数据查询与简单计算。

    与 DataAnalysis 的区别：
    - 无 VisualizationPrepare / DataVisualization 工具
    - 提示词强调「直接给答案」和「追问先行」
    - max_steps 限制为 15（对比 DataAnalysis 的 60）
    """

    name: str = "quick_query"
    description: str = "轻量数据查询智能体，专注快速数据查询与简单计算，不生成图表和报告"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 15

    # Sandbox 注入（由 Web 层设置，可选）
    sandbox: Optional[object] = None
    _sandbox_workspace: str = ""

    # 工具集合：公司数据查询 + Python 执行 + 人工询问 + 终止
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            CompanyDataLookup(),
            NormalPythonExecute(),
            AskHuman(),
            Terminate(),
        )
    )

    def set_sandbox(
        self, sandbox: object, workspace: str = "/workspace", host_workspace: str = ""
    ) -> None:
        """注入 Sandbox 并同步到所有执行类工具。

        与 DataAnalysis.set_sandbox() 逻辑完全一致。

        Args:
            sandbox: DockerSandbox 实例
            workspace: 容器内工作目录路径，默认 /workspace
            host_workspace: 宿主机工作目录绝对路径（保留参数兼容性）
        """
        self.sandbox = sandbox
        self._sandbox_workspace = workspace

        # 修正 system_prompt 中的目录路径为容器内路径
        self.system_prompt = SYSTEM_PROMPT.format(directory=workspace)

        # 遍历所有工具，注入 sandbox 和 workspace 属性
        for tool in self.available_tools:
            if hasattr(tool, "sandbox"):
                tool.sandbox = sandbox
                logger.debug(f"Sandbox 已注入工具: {tool.name}")
            if hasattr(tool, "workspace_dir") and workspace:
                tool.workspace_dir = workspace
                logger.debug(f"Workspace 已注入工具: {tool.name} → {workspace}")
            # 修正发给 LLM 的工具描述中的宿主机路径 → 容器内路径
            if hasattr(tool, "parameters") and isinstance(tool.parameters, dict):
                code_desc = (
                    tool.parameters.get("properties", {})
                    .get("code", {})
                    .get("description", "")
                )
                if code_desc and str(config.workspace_root) in code_desc:
                    tool.parameters["properties"]["code"]["description"] = (
                        code_desc.replace(str(config.workspace_root), workspace)
                    )
                    logger.debug(f"ToolDesc 已更新: {tool.name} → {workspace}")
```

- [ ] **Step 2: 验证导入和实例化**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "from app.agent.quick_query import QuickQuery; a = QuickQuery(); print(f'name={a.name}, tools={len(a.available_tools.tools)}, max_steps={a.max_steps}')"
```

Expected: `name=quick_query, tools=4, max_steps=15`

- [ ] **Step 3: 提交**

```bash
git add app/agent/quick_query.py
git commit -m "feat(agent): 新增 QuickQuery 轻量数据查询智能体"
```

---

### Task 3: 扩展 agent_runner 工厂支持 QuickQuery

**Files:**
- Modify: `app/web/agent_runner.py`

**Interfaces:**
- Consumes: `QuickQuery` from `app.agent.quick_query`
- Produces: `ObservableQuickQuery` class
- Modifies: `create_observable_agent()` — 新增 `elif agent_type == "quick_query"` 分支

- [ ] **Step 1: 在 `app/web/agent_runner.py` 顶部添加导入**

打开 `app/web/agent_runner.py`，在第 11 行（`from app.agent.data_analysis import DataAnalysis` 之后）插入：

```python
from app.agent.quick_query import QuickQuery
```

- [ ] **Step 2: 在文件末尾（`ObservableDataAnalysis` 类之后、工厂函数之前）添加 ObservableQuickQuery 类**

在 `class ObservableDataAnalysis(DataAnalysis):` 类定义之后（约第 160 行）、`# ── Agent 工厂 ──` 注释之前插入：

```python
# ── ObservableQuickQuery ───────────────────────────────


class ObservableQuickQuery(QuickQuery):
    """QuickQuery 的事件注入子类。

    与 ObservableManus / ObservableDataAnalysis 完全相同的 emit 逻辑。
    """

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

    async def run(self, request: str | None = None) -> str:
        try:
            result = await super().run(request)
            await _emit(self.event_queue, "done", {"reason": "completed"})
            return result
        except Exception as exc:
            await _emit(self.event_queue, "error", {"message": str(exc)})
            await _emit(self.event_queue, "done", {"reason": "error"})
            raise
```

- [ ] **Step 3: 在工厂函数中新增 QuickQuery 分支**

在 `create_observable_agent()` 函数中（约第 186 行），在 `elif agent_type == "data_analysis":` 分支之后、`else:` 之前插入：

```python
    elif agent_type == "quick_query":
        agent = ObservableQuickQuery()
```

- [ ] **Step 4: 验证导入和创建**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "import asyncio; from app.web.agent_runner import create_observable_agent; async def t(): q = asyncio.Queue(); a = await create_observable_agent('quick_query', q); print(f'name={a.name}, tools={len(a.available_tools.tools)}, max_steps={a.max_steps}'); asyncio.get_event_loop().run_until_complete(t())"
```

Expected: `name=quick_query, tools=4, max_steps=15`

- [ ] **Step 5: 提交**

```bash
git add app/web/agent_runner.py
git commit -m "feat(web): agent_runner 工厂支持 QuickQuery"
```

---

### Task 4: 注册 quick_query 到会话模型

**Files:**
- Modify: `app/web/chat/models.py:10`

**Interfaces:**
- Modifies: `AGENT_TYPES` set — 新增 `"quick_query"`

- [ ] **Step 1: 修改 AGENT_TYPES**

将 `app/web/chat/models.py` 第 10 行：

```python
AGENT_TYPES = {"general", "data_analysis"}
```

改为：

```python
AGENT_TYPES = {"general", "data_analysis", "quick_query"}
```

- [ ] **Step 2: 验证数据库模型**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "from app.web.chat.models import AGENT_TYPES; assert 'quick_query' in AGENT_TYPES; print(f'AGENT_TYPES={AGENT_TYPES}')"
```

Expected: `AGENT_TYPES={'general', 'quick_query', 'data_analysis'}`

- [ ] **Step 3: 提交**

```bash
git add app/web/chat/models.py
git commit -m "feat(web): AGENT_TYPES 注册 quick_query"
```

---

### Task 5: 前端 NewChatDialog 新增「快速查询」选项

**Files:**
- Modify: `web_ui/src/components/NewChatDialog.vue:7-8`

**Interfaces:**
- Produces: `<option value="quick_query">` 在 `<select>` 中

- [ ] **Step 1: 添加新选项**

在 `web_ui/src/components/NewChatDialog.vue` 的 `<select>` 中，在第 8 行 `</select>` 之前插入：

```html
        <option value="quick_query">⚡ 快速查询</option>
```

完整 `<select>` 变为：

```html
<select v-model="selected" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4">
  <option value="general">🤖 通用 Agent (Manus)</option>
  <option value="data_analysis">📊 数据分析 Agent</option>
  <option value="quick_query">⚡ 快速查询</option>
</select>
```

- [ ] **Step 2: 构建前端验证**

```bash
cd web_ui && npm run build
```

Expected: 构建成功，无 TypeScript 错误。

- [ ] **Step 3: 提交**

```bash
git add web_ui/src/components/NewChatDialog.vue
git commit -m "feat(ui): 新建会话对话框新增「快速查询」Agent 选项"
```

---

### Task 6: （可选）ChatView 显示 Agent 类型标签

**Files:**
- Modify: `web_ui/src/views/ChatView.vue`

**Interfaces:**
- Consumes: `currentAgentType` 已存在的 computed 属性

- [ ] **Step 1: 确认 ChatView 已传递 agentType 给 ChatWindow**

检查 `web_ui/src/views/ChatView.vue` 第 14 行，确认 `:agentType="currentAgentType"` 已传递。当前代码已包含 — **无需改动**。

确认 `ChatWindow` 组件已接收 `agentType` prop 并展示。如果 ChatWindow 未展示 agent 类型标签，可选择添加。

- [ ] **Step 2: 验证前端构建**

```bash
cd web_ui && npm run build
```

Expected: 构建成功。

- [ ] **Step 3: 提交（如有改动）**

```bash
git add web_ui/src/views/ChatView.vue
git commit -m "feat(ui): ChatView 显示 Agent 类型标签"
```

---

### Task 7: 端到端回归验证

- [ ] **Step 1: 运行现有测试**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/ -v --timeout=60 2>&1 | Select-Object -Last 50
```

Expected: 已有测试全部通过（QuickQuery 不引入回归）。

- [ ] **Step 2: 运行 QuickQuery 导入冒烟验证**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
from app.agent.quick_query import QuickQuery
from app.prompt.quick_query import SYSTEM_PROMPT, NEXT_STEP_PROMPT
from app.web.chat.models import AGENT_TYPES

# 验证能正常创建实例
a = QuickQuery()
assert a.name == 'quick_query'
assert a.max_steps == 15
assert len(a.available_tools.tools) == 4

# 验证工具名称
tool_names = {t.name for t in a.available_tools.tools}
assert tool_names == {'company_data_lookup', 'python_execute', 'ask_human', 'terminate'}, f'Unexpected tools: {tool_names}'

# 验证 AGENT_TYPES 注册
assert 'quick_query' in AGENT_TYPES

print('ALL CHECKS PASSED')
"
```

Expected: `ALL CHECKS PASSED`

- [ ] **Step 3: 提交最终验证结果**

```bash
git add -A
git diff --cached --stat
git commit -m "test: QuickQuery 端到端回归验证通过"
```
