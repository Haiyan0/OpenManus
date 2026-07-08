# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中编写代码时提供指导。

## Python 环境

当前机台 Python 路径：**C:\Users\hyh\anaconda3\envs\open_manus\python.exe**

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

## 构建与运行命令

```bash
# 安装依赖（推荐使用 uv）
uv venv --python 3.12
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
playwright install           # 可选，用于浏览器自动化

# 运行主智能体（交互式）
python main.py
python main.py --prompt "你的任务描述"

# 运行规划流（多智能体编排）
python run_flow.py

# 在 Docker 沙箱中运行
python sandbox_main.py

# 运行测试
pytest tests/

# 运行单个测试文件
pytest tests/sandbox/test_sandbox.py -v

# 运行单个测试
pytest tests/sandbox/test_sandbox.py::test_sandbox_python_execution -v
```

## 架构

### 智能体类继承层次

```
BaseAgent (app/agent/base.py)
  └── ReActAgent (app/agent/react.py) — 引入 think() + act() 循环
        └── ToolCallAgent (app/agent/toolcall.py) — LLM 工具/函数调用
              ├── Manus (app/agent/manus.py) — 通用型：PythonExecute、
              │     BrowserUseTool、StrReplaceEditor、AskHuman，+ 动态 MCP 工具
              ├── SWEAgent (app/agent/swe.py) — 软件工程：Bash、
              │     StrReplaceEditor、Terminate
              └── DataAnalysis (app/agent/data_analysis.py) — 数据分析：
                    NormalPythonExecute、VisualizationPrepare、DataVisualization
```

所有智能体都是 Pydantic 模型（`BaseAgent extends BaseModel`）。执行循环位于 `BaseAgent.run()` 中——通过 `think()` → `act()` 逐步执行，直到达到 `max_steps` 或状态变为 `FINISHED`。状态机：`IDLE → RUNNING → FINISHED | ERROR`。

智能体持有 `Memory`（`Message` 对象列表）和一个 `LLM` 实例。`ToolCallAgent.think()` 方法将对话内容 + 工具定义发送给 LLM；`act()` 执行返回的工具调用并记录结果。卡住检测会比较连续的助手消息中是否存在重复内容。

### 工具系统

所有工具都继承自 `BaseTool`（`app/tool/base.py`），它是一个 Pydantic 模型，包含 `name`、`description`、`parameters`（JSON Schema）、一个抽象的 `execute()` 方法以及用于 OpenAI 函数调用格式的 `to_param()`。结果使用 `ToolResult`（携带 `output`、`error`、可选的 `base64_image`）。

`ToolCollection`（`app/tool/tool_collection.py`）是一个容器，按工具名称分发并将其转换为 LLM 兼容的参数。工具可以在类定义时静态添加，也可以动态添加（通过 `add_tools()` 添加 MCP 工具）。

内置关键工具：

- `PythonExecute` / `NormalPythonExecute` — 在子进程中执行 Python
- `BrowserUseTool` — 基于 Playwright 的网页浏览
- `StrReplaceEditor` — 具有字符串替换语义的文件查看/编辑
- `Bash` — Shell 命令执行
- `WebSearch` — 带引擎回退的网页搜索（Google → DuckDuckGo → Baidu → Bing）
- `PlanningTool` — 创建/标记/更新计划（由 PlanningFlow 使用）
- `Crawl4aiTool` — 网页爬取
- `CreateChatCompletion` — 子智能体 LLM 调用
- `Terminate` — 标记智能体完成（特殊工具，设置 `AgentState.FINISHED`）

### LLM 集成（`app/llm.py`）

`LLM` 类是一个按配置名称（例如 `"default"`、`"vision"`）管理的单例。它封装了 OpenAI SDK（`AsyncOpenAI`），并支持 Azure 和 AWS Bedrock 后端。Token 计数使用 `tiktoken`，回退到 `cl100k_base`。

三种主要方法：

- `ask()` — 带流式支持的纯文本对话
- `ask_with_images()` — 多模态（将图像附加到最后一条用户消息）
- `ask_tool()` — 工具/函数调用（始终为非流式）

所有方法都包含通过 `tenacity` 实现的重试逻辑（指数退避，最多 6 次）、通过 `TokenLimitExceeded` 实现的 Token 限制强制、以及用于多模态模型的 base64 图像处理。

### 配置（`app/config.py`）

基于 TOML 的配置文件，从 `config/config.toml` 加载（从 `config/config.example.toml` 复制）。`Config` 单例将设置加载到 `AppConfig` 中，包含：`LLMSettings`（每个模型名称的字典，包含 base_url、api_key、model、max_tokens、temperature、api_type 用于 azure/aws/ollama/jiekou）、`BrowserSettings`、`SearchSettings`、`SandboxSettings`、`MCPSettings`、`DaytonaSettings` 和 `RunflowSettings`。

MCP 服务器配置在单独的 `config/mcp.json` 文件中——每个服务器有 `type`（sse 或 stdio）、`url`/`command` 和 `args`。

### 流系统（多智能体编排）

`BaseFlow`（`app/flow/base.py`）管理一个智能体字典，并指定一个主要智能体。`PlanningFlow`（`app/flow/planning.py`）使用 LLM + `PlanningTool` 创建逐步计划，然后迭代执行各步骤，将每一步分派给相应的执行智能体。它在 `run_flow.py` 中运行——这是生产环境的多智能体入口点。

### 沙箱（`app/sandbox/`）

`DockerSandbox`（`app/sandbox/core/sandbox.py`）管理具有资源限制（CPU、内存、网络隔离）的 Docker 容器。它通过 tar 归档提供文件读写功能，通过 `AsyncDockerizedTerminal` 提供命令执行功能，以及清理协议。`LocalSandboxClient`（`app/sandbox/client.py`）以一致接口封装了上述功能，作为模块级别的 `SANDBOX_CLIENT` 单例暴露。

### A2A 协议（`protocol/a2a/`）

基于 FastAPI 的智能体间通信服务器，允许 OpenManus 智能体作为 HTTP 服务暴露，供其他智能体调用。

### 数据模型（`app/schema.py`）

核心 Pydantic 模型：`Message`（role、content、tool_calls、base64_image）、`ToolCall`/`Function`（工具调用结构）、`AgentState` 枚举、`Memory`（消息列表）、`Role`/`ToolChoice` 枚举。

## 关键模式

- **智能体作为 Pydantic 模型**：智能体使用 `@model_validator(mode="after")` 进行初始化，使用 `Field(default_factory=...)` 处理可变默认值。Manus 智能体需要异步工厂方法 `Manus.create()` 来在创建时设置 MCP 服务器连接。
- **状态异步上下文管理器**：`BaseAgent.state_context()` 确保安全的状态转换，出错时自动回滚到之前的状态。
- **特殊工具**：`Terminate().name` 位于 `special_tool_names` 中——执行时，它会将智能体状态设置为 `FINISHED`，结束运行循环。
- **MCP 工具集成**：MCP 服务器在智能体创建时连接，其工具动态添加到 `available_tools` 中。断开服务器连接会重建工具集合，排除该服务器的工具。
