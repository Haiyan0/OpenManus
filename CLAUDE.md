# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中编写代码时提供指导。仓库工作指南的补充（安装陷阱、lint、测试要点）见 `AGENTS.md`。

## Python 环境

当前机台 Python 路径：**C:\Users\hyh\anaconda3\envs\open_manus\python.exe**（conda 环境，勿用系统 `python` 泛指）

当前工作项目目录：**C:\Code\OpenManus**

脚本运行环境：**Powershell**

运行系统：**win11 系统**

## 中文交流规范

- 计划、审查和逻辑解释必须使用**中文**
- 代码注释使用**简体中文**
- 代码标识符保持英文

## 工作流程

1. **开始任务前**: 先确定流程节点和验收计划，以中文展示步骤状态（已完成/进行中/待处理）
2. **Karpathy 准则**: 先思考再编码、极简实现、精确定位修改、目标驱动验收

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 项目概述

OpenManus 是一个受 Manus 启发的开源 AI 智能体框架。它实现了基于 ReAct 模式的智能体，通过工具调用（兼容 OpenAI 的函数调用）来自主完成用户任务——浏览网页、执行 Python、编辑文件、搜索以及与远程 MCP 服务器交互。

本仓库在 upstream（FoundationAgents/OpenManus）基础上深度定制，本地扩展方向：

- **Web 聊天界面** — 多用户 FastAPI 后端（`app/web/`）+ Vue3 前端（`web_ui/`），WebSocket 流式对话，MySQL 持久化 + JWT 认证
- **企业数据查询** — `CompanyDataLookup` 工具（MySQL / 本地 CSV 双模式）+ QuickQuery / DataAnalysis 智能体
- **公众号发布** — WechatPublish 智能体 + WechatPublishTool（bun 脚本，依赖自包含）
- **Docker 沙箱** — Web 层可为智能体注入沙箱，隔离执行 Python/文件操作
- **多环境配置** — `OPENMANUS_ENV` 选择 `config/config_{env}.toml`（默认 dev），入口脚本经 `entry.py` 桥接

## 构建与运行命令

### 安装依赖

```bash
# 通用方式（推荐使用 uv）
uv venv --python 3.12
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
playwright install           # 可选，用于浏览器自动化
```

本机台已配置 conda 环境 `open_manus`，无需重复安装。

### 入口脚本

所有入口接受可选位置参数 `[dev|test]` 选择部署环境（经 `entry.py` 桥接，默认 `dev`）：

| 命令                           | 用途                    |
| ------------------------------ | ----------------------- |
| `python main.py [dev           | test] [--prompt "..."]` |
| `python run_flow.py [dev       | test]`                  |
| `python web_run.py [dev        | test]`                  |
| `python run_mcp.py [dev        | test]`                  |
| `python run_mcp_server.py [dev | test]`                  |

### 测试

```bash
# 运行全部测试
pytest tests/

# 运行单个测试文件
pytest tests/sandbox/test_sandbox.py -v

# 运行单个测试
pytest tests/sandbox/test_sandbox.py::test_sandbox_python_execution -v
```

`pytest.ini` 已启用 `asyncio_mode = auto`，异步测试无需显式 `@pytest.mark.asyncio`。沙箱测试需 Docker Desktop 运行中；web 测试依赖 `[web]` MySQL 配置。

## 架构

### 智能体类继承层次

```
BaseAgent (app/agent/base.py)
  └── ReActAgent (app/agent/react.py) — 引入 think() + act() 循环
        └── ToolCallAgent (app/agent/toolcall.py) — LLM 工具/函数调用
              ├── Manus (app/agent/manus.py) — 通用型：PythonExecute、
              │     BrowserUseTool、StrReplaceEditor、AskHuman，+ 动态 MCP 工具
              ├── DataAnalysis (app/agent/data_analysis.py) — 数据分析：
              │     NormalPythonExecute、VisualizationPrepare、DataVisualization
              ├── QuickQuery (app/agent/quick_query.py) — 轻量数据查询：
              │     CompanyDataLookup、NormalPythonExecute、AskHuman、Terminate
              │     （max_steps=15，不生成图表，强调直接给答案）
              └── WechatPublish (app/agent/wechat_publish.py) — 公众号发布：
                    WechatPublishTool、NormalPythonExecute、AskHuman、Terminate
                    （max_steps=30，发布 markdown 到公众号草稿箱）
```

DataAnalysis / QuickQuery / WechatPublish 均支持 `set_sandbox()` 由 Web 层注入 Docker 沙箱。

所有智能体都是 Pydantic 模型（`BaseAgent extends BaseModel`）。执行循环位于 `BaseAgent.run()` 中——通过 `think()` → `act()` 逐步执行，直到达到 `max_steps` 或状态变为 `FINISHED`。状态机：`IDLE → RUNNING → FINISHED | ERROR`。

智能体持有 `Memory`（`Message` 对象列表）和一个 `LLM` 实例。`ToolCallAgent.think()` 方法将对话内容 + 工具定义发送给 LLM；`act()` 执行返回的工具调用并记录结果。卡住检测会比较连续的助手消息中是否存在重复内容。

### 工具系统

所有工具都继承自 `BaseTool`（`app/tool/base.py`），它是一个 Pydantic 模型，包含 `name`、`description`、`parameters`（JSON Schema）、一个抽象的 `execute()` 方法以及用于 OpenAI 函数调用格式的 `to_param()`。结果使用 `ToolResult`（携带 `output`、`error`、可选的 `base64_image`）。

`ToolCollection`（`app/tool/tool_collection.py`）是一个容器，按工具名称分发并将其转换为 LLM 兼容的参数。工具可以在类定义时静态添加，也可以动态添加（通过 `add_tools()` 添加 MCP 工具）。

内置关键工具：

- `PythonExecute` / `NormalPythonExecute` — 在子进程（或沙箱）中执行 Python
- `BrowserUseTool` — 基于 Playwright 的网页浏览
- `StrReplaceEditor` — 具有字符串替换语义的文件查看/编辑
- `Bash` — Shell 命令执行
- `WebSearch` — 带引擎回退的网页搜索（Google → DuckDuckGo → Baidu → Bing）
- `PlanningTool` — 创建/标记/更新计划（由 PlanningFlow 使用）
- `CreateChatCompletion` — 子智能体 LLM 调用
- `Terminate` — 标记智能体完成（特殊工具，设置 `AgentState.FINISHED`）

本地业务工具：

- `CompanyDataLookup`（`app/tool/company_data_lookup.py`）— 企业数据查询，MySQL / 本地 CSV 双模式（由 `[web].data_lookup_mode` 选择），走独立业务数据查询库（`mysql_data_database`）
- `AskHuman`（`app/tool/ask_human.py`）— 人工询问
- `WechatPublishTool`（`app/tool/wechat_publish/`）— 公众号发布，bun 脚本依赖自包含

数据读取规范：NormalPythonExecute stdout 注入 50000 字符保护性截断（头 2 万 + 尾 3 万）；数据全量表述走 system 通道，避免被 `max_observe` 截断。

### LLM 集成（`app/llm.py`）

`LLM` 类是一个按配置名称（例如 `"default"`、`"vision"`）管理的单例。它封装了 OpenAI SDK（`AsyncOpenAI`），并支持 Azure 和 AWS Bedrock 后端。Token 计数使用 `tiktoken`，回退到 `cl100k_base`。

三种主要方法：

- `ask()` — 带流式支持的纯文本对话
- `ask_with_images()` — 多模态（将图像附加到最后一条用户消息）
- `ask_tool()` — 工具/函数调用（始终为非流式）

所有方法都包含通过 `tenacity` 实现的重试逻辑（指数退避，最多 6 次）、通过 `TokenLimitExceeded` 实现的 Token 限制强制、以及用于多模态模型的 base64 图像处理。

### 配置（`app/config.py`）— 多环境

部署环境由 `OPENMANUS_ENV` 环境变量决定（入口脚本位置参数经 `entry.py` 写入该变量），未设置或空白时默认 `dev`。配置文件按 `config/config_{env}.toml` 选择：

- `dev` 缺失时回退 `config.example.toml`（保持开箱即用）
- 非 `dev` 环境缺失时**明确报错**，报错信息包含可用环境清单

本地实际配置文件为 `config/config_dev.toml`、`config/config_test.toml`（均被 `config/.gitignore` 忽略，勿提交）；模板为 `config.example.toml` 及各模型示例（azure/anthropic/google/jiekouai/ollama/ppio）。

`Config` 单例将设置加载到 `AppConfig` 中，包含：`LLMSettings`（每个模型名称的字典，包含 base_url、api_key、model、max_tokens、temperature、api_type 用于 azure/aws/ollama/jiekou）、`BrowserSettings`、`SearchSettings`、`SandboxSettings`、`MCPSettings`、`WebSettings`（web 子系统配置，含 `data_lookup_mode`、`mysql_data_database` 等）和 `RunflowSettings`。

MCP 服务器配置在 `config/mcp.example.json`（模板），本地 `config/mcp.json`（gitignore）——每个服务器有 `type`（sse 或 stdio）、`url`/`command` 和 `args`。

### Web 聊天子系统（`app/web/` + `web_ui/`）

`web_run.py` 通过 uvicorn 启动 `app.web.server:app`（`0.0.0.0:8080`）。结构：

```
app/web/
├── server.py          # FastAPI 入口 + lifespan（启动清理孤儿沙箱，关闭清理全部沙箱）
├── auth/              # JWT 认证（models/schemas/router/service）
├── chat/              # 会话（models/schemas/router/service/ws_handler）
├── files/             # 文件管理（models/schemas/router/service）
├── sandbox/           # 沙箱生命周期服务（startup_sandbox_cleanup 等）
├── agent_runner.py    # 智能体运行调度（按 agent 类型分发）
├── dependencies.py    # FastAPI 依赖（认证、DB 会话等）
└── database.py        # MySQL 引擎/连接池
```

主要端点：`/`（前端 Vue 构建产物）、`/static/`、`WS /ws/{chat_id}?token=`、`/api/auth/*`、`/api/chats/*`、`/api/files/*`。

前端 `web_ui/` 是独立 Vue3 项目（Vite + Pinia + Tailwind）。后端服务 `web_ui/dist` 构建产物，改前端须 `npm run build` 后再重启后端。多用户隔离依赖 MySQL + JWT（`jwt_secret_key` 生产环境必改）。

### 流系统（多智能体编排）

`BaseFlow`（`app/flow/base.py`）管理一个智能体字典，并指定一个主要智能体。`PlanningFlow`（`app/flow/planning.py`）使用 LLM + `PlanningTool` 创建逐步计划，然后迭代执行各步骤，将每一步分派给相应的执行智能体。它在 `run_flow.py` 中运行——这是生产环境的多智能体入口点。

### 沙箱（`app/sandbox/`）

`DockerSandbox`（`app/sandbox/core/sandbox.py`）管理具有资源限制（CPU、内存、网络隔离）的 Docker 容器。它通过 tar 归档提供文件读写功能，通过 `AsyncDockerizedTerminal` 提供命令执行功能，以及清理协议。`DockerSession`（`app/sandbox/core/terminal.py`）已兼容 docker SDK 7.x 的 NpipeSocket 返回形态，recv 经线程池执行以保留超时语义。`LocalSandboxClient`（`app/sandbox/client.py`）以一致接口封装了上述功能，作为模块级别的 `SANDBOX_CLIENT` 单例暴露。

### 数据模型（`app/schema.py`）

核心 Pydantic 模型：`Message`（role、content、tool_calls、base64_image）、`ToolCall`/`Function`（工具调用结构）、`AgentState` 枚举、`Memory`（消息列表）、`Role`/`ToolChoice` 枚举。

## 关键模式

- **entry.py 启动桥接**：入口脚本必须先 `import entry` 并执行 `entry.apply_env(entry.parse_env())`，且必须在任何 `app.*` import **之前**——config 单例在首次 import 时完成加载，先导入 app 包会让环境变量写入失效。
- **智能体作为 Pydantic 模型**：智能体使用 `@model_validator(mode="after")` 进行初始化，使用 `Field(default_factory=...)` 处理可变默认值。Manus 智能体需要异步工厂方法 `Manus.create()` 来在创建时设置 MCP 服务器连接。
- **状态异步上下文管理器**：`BaseAgent.state_context()` 确保安全的状态转换，出错时自动回滚到之前的状态。
- **特殊工具**：`Terminate().name` 位于 `special_tool_names` 中——执行时，它会将智能体状态设置为 `FINISHED`，结束运行循环。
- **MCP 工具集成**：MCP 服务器在智能体创建时连接，其工具动态添加到 `available_tools` 中。断开服务器连接会重建工具集合，排除该服务器的工具。
