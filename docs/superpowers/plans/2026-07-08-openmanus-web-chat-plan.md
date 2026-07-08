# OpenManus Web 聊天界面 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OpenManus 构建 WebSocket 驱动的 Web 聊天界面，实时展示 agent 每步思考过程和工具调用结果。

**Architecture:** FastAPI + WebSocket 后端 → `ObservableManus(Manus)` 子类通过 `asyncio.Queue` 推送事件 → 前端 Alpine.js + Tailwind CDN 单页渲染。

**Tech Stack:** FastAPI, WebSocket, asyncio, Alpine.js 3.x CDN, Tailwind CSS CDN, marked.js CDN

## 全局约束

- Python 3.12（`C:\Users\hyh\anaconda3\envs\open_manus\python.exe`）
- 不修改 `app/agent/`、`app/tool/`、`app/config.py`、`app/llm.py`、`main.py` 等现有代码
- 现有 `python main.py` 运行方式不受影响
- Tailwind 仅用内置色阶（gray/blue/yellow/green/red），不引入自定义颜色
- 启动入口 `python web_run.py`，端口 8080
- 配置复用 `config/config.toml`

---

### Task 1: 项目脚手架 — `__init__.py` 和 `web_run.py`

**Files:**
- Create: `app/web/__init__.py`
- Create: `web_run.py`

**Interfaces:**
- Produces: `web_run.py` 入口脚本，可被 `python web_run.py` 直接执行，内部 import `app.web.server:app`

- [ ] **Step 1: 创建 `app/web/__init__.py`**

```python
# app/web/__init__.py
# OpenManus Web Chat 模块
```

- [ ] **Step 2: 创建 `web_run.py`**

```python
# web_run.py — OpenManus Web 聊天界面启动入口
"""启动 OpenManus Web 聊天服务器。

Usage:
    python web_run.py
    # 访问 http://localhost:8080
"""

import uvicorn


def main():
    uvicorn.run(
        "app.web.server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 验证 import 路径正确**（无测试，仅静态检查语法）

```powershell
python -c "import ast; ast.parse(open('web_run.py').read()); print('OK')"
python -c "import ast; ast.parse(open('app/web/__init__.py').read()); print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add app/web/__init__.py web_run.py
git commit -m "feat(web): 添加 web 模块脚手架和启动入口"
```

---

### Task 2: ObservableManus 事件发射器

**Files:**
- Create: `app/web/agent_runner.py`

**Interfaces:**
- Produces: `class ObservableManus(Manus)` — 继承 Manus 的子类
  - `event_queue: asyncio.Queue` — 注入的事件队列（属性，default=None）
  - `async _emit(type: str, data: dict) -> None` — 推送事件到队列，event_queue 为 None 时静默跳过
  - `async step() -> str` — 覆写：推送 step_start + 委托父类
  - `async think() -> bool` — 覆写：推送 thinking/assistant + 委托父类
  - `async execute_tool(command: ToolCall) -> str` — 覆写：推送 tool_start/tool_end + 委托父类
  - `async run(request: str | None) -> str` — 覆写：包裹异常，推送 done/error
- Consumes: `app.agent.manus.Manus`（继承）、`app.schema.AgentState`（状态检测）

- [ ] **Step 1: 编写 `app/web/agent_runner.py` 完整实现**

```python
"""ObservableManus — Manus agent 的事件注入包装器。

通过在关键生命周期节点覆写父类方法，将执行过程以事件流形式
推送到 asyncio.Queue，供 WebSocket 服务消费。
"""

import asyncio
from typing import Any, Optional

from app.agent.manus import Manus
from app.schema import AgentState, ToolCall


class ObservableManus(Manus):
    """Manus 的子类，在执行循环关键节点推送事件。

    用法:
        queue = asyncio.Queue()
        agent = await ObservableManus.create()
        agent.event_queue = queue
        asyncio.create_task(agent.run(prompt))
        # 另一个协程从 queue 中消费事件
    """

    event_queue: Optional[asyncio.Queue] = None

    async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """推送事件到队列。event_queue 为 None 时静默跳过。"""
        if self.event_queue is not None:
            payload = {"type": event_type, **data}
            await self.event_queue.put(payload)

    async def step(self) -> str:
        """执行一步：先推送 step_start 事件，再委托父类。"""
        await self._emit(
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        """思考阶段：调用父类 think() 后，推送 thinking 或 assistant 事件。"""
        should_act = await super().think()

        # 从最后一条 assistant 消息中提取思考内容
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

        # 有思考内容或工具调用时才推送
        if thinking_content or tool_calls_data:
            await self._emit(
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        # 无工具调用但有内容 → agent 的最终回复
        if not should_act and thinking_content and not tool_calls_data:
            await self._emit("assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        """执行工具：推送 tool_start → 执行 → 推送 tool_end。"""
        await self._emit(
            "tool_start",
            {
                "tool": command.function.name,
                "args": command.function.arguments,
            },
        )
        try:
            result = await super().execute_tool(command)
            await self._emit(
                "tool_end",
                {"tool": command.function.name, "result": str(result), "ok": True},
            )
            return result
        except Exception as exc:
            await self._emit(
                "tool_end",
                {
                    "tool": command.function.name,
                    "error": str(exc),
                    "ok": False,
                },
            )
            raise

    async def run(self, request: Optional[str] = None) -> str:
        """运行 agent，推送 done 事件。异常时推送 error。"""
        try:
            result = await super().run(request)
            await self._emit("done", {"reason": "completed"})
            return result
        except Exception as exc:
            await self._emit("error", {"message": str(exc)})
            await self._emit("done", {"reason": "error"})
            raise
```

- [ ] **Step 2: 验证语法和 import**

```powershell
python -c "import ast; ast.parse(open('app/web/agent_runner.py').read()); print('Syntax OK')"
python -c "from app.web.agent_runner import ObservableManus; print('Import OK')"
```

- [ ] **Step 3: 提交**

```bash
git add app/web/agent_runner.py
git commit -m "feat(web): 添加 ObservableManus 事件发射器"
```

---

### Task 3: FastAPI + WebSocket 服务器

**Files:**
- Create: `app/web/server.py`

**Interfaces:**
- Produces: FastAPI `app` 实例，含：
  - `GET /` → `FileResponse("app/web/static/index.html")`
  - `WebSocket /ws` → 接收 prompt，创建 ObservableManus，流式推送事件
  - `StaticFiles` 挂载 `/static` → `app/web/static/`
- Consumes: `app.web.agent_runner.ObservableManus`（Task 2）

- [ ] **Step 1: 编写 `app/web/server.py`**

```python
"""FastAPI 服务器 — OpenManus Web 聊天后端。

端点:
    GET  /        → 返回聊天前端页面
    GET  /static/ → 静态资源目录（挂载到 app/web/static/）
    WS   /ws      → WebSocket 端点，接收 prompt，流式推送 agent 事件
"""

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.web.agent_runner import ObservableManus


# ── FastAPI 应用 ──────────────────────────────────────────────

app = FastAPI(title="OpenManus Chat", version="0.1.0")

# 静态资源目录
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 路由 ──────────────────────────────────────────────────────

@app.get("/")
async def root():
    """返回聊天前端页面。"""
    index_path = STATIC_DIR / "index.html"
    return FileResponse(str(index_path))


# ── WebSocket 端点 ────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    """WebSocket 聊天端点。

    1. 接收客户端发来的 prompt 文本
    2. 创建 ObservableManus agent
    3. 并行：agent 执行 + 从 event_queue 消费事件推送客户端
    4. agent 完成后关闭连接
    """
    await ws.accept()

    try:
        # 接收 prompt
        prompt = await ws.receive_text()
        if not prompt or not prompt.strip():
            await ws.send_json(
                {"type": "error", "message": "Empty prompt"}
            )
            await ws.close()
            return
    except WebSocketDisconnect:
        return

    # 创建 agent 和事件队列
    agent = await ObservableManus.create()
    queue: asyncio.Queue = asyncio.Queue()
    agent.event_queue = queue

    # 启动 agent 执行任务
    agent_task = asyncio.create_task(agent.run(prompt))

    # 消费事件队列并推送给前端
    try:
        while not agent_task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                # 队列暂时为空，继续循环（除非 agent 已结束且队列空了）
                continue

        # 确保 agent 任务完成（可能已经 done）
        await agent_task
    except WebSocketDisconnect:
        # 客户端断开连接，取消 agent
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
    except Exception as exc:
        # 未预期的错误
        try:
            await ws.send_json(
                {"type": "error", "message": f"Server error: {str(exc)}"}
            )
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
```

- [ ] **Step 2: 验证语法和 import**

```powershell
python -c "import ast; ast.parse(open('app/web/server.py').read()); print('Syntax OK')"
python -c "from app.web.server import app; print('Import OK')"
```

- [ ] **Step 3: 提交**

```bash
git add app/web/server.py
git commit -m "feat(web): 添加 FastAPI + WebSocket 服务器"
```

---

### Task 4: 前端 HTML 页面

**Files:**
- Create: `app/web/static/index.html`

**Interfaces:**
- Consumes: WebSocket `/ws` 端点（Task 3 定义），事件类型见设计文档 §5
- Produces: 自包含单页聊天界面，Alpine.js + Tailwind CDN + marked.js CDN

- [ ] **Step 1: 编写 `app/web/static/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenManus Chat</title>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  /* 滚动条美化 */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
  /* 代码块样式 */
  pre { background: #1f2937; color: #e5e7eb; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
  pre code { background: none; padding: 0; }
  code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
  /* 工具卡片过渡动画 */
  .tool-card { transition: border-color 0.3s ease; }
  /* spinner 动画 */
  @keyframes spin { to { transform: rotate(360deg); } }
  .animate-spin { animation: spin 0.8s linear infinite; }
</style>
</head>
<body class="bg-gray-50 h-screen flex flex-col">

<!-- ═══ 顶栏 ═══ -->
<header class="bg-white border-b border-gray-200 shadow-sm px-6 py-3 flex items-center justify-between shrink-0">
  <div class="flex items-center gap-2">
    <span class="text-xl">🤖</span>
    <h1 class="text-lg font-semibold text-gray-800">OpenManus Chat</h1>
  </div>
  <div class="flex items-center gap-2">
    <span x-show="running" class="flex items-center gap-1 text-sm text-yellow-600">
      <span class="animate-spin inline-block w-3 h-3 border-2 border-yellow-600 border-t-transparent rounded-full"></span>
      运行中
    </span>
    <span x-show="!running && connected" class="text-sm text-green-600">⚡ 就绪</span>
    <span x-show="!connected" class="text-sm text-gray-400">未连接</span>
  </div>
</header>

<!-- ═══ 消息区 ═══ -->
<main
  class="flex-1 overflow-y-auto px-4 py-6 space-y-4"
  x-data="chat()"
  x-ref="scrollContainer"
  id="app"
>
  <!-- 空状态 -->
  <div x-show="messages.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
    <span class="text-5xl mb-4">🤖</span>
    <p class="text-lg">OpenManus Chat 已就绪</p>
    <p class="text-sm mt-1">在下方输入任务，开始与 AI Agent 对话</p>
  </div>

  <!-- 消息列表 -->
  <template x-for="(msg, idx) in messages" :key="idx">
    <div>

      <!-- 用户消息 -->
      <div x-show="msg.type === 'user'" class="flex justify-end mb-4">
        <div class="bg-blue-500 text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] shadow-sm">
          <p class="whitespace-pre-wrap text-sm" x-text="msg.content"></p>
        </div>
      </div>

      <!-- 步骤指示器 -->
      <div x-show="msg.type === 'step_start'" class="text-center mb-3">
        <span class="text-xs text-gray-400 bg-gray-100 rounded-full px-3 py-1"
          x-text="'Step ' + msg.step + '/' + msg.max_steps"></span>
      </div>

      <!-- 思考气泡 -->
      <div x-show="msg.type === 'thinking' && msg.content" class="mb-3">
        <div class="bg-gray-100 border border-gray-200 rounded-xl px-4 py-2.5 max-w-[85%]">
          <button
            class="flex items-center gap-1.5 text-xs text-gray-500 font-medium mb-1 cursor-pointer w-full text-left"
            @click="msg._expanded = !msg._expanded"
          >
            <span>🤔 思考过程</span>
            <svg class="w-3 h-3 transition-transform" :class="msg._expanded ? 'rotate-180' : ''"
              viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd"/>
            </svg>
          </button>
          <div x-show="msg._expanded" class="text-sm text-gray-600 whitespace-pre-wrap leading-relaxed"
            x-html="renderMarkdown(msg.content)"></div>
        </div>
      </div>

      <!-- 工具卡片 -->
      <div x-show="msg.type === 'tool_start' || msg.type === 'tool_end'"
        class="mb-3"
        :class="{
          'border-l-4 border-yellow-400': msg.state === 'running' || msg.type === 'tool_start',
          'border-l-4 border-green-400': msg.state === 'done',
          'border-l-4 border-red-400': msg.state === 'error'
        }">
        <div class="bg-white rounded-r-lg border border-l-0 border-gray-200 px-4 py-2.5 shadow-sm max-w-[85%]">
          <div class="flex items-center gap-2">
            <span class="text-sm">🔧</span>
            <span class="text-sm font-medium text-gray-700" x-text="msg.tool"></span>
            <span x-show="msg.state === 'running' || msg.type === 'tool_start'" class="animate-spin inline-block w-3 h-3 border-2 border-yellow-500 border-t-transparent rounded-full"></span>
            <span x-show="msg.state === 'done'" class="text-green-500 text-xs">✅</span>
            <span x-show="msg.state === 'error'" class="text-red-500 text-xs">❌</span>
          </div>
          <div x-show="msg.args" class="mt-1.5 text-xs text-gray-500 font-mono bg-gray-50 rounded px-2 py-1 overflow-x-auto"
            x-text="msg.args"></div>
          <div x-show="msg.result" class="mt-1.5 text-sm text-gray-700 whitespace-pre-wrap max-h-40 overflow-y-auto"
            x-text="msg.result"></div>
          <div x-show="msg.error" class="mt-1.5 text-sm text-red-600" x-text="msg.error"></div>
        </div>
      </div>

      <!-- Agent 回复 -->
      <div x-show="msg.type === 'assistant'" class="mb-4">
        <div class="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 max-w-[85%] shadow-sm">
          <div class="text-sm text-gray-800 leading-relaxed" x-html="renderMarkdown(msg.content)"></div>
        </div>
      </div>

      <!-- 错误消息 -->
      <div x-show="msg.type === 'error'" class="mb-3">
        <div class="bg-red-50 border border-red-200 rounded-xl px-4 py-2.5 max-w-[85%]">
          <span class="text-sm text-red-700" x-text="'⚠️ ' + msg.message"></span>
        </div>
      </div>

      <!-- 完成标记 -->
      <div x-show="msg.type === 'done'" class="text-center my-3">
        <span class="text-xs text-gray-400">— 任务结束 —</span>
      </div>

    </div>
  </template>
</main>

<!-- ═══ 输入区 ═══ -->
<footer class="bg-white border-t border-gray-200 px-4 py-3 shrink-0">
  <div class="max-w-3xl mx-auto flex gap-2">
    <input
      type="text"
      x-model="input"
      @keydown.enter="send()"
      :disabled="running"
      placeholder="输入你的任务，按 Enter 发送..."
      class="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
    >
    <button
      @click="send()"
      :disabled="running || !input.trim()"
      class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed shrink-0"
    >发送 ▶</button>
  </div>
</footer>

<!-- ═══ Alpine.js 组件 ═══ -->
<script>
function chat() {
  return {
    messages: [],
    input: '',
    connected: false,
    running: false,
    ws: null,

    send() {
      const prompt = this.input.trim();
      if (!prompt || this.running) return;

      this.connected = true;
      this.running = true;
      this.messages = [{ type: 'user', content: prompt }];
      this.input = '';

      const wsUrl = `ws://${location.host}/ws`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.ws.send(prompt);
      };

      this.ws.onmessage = (e) => {
        const event = JSON.parse(e.data);

        if (event.type === 'tool_end') {
          // 找到匹配的 tool_start 并内联更新
          for (let i = this.messages.length - 1; i >= 0; i--) {
            const m = this.messages[i];
            if (m.type === 'tool_start' && m.tool === event.tool && !m.state) {
              this.messages[i] = {
                ...m,
                result: event.result || null,
                error: event.error || null,
                ok: event.ok,
                state: event.ok ? 'done' : 'error',
              };
              this.scrollBottom();
              return;
            }
          }
        }

        this.messages.push(event);
        this.scrollBottom();
      };

      this.ws.onclose = () => {
        this.running = false;
      };

      this.ws.onerror = () => {
        this.running = false;
        this.messages.push({ type: 'error', message: 'WebSocket 连接失败，请检查服务器是否运行' });
      };
    },

    scrollBottom() {
      this.$nextTick(() => {
        const el = this.$refs.scrollContainer;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },

    renderMarkdown(text) {
      if (!text) return '';
      try {
        return marked.parse(text);
      } catch (e) {
        return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
      }
    }
  };
}
</script>

</body>
</html>
```

- [ ] **Step 2: 提交**

```bash
git add app/web/static/index.html
git commit -m "feat(web): 添加前端聊天页面（Alpine.js + Tailwind）"
```

---

### Task 5: 端到端集成验证

**Files:**
- 无新文件。通过手动启动服务器，浏览器访问验证完整流程。

**依赖:** Task 1–4 全部完成。

- [ ] **Step 1: 启动服务器**

```powershell
python web_run.py
```

预期输出:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8080
```

- [ ] **Step 2: 浏览器访问 `http://localhost:8080`，验证页面加载**

检查点：
- 页面标题 "OpenManus Chat"
- 顶栏显示 "🤖 OpenManus Chat" + 状态 "未连接"
- 底部输入框 + 发送按钮可见
- 中间显示引导文字 "OpenManus Chat 已就绪"

- [ ] **Step 3: 发送简单 prompt 测试完整流程**

输入: `请用 Python 打印 "Hello OpenManus"`

验证点：
- 用户消息气泡出现（蓝色右边）
- 步骤指示器 "Step 1/20" 出现
- 思考气泡出现（可展开/折叠）
- 工具卡片出现：PythonExecute（先黄色左边框 → 完成后变绿色左边框）
- Agent 回复 Markdown 渲染正确
- 完成后显示 "— 任务结束 —"
- 状态回到 "就绪"，可以再次输入

- [ ] **Step 4: 测试错误处理**

空输入按发送 → 不应发送（按钮 disabled）

关闭服务器后尝试发送 → 前端显示红色错误提示 "WebSocket 连接失败"

- [ ] **Step 5: `Ctrl+C` 停止服务器，确认资源清理**

确认 Agent 资源（MCP 连接、浏览器实例）正常释放。

- [ ] **Step 6: 确认现有 `main.py` 不受影响**

```powershell
python main.py --prompt "say hello"
```

预期：正常运行，不受新模块影响。

- [ ] **Step 7: 提交**（如有微调）

```bash
git add -A
git commit -m "chore(web): 端到端验证通过，微调"
```
