# AGENTS.md

本文件是 AI 编码助手进入 OpenManus 工作树后的执行手册。`CLAUDE.md` 是项目架构、个人偏好和核心规则的权威说明；本文件负责把这些要求落到“先读什么、去哪里改、如何验证、哪些地方不要踩坑”。

## 1. 指令优先级与工作原则

指令发生冲突时按以下顺序处理：

1. 用户在当前任务中的明确要求。
2. `CLAUDE.md` 中的个人要求与项目规则。
3. 本文件的仓库操作约定。

判断项目事实时，以当前代码、测试和配置所体现的实际行为为准。若说明文档与实现不一致，先核实原因并向用户说明，不要为了迎合旧文档而修改正确代码。

必须遵守：

- 计划、进度、审查和逻辑解释使用中文。
- 代码注释使用简体中文；代码标识符保持英文。
- 收到任务先检查可用 skill；只要可能适用就先阅读并遵循。
- 功能新增或行为变更先使用 brainstorming 做需求分析，并在设计获用户确认后实施。
- 修改代码遵循 TDD：先写会失败的测试，再做最小实现，最后重构。
- 声称完成前必须运行与风险相称的验证命令，并依据真实输出汇报。
- 遵循 Karpathy 准则：先思考、极简实现、精确修改、目标驱动验收。

## 2. 每个任务的标准流程

### 2.1 开始前

1. 阅读本文件、`CLAUDE.md`，以及目标目录内更具体的说明文件。
2. 检查匹配的 skill，并按 skill 规定的流程工作。
3. 查看 `git status --short` 和相关文件历史，识别用户已有修改；不要覆盖、回退或顺手整理无关改动。
4. 先阅读目标实现、直接调用方和现有测试，不根据文件名猜行为。
5. 用中文列出精简计划和验收方式，状态标记为已完成、进行中、待处理。

### 2.2 实施中

- 功能或缺陷修复先建立最小失败测试；纯文档、配置说明等不适合 TDD 的任务，先定义可执行的验收清单。
- 修改范围保持最小，只做服务当前目标的重构。
- 沿用现有异步、Pydantic、工具注册、异常处理和测试模式。
- 发现需求会改变公共接口、数据模型或多个子系统时，暂停并升级设计，不擅自扩大范围。
- 工作树可能是脏的。用户已有改动属于用户；与任务无关的文件一律不碰。

### 2.3 完成前

1. 先运行最小相关测试，再按影响范围扩大到子系统或全量测试。
2. 对改动文件运行格式和静态检查。
3. 阅读最终 diff，确认没有秘密、生成物、调试代码或无关格式化。
4. 汇报实际修改、验证结果、未运行的检查及原因；不能把“预计通过”写成“已通过”。

## 3. 本机环境（关键）

- 系统：Windows 11。
- Shell：PowerShell。
- 项目目录：`C:\Code\OpenManus`。
- 固定 Python：`C:\Users\hyh\anaconda3\envs\open_manus\python.exe`。

不要调用泛指的 `python`、`python3` 或其他解释器。所有 Python 命令都使用上述绝对路径，例如：

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\test_schema.py -v
```

本机 conda 环境已经配置，不要无故重建环境或重装全部依赖。确需安装依赖时使用：

```powershell
uv pip install --python C:\Users\hyh\anaconda3\envs\open_manus\python.exe -r requirements.txt
```

禁止使用 `pip install -e .` 或 `python setup.py`：`setup.py` 会读取仓库中不存在的 `README.md`，当前会直接触发 `FileNotFoundError`。浏览器自动化另需可选的 Playwright 浏览器安装。

## 4. 十分钟项目地图

OpenManus 的主执行链路：

```text
入口脚本
  -> entry.py 写入 OPENMANUS_ENV
  -> app/config.py 首次导入时加载配置
  -> Agent.run()
  -> ReAct: think() / act()
  -> LLM 工具调用
  -> ToolCollection 分发工具
  -> 本地进程、浏览器、MCP 或 Docker Sandbox
```

Web 链路：

```text
Vue3 前端
  -> FastAPI REST / WebSocket
  -> chat/ws_handler.py
  -> agent_runner.py 创建可观测 Agent
  -> Agent + 用户隔离 Sandbox
  -> MySQL 持久化消息、会话和文件元数据
```

关键目录：

| 路径 | 职责 | 常见修改场景 |
| --- | --- | --- |
| `app/agent/` | Agent 状态机、ReAct、工具调用及业务 Agent | 新增 Agent、调整步骤循环或工具组合 |
| `app/tool/` | 工具协议与具体工具 | 新增工具、修改执行或返回结构 |
| `app/flow/` | PlanningFlow 多智能体规划与分派 | 调整计划创建、步骤选择或执行策略 |
| `app/web/` | FastAPI、JWT、MySQL、WebSocket、文件与沙箱调度 | Web API、会话、认证、持久化 |
| `web_ui/` | Vue3 + Vite + Pinia + Tailwind 前端 | 页面、状态管理、REST/WS 客户端 |
| `app/sandbox/` | Docker 容器、终端、文件操作与生命周期 | 隔离执行、超时、容器清理 |
| `app/prompt/` | 各 Agent 的系统提示词 | 修改行为约束或工具使用策略 |
| `app/tool/chart_visualization/` | TypeScript + VChart 图表生成子项目 | 数据分析图表与渲染 |
| `app/tool/wechat_publish/` | Bun/TypeScript 公众号发布工具 | Markdown 转换、素材上传、远程发布 |
| `project_docs/` | 企业/项目两级业务说明 | 企业数据查询的业务语义资产 |
| `tests/` | 单元、Web、工具与 Sandbox 测试 | 任何代码改动的首要参考 |
| `docs/superpowers/` | 已确认的设计与实施计划 | 理解定制功能的历史决策 |
| `config/` | 配置模板及本地环境配置 | LLM、Web、Sandbox、MCP、多环境 |

推荐阅读顺序：

1. `CLAUDE.md`：架构和个人要求。
2. 与任务对应的测试：确认期望行为。
3. 目标模块及直接调用方：确认真实数据流。
4. `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 中相关主题：理解设计原因。
5. 专题文档：`启动项说明.md`、`开启mcp.md`、`docs/sandbox-guide.md`、`docs/openmanus-web-ops-manual.md`。这些长文可能滞后，关键命令和配置仍需以代码与测试复核。

## 5. 核心架构与修改落点

### 5.1 Agent 层次

```text
BaseAgent                         app/agent/base.py
  -> ReActAgent                   app/agent/react.py
      -> ToolCallAgent            app/agent/toolcall.py
          -> Manus                通用执行，支持动态 MCP
          -> DataAnalysis         数据分析与图表
          -> QuickQuery           轻量企业数据查询
          -> WechatPublish        公众号发布
          -> BrowserAgent         浏览器专用 Agent
          -> MCPAgent             MCP 客户端 Agent
```

- `BaseAgent.run()` 管理步骤循环与 `IDLE -> RUNNING -> FINISHED | ERROR` 状态。
- `ToolCallAgent.think()` 请求 LLM 工具调用，`act()` 执行工具并记录结果。
- Agent 是 Pydantic 模型；可变字段使用 `Field(default_factory=...)`，初始化联动通常放在 `@model_validator(mode="after")`。
- `Manus` 连接动态 MCP 服务时必须通过异步工厂 `await Manus.create()`；不要在需要 MCP 初始化的入口中直接用 `Manus()` 替代。
- `Terminate` 是特殊工具，会把 Agent 状态设置为 `FINISHED`。
- Web 支持的会话类型以 `app/web/chat/models.py` 的 `AGENT_TYPES` 为准，目前为 `general`、`data_analysis`、`quick_query`、`wechat_publish`。新增类型时必须同步服务校验、`agent_runner.py`、前端选择器及测试。

### 5.2 工具系统

- 所有工具继承 `app/tool/base.py::BaseTool`，提供 `name`、`description`、JSON Schema `parameters` 和异步 `execute()`。
- 结果统一使用 `ToolResult`；工具错误应返回可诊断信息，不要吞异常或伪装成功。
- `ToolCollection` 负责按名称分发，并转换成 LLM 可用的函数调用参数。
- 新增工具通常需要同时处理：实现文件、`app/tool/__init__.py` 导出、目标 Agent 的 `available_tools`、提示词约束和测试。
- `CompanyDataLookup` 同时承载本地 CSV / MySQL 查询和 `project_docs/` 业务文档读取；修改查询协议时要覆盖三条路径。
- `NormalPythonExecute` 的 stdout 有保护性截断；涉及大数据上下文时不要随意移除 system 通道和截断策略。

### 5.3 Web 子系统

- `web_run.py` 启动 `app.web.server:app`，监听 `0.0.0.0:8080`。
- `app/web/server.py` 的 lifespan 负责数据库心跳与孤儿 Sandbox 清理；改启动/关闭行为时检查资源回收。
- `app/web/chat/ws_handler.py` 管理 WebSocket 生命周期，`app/web/agent_runner.py` 把 Agent 事件转换为前端流式事件。
- Web 创建的 Agent 可注入用户隔离 Sandbox；当前只有 `general` 会话允许 Sandbox 网络访问。
- 数据库错误有 503 降级路径；不要把临时数据库不可用改成未处理的 500。
- 前端构建产物位于 `web_ui/dist`，后端直接服务该目录。修改前端后必须重新构建。

### 5.4 Sandbox

- `DockerSandbox` 管理容器、资源限制、文件归档和命令执行。
- `DockerSession` / `AsyncDockerizedTerminal` 负责带超时的终端交互；阻塞 Docker SDK 调用通过线程处理，修改时必须保留异步超时语义。
- Web 层通过 `app/web/sandbox/service.py` 管理每个用户/会话的 Sandbox 生命周期。
- Sandbox 集成测试依赖 Docker Desktop；未启动 Docker 时应明确记录为环境限制，不能宣称相关验证通过。

## 6. 配置与入口约束

### 6.1 `entry.py` 导入顺序不可破坏

所有入口必须先执行：

```python
import entry

entry.apply_env(entry.parse_env())
```

之后才能导入任何 `app.*`。`app/config.py` 的单例会在首次导入时加载配置；提前导入 `app.*` 会导致命令行环境参数失效。

### 6.2 多环境配置

- `OPENMANUS_ENV` 决定 `config/config_{env}.toml`，未设置或空白时默认 `dev`。
- 入口的位置参数优先于已有环境变量，且必须紧跟脚本名，如 `main.py test --prompt "..."`。
- `dev` 配置缺失时回退 `config/config.example.toml`。
- 非 `dev` 配置缺失时明确报错，不允许静默回退。
- `config/config_dev.toml`、`config/config_test.toml` 是本地配置：若已存在就保留，不重建、不覆盖、不提交。
- `config/mcp.json` 是可选本地 MCP 配置，可能不存在。当前不能假定它已被 gitignore；创建或修改前先检查忽略规则，绝不能提交密钥或内网地址。模板是 `config/mcp.example.json`。

## 7. 启动命令

以下命令都从仓库根目录运行。环境参数仅支持入口实际接受的形式，默认均为 `dev`。

| 命令 | 用途 |
| --- | --- |
| `C:\Users\hyh\anaconda3\envs\open_manus\python.exe main.py [dev\|test] [--prompt "..."]` | CLI 通用 Manus Agent |
| `C:\Users\hyh\anaconda3\envs\open_manus\python.exe run_flow.py [dev\|test]` | PlanningFlow；整体硬超时 3600 秒 |
| `C:\Users\hyh\anaconda3\envs\open_manus\python.exe web_run.py [dev\|test]` | FastAPI Web 服务，端口 8080 |
| `C:\Users\hyh\anaconda3\envs\open_manus\python.exe run_mcp.py [dev\|test]` | MCP Agent 客户端；另支持连接和 prompt 参数 |
| `C:\Users\hyh\anaconda3\envs\open_manus\python.exe run_mcp_server.py [dev\|test]` | MCP 服务端 |

前端独立开发：

```powershell
npm --prefix web_ui ci
npm --prefix web_ui run dev
npm --prefix web_ui run build
```

图表子项目仅在修改图表生成链路时安装依赖：

```powershell
npm --prefix app/tool/chart_visualization ci
```

不要运行 `npm test`：两个 npm 子项目目前都没有可用的测试脚本，图表行为由 Python 侧测试覆盖。

## 8. 测试与格式化

### 8.1 测试命令

始终用 `-m pytest`，避免入口解析或解释器混淆：

```powershell
# 单个测试
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\sandbox\test_sandbox.py::test_sandbox_python_execution -v

# 单个文件
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\test_schema.py -v

# 多环境与入口回归
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\test_entry.py tests\test_entrypoints.py tests\test_config_env.py -v

# 全量测试；需要按测试范围准备 MySQL 和 Docker Desktop
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests -v
```

`pytest.ini` 已设置 `asyncio_mode = auto`，异步测试不需要显式添加 `@pytest.mark.asyncio`。

### 8.2 外部依赖矩阵

| 测试范围 | 额外条件 |
| --- | --- |
| 普通 Agent、配置、Schema、纯工具单测 | 本地 Python 配置可加载 |
| `tests/web/` | 部分测试需要 `[web]` MySQL 配置和可访问数据库 |
| `tests/sandbox/` | 集成测试需要 Docker Desktop；部分单元测试可独立运行 |
| `CompanyDataLookup` 本地模式 | `company_data_resource/` 中的本地 CSV 数据 |
| `CompanyDataLookup` MySQL 模式 | `mysql_data_database` 指向的业务数据库 |
| 前端修改 | `npm --prefix web_ui run build` |

`tests/web/conftest.py` 的 autouse async fixture 不可删除。它必须在每个异步测试结束后、同一 event loop 上 dispose 数据库引擎，否则 aiomysql 连接跨 loop 回收会产生难以定位的异常。

### 8.3 格式化与 pre-commit

优先只检查改动文件，避免在脏工作树中重写用户的无关代码：

```powershell
pre-commit run --files path\to\changed_file.py
```

准备提交并确认工作树范围安全时，再运行：

```powershell
pre-commit run --all-files
```

当前 hook 顺序为：Black；尾随空白、文件结尾、YAML、大文件检查；Autoflake；Isort。Isort 使用 Black profile 和 `--lines-after-imports=2`；Autoflake 排除 `__init__.py`，不要手动清理其中用于公共导出的导入。

## 9. 按任务选择验收范围

| 修改类型 | 最低验收 |
| --- | --- |
| 纯文档 | 检查链接/路径/命令，查看 diff，对改动文件跑 pre-commit |
| Agent 或工具 | 新增/修改单测 + 相关 Agent/工具测试 + 改动文件 pre-commit |
| 配置或入口 | `test_entry.py`、`test_entrypoints.py`、`test_config_env.py` |
| Web 后端 | 相关 `tests/web/`；涉及数据库时验证 503 降级与资源 dispose |
| Web 前端 | `npm --prefix web_ui run build`，必要时联调 REST 与 WebSocket |
| Sandbox | 对应单元测试；Docker 可用时再跑集成测试 |
| 数据查询 | local / mysql / project_docs 三条受影响路径分别覆盖 |
| 图表 | `tests/tool/test_data_visualization.py` 及相关 Sandbox 注入测试 |
| 公众号发布 | `tests/tool/test_wechat_publish.py`，不要真实发布除非用户明确授权 |

## 10. 易踩坑与禁止事项

- 不要使用系统 Python，不要混用多个环境。
- 不要在 `entry.apply_env(...)` 之前导入 `app.*`。
- 不要重建、覆盖或提交本地配置与密钥。
- 不要删除或弱化 `tests/web/conftest.py` 的数据库清理 fixture。
- 不要把 Docker、MySQL、外部 LLM 或真实公众号发布失败误判为纯代码失败；先隔离外部条件。
- 不要默认运行期目录可以提交：`workspace/`、`logs/`、`data/`、`company_data_resource/` 以及构建产物均应保持在版本控制外。
- 不要用破坏性 Git 命令清理工作树，不要回退用户已有变更。
- 不要因为 pre-commit 会自动修复就对全仓库盲跑；先限制到本次改动文件并复查 diff。
- 不要修改 `__init__.py` 的导出仅为了消除“未使用导入”。
- 不要真实调用有外部副作用的工具（公众号发布、远程写入、删除数据），除非用户明确要求并且目标已核实。

## 11. 完成定义

任务只有在以下条件满足后才能标记完成：

- 用户要求和已确认设计均已实现，没有偷偷扩展范围。
- 新行为有先失败后通过的测试；不适用 TDD 时有明确且已执行的替代验收。
- 相关测试、格式检查和必要构建已实际运行并记录结果。
- 最终 diff 只包含预期文件，不含密钥、生成物和无关改动。
- 已知限制、依赖外部环境而未执行的验证，以及潜在后续工作已如实告知用户。
