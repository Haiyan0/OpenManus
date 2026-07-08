# OpenManus Web 聊天界面 - 设计文档

> 日期：2026-07-08 | 状态：已确认

## 1. 目标

为 OpenManus 构建一个基于 Web 的交互式聊天界面，类似 OpenClaw 的网页式前端。用户通过浏览器与 Manus Agent 对话，实时看到每一步的思考过程、工具调用及最终回复。

## 2. 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| 后端框架 | FastAPI（已有依赖）| 高性能异步，原生 WebSocket 支持 |
| 实时通信 | WebSocket | 双向流式推送 agent 事件 |
| 前端 | Alpine.js + Tailwind CSS CDN | 零构建步骤，单文件 HTML |
| Markdown | marked.js CDN | 渲染 agent 回复中的富文本 |
| Agent 集成 | 子类 `ObservableManus(Manus)` | 不侵入现有代码，通过覆写注入事件 |

## 3. 文件结构（新增 5 个文件）

```
C:\Code\OpenManus\
  app\web\
    __init__.py              # 空文件，标记为 Python 包
    server.py                # FastAPI 应用 + WebSocket /ws 端点 + GET / 首页
    agent_runner.py          # ObservableManus 子类，事件发射核心
    static\
      index.html             # 单页前端（Alpine.js + Tailwind CDN）
  web_run.py                 # 启动入口：uvicorn.run(...)
```

## 4. 架构

```
浏览器 (Alpine.js + Tailwind CDN + marked.js)
    │  WebSocket /ws
    ▼
FastAPI (server.py)
    │
    ├── GET / → index.html（静态页面）
    │
    ├── WebSocket /ws
    │     │  接收用户 prompt
    │     │  创建 ObservableManus agent
    │     │  从 event_queue 读取事件 → send_json 推给前端
    │     │
    │     └── ObservableManus (agent_runner.py)
    │            │  继承 Manus，覆写 step/think/execute_tool
    │            │  在每个关键节点向 event_queue 推送事件
    │            │
    │            └── Manus → ToolCallAgent → ReActAgent → BaseAgent
    │                 （现有代码，不做任何修改）
    │
    └── StaticFiles("/static") → app/web/static/
```

## 5. 事件模型

### 事件类型

| 事件 | 触发时机 | 负载字段 | 前端展示 |
|------|---------|---------|---------|
| `step_start` | 每步开始 | `step`, `max_steps` | 灰色步骤指示器 "Step 1/20" |
| `thinking` | LLM 返回思考内容 | `content`, `tool_calls` | 可折叠灰色气泡 |
| `tool_start` | 工具开始执行 | `tool`, `args` | 黄色左边框卡片 + spinner |
| `tool_end` | 工具执行完毕 | `tool`, `result`, `ok`, `error?` | 绿/红色左边框 + 结果摘要 |
| `assistant` | Agent 完成（无工具调用的内容） | `content` | 白色气泡 Markdown |
| `error` | 任何步骤异常 | `message` | 红色错误提示 |
| `done` | Agent 运行结束 | `reason` | 结束标记 |

### 事件注入方式（不侵入现有代码）

在 `agent_runner.py` 中定义 `ObservableManus(Manus)`：

- `step()` → 覆写：先 `emit("step_start", ...)` 再 `super().step()`
- `think()` → 覆写：在 `super().think()` 返回后，从 `self.tool_calls` 和 `response.content` 获取数据，`emit("thinking", ...)`
- `execute_tool()` → 覆写：包裹 try-catch，执行前后分别 `emit("tool_start")` / `emit("tool_end")`
- 最后检测 `AgentState.FINISHED` → `emit("done")`
- 通过 `asyncio.Queue` 传递事件，server.py 的 WebSocket 协程从中消费

## 6. 前端 UI 设计

### 布局

```
┌─────────────────────────────────────────┐
│  🤖 OpenManus Chat                    ⚡ │  顶栏：名称 + 运行状态
├─────────────────────────────────────────┤
│                                         │
│  ┌─ Step 1/20 ──────────────────────┐  │
│  │  🤔 思考过程          [展开 ▼]   │  │  可折叠灰色气泡
│  │  用户要写计算器，我需要...       │  │
│  ├───────────────────────────────────┤  │
│  │  🔧 PythonExecute               │  │  工具卡片
│  │    执行中... ⟳                   │  │  ├─ 执行中：黄色左边框 + spinner
│  │    ✅ 输出: Hello World          │  │  └─ 完成：绿色左边框 + 结果
│  ├───────────────────────────────────┤  │
│  │  🔧 StrReplaceEditor            │  │
│  │    ✅ 文件已更新                 │  │
│  └───────────────────────────────────┘  │
│                                         │
│  💬 我已经创建了计算器，代码如下...    │  白色气泡 Markdown
│                                         │
├─────────────────────────────────────────┤
│  [输入你的任务...]            [发送 ▶] │  底部输入栏
└─────────────────────────────────────────┘
```

### 色彩方案（Tailwind 语义色，无自定义变量冲突）

| 元素 | Tailwind Class |
|------|---------------|
| 页面背景 | `bg-gray-50` |
| 顶栏 | `bg-white border-b border-gray-200 shadow-sm` |
| 用户消息气泡 | `bg-blue-500 text-white rounded-lg` |
| Agent 回复气泡 | `bg-white border border-gray-200 rounded-lg` |
| Thinking 气泡 | `bg-gray-100 text-gray-600 border border-gray-200` |
| 工具卡片-执行中 | `border-l-4 border-yellow-400 bg-white` |
| 工具卡片-完成 | `border-l-4 border-green-400 bg-white` |
| 工具卡片-出错 | `border-l-4 border-red-400 bg-white` |
| 步骤指示器 | `text-gray-400 text-sm` |
| 输入框 | `border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500` |
| 发送按钮 | `bg-blue-500 hover:bg-blue-600 text-white rounded-lg` |

全部使用 Tailwind 内置色阶（gray/blue/yellow/green/red），不引入自定义颜色，避免与项目其他部分或 Tailwind preflight 冲突。

### CDN 依赖

```html
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
```

可选（代码高亮）：
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github.min.css">
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js"></script>
```

## 7. 数据流

```
用户输入 prompt
  → WebSocket 收到文本
    → server.py 创建 ObservableManus + event_queue
      → asyncio.create_task(agent.run(prompt))
        → agent.step() 每步推送事件到 queue
          → WebSocket 协程从 queue 取事件 → send_json 给前端
            → Alpine.js 追加到 messages 数组 → 响应式渲染
  → agent 完成 → emit("done") → WebSocket 关闭
```

## 8. 启动方式

```bash
python web_run.py
# 访问 http://localhost:8080
```

配置使用现有 `config/config.toml`，无需额外配置。

## 9. 错误处理

- **Agent 执行异常**：捕获后 `emit("error", {"message": str(e)})`，前端显示红色提示
- **WebSocket 断连**：前端 `onclose` 重新连接 + 显示"连接断开"提示
- **LLM Token 超限**：现有 `TokenLimitExceeded` 机制已处理，转为 `done` 事件
- **空 prompt**：前端验证，不允许发送空白消息

## 10. 兼容性

- **浏览器**：Chrome/Firefox/Edge 最新两个大版本
- **Python**：3.12（现有环境）
- **不做修改的现有代码**：`app/agent/`、`app/tool/`、`app/config.py`、`app/llm.py`、`main.py` 等全部不改
- **现有 `main.py` 和 `python main.py` 运行方式不受影响**

## 11. 不做的事情（YAGNI）

- 不做多会话管理（每次刷新页面是新的会话）
- 不做历史记录持久化
- 不做用户认证
- 不做文件上传
- 不做多 Agent 编排前端（只接入 Manus）
- 不做移动端适配（桌面优先）
