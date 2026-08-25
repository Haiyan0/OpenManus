# OpenManus Sandbox 启动与运维手册

> 适用版本：当前 `feat/web-chat` 分支
> 目标读者：初级程序员及以上
> 最后更新：2026-08-25

---

## 目录

1. [架构总览](#1-架构总览)
2. [本地多进程执行（当前默认）](#2-本地多进程执行当前默认)
3. [Docker Sandbox（本地容器隔离）](#3-docker-sandbox本地容器隔离)
4. [运行指南](#4-运行指南)
5. [配置参考](#5-配置参考)
6. [常见问题排查](#6-常见问题排查)

---

## 1. 架构总览

### 1.1 两套执行环境全景图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OpenManus 执行环境                            │
├───────────────────────────┬──────────────────────────────────────────┤
│  本地多进程                │  Docker Sandbox                          │
│  (当前默认)                │  (Web 层注入)                             │
├───────────────────────────┼──────────────────────────────────────────┤
│  入口:                     │  入口:                                    │
│  main.py                  │  Web 会话（agent_runner set_sandbox）      │
│  run_flow.py              │                                          │
├───────────────────────────┼──────────────────────────────────────────┤
│  隔离方式:                 │  隔离方式:                                │
│  multiprocessing          │  Docker 容器                             │
│  .Process                 │  (CPU/内存/网络限制)                      │
├───────────────────────────┼──────────────────────────────────────────┤
│  文件系统:                 │  文件系统:                                │
│  本地文件系统               │  容器内隔离文件系统                        │
├───────────────────────────┼──────────────────────────────────────────┤
│  网络安全:                 │  网络安全:                                │
│  无网络隔离                 │  可配置关闭网络                            │
├───────────────────────────┼──────────────────────────────────────────┤
│  安全等级:                 │  安全等级:                                │
│  ★★☆☆☆ (低)               │  ★★★★☆ (高)                              │
├───────────────────────────┼──────────────────────────────────────────┤
│  适用场景:                 │  适用场景:                                │
│  开发调试、                │  本地安全执行、                            │
│  轻量数据分析              │  不可信代码隔离                            │
└───────────────────────────┴──────────────────────────────────────────┘
```

### 1.2 执行环境对比表

| 维度                 | 本地多进程      | Docker Sandbox     |
| -------------------- | --------------- | ------------------ |
| **启用状态**   | ✅ 默认启用     | ✅ Web 层注入      |
| **配置位置**   | 无需配置        | `[sandbox]` 段   |
| **额外依赖**   | 无              | Docker Desktop     |
| **资源限制**   | 仅超时(30s)     | 内存/CPU/网络      |
| **文件持久化** | 本地直接读写    | 容器内/volume 挂载 |
| **浏览器支持** | Playwright 本地 | 不支持             |
| **适合生产**   | 否              | 是                 |

### 1.3 `run_flow.py` 完整调用链路

```
run_flow.py (入口)
  │
  ├─ 创建 agents 字典:
  │   ├─ Manus (通用智能体) ──── PythonExecute (多进程)
  │   └─ DataAnalysis (数据分析) ──── NormalPythonExecute (多进程)
  │
  └─ FlowFactory.create_flow(PLANNING)
       │
       └─ PlanningFlow.execute(prompt)
            │
            ├─ _create_initial_plan()     ← LLM 生成执行计划
            │
            └─ while 还有未完成步骤:
                 │
                 ├─ _get_current_step_info()   ← 获取下一步
                 ├─ get_executor(step_type)     ← 选择执行 Agent
                 └─ _execute_step(executor)     ← executor.run(step_prompt)
                      │
                      └─ ToolCallAgent.run()
                           │
                           └─ think() → act() 循环
                                │
                                └─ execute_tool()
                                     │
                                     └─ PythonExecute.execute()
                                          │
                                          └─ multiprocessing.Process
                                               (子进程执行代码, 30s 超时)
```

> **关键结论：`run_flow.py` 当前不使用任何沙箱容器。** 代码执行通过 `multiprocessing.Process` 在本地子进程中完成。Docker Sandbox 模块由 Web 层注入使用。

---

## 2. 本地多进程执行（当前默认）

### 2.1 工作原理

`main.py` 和 `run_flow.py` 启动的 Agent 默认使用以下工具执行 Python 代码：

| Agent            | 工具类                  | 文件位置                                           |
| ---------------- | ----------------------- | -------------------------------------------------- |
| `Manus`        | `PythonExecute`       | `app/tool/python_execute.py`                     |
| `DataAnalysis` | `NormalPythonExecute` | `app/tool/chart_visualization/python_execute.py` |

`NormalPythonExecute` 继承自 `PythonExecute`，增加了 `code_type` 参数（用于区分 data process / report / others），但核心执行逻辑完全相同。

### 2.2 进程隔离机制

```python
# 简化的执行流程 (app/tool/python_execute.py)
def _run_code(self, code, result_dict, safe_globals):
    """在子进程中执行 Python 代码，捕获 stdout"""
    output_buffer = StringIO()
    sys.stdout = output_buffer       # 重定向标准输出
    exec(code, safe_globals, safe_globals)
    result_dict["observation"] = output_buffer.getvalue()

async def execute(self, code, timeout=30):
    with multiprocessing.Manager() as manager:
        result = manager.dict()
        proc = multiprocessing.Process(
            target=self._run_code,
            args=(code, result, safe_globals)
        )
        proc.start()
        proc.join(timeout)           # 等待最多 30 秒

        if proc.is_alive():          # 超时处理
            proc.terminate()         # 强制终止子进程
            proc.join(1)
            return {"observation": "Execution timeout...", "success": False}
```

### 2.3 安全特点

| 特性                     | 说明                                                          |
| ------------------------ | ------------------------------------------------------------- |
| **进程隔离**       | 代码在独立子进程中运行，崩溃不影响主进程                      |
| **超时控制**       | 默认 30 秒超时，防止无限循环                                  |
| **输出捕获**       | `sys.stdout` 重定向到 `StringIO`，仅 `print()` 输出可见 |
| **受限 globals**   | 使用`__builtins__` 副本，但**没有限制危险函数**       |
| **无网络隔离**     | 代码可以访问网络                                              |
| **无文件系统隔离** | 代码可以读写本地文件系统                                      |

> ⚠️ **安全警告**：多进程模式的安全隔离有限。不可信代码仍可能通过 `__import__`、`open()` 等访问系统资源。**不要在此模式下执行不可信代码。**

---

## 3. Docker Sandbox（本地容器隔离）

### 3.1 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                      Docker Sandbox 架构                      │
│                                                              │
│  ┌─────────────────────┐     ┌─────────────────────────────┐ │
│  │  SandboxManager      │     │  LocalSandboxClient          │ │
│  │  (生命周期管理)       │────▶│  (单例 SANDBOX_CLIENT)       │ │
│  │                     │     │                             │ │
│  │  - 最多 100 沙箱     │     │  - create()  创建沙箱        │ │
│  │  - 空闲 3600s 回收   │     │  - run_command() 执行命令   │ │
│  │  - 每 300s 检查      │     │  - read_file() 读文件       │ │
│  │  - 并发锁控制        │     │  - write_file() 写文件      │ │
│  └─────────────────────┘     │  - copy_to/from() 文件传输  │ │
│                               │  - cleanup() 清理资源       │ │
│                               └──────────┬──────────────────┘ │
│                                          │                    │
│  ┌───────────────────────────────────────▼──────────────────┐ │
│  │  DockerSandbox (单个沙箱实例)                              │ │
│  │                                                          │ │
│  │  容器配置:                                                │ │
│  │  - 镜像: python:3.12-slim (可配置)                        │ │
│  │  - 工作目录: /workspace                                   │ │
│  │  - 内存限制: 512m (可配置)                                 │ │
│  │  - CPU 限制: 1.0 核 (可配置)                              │ │
│  │  - 网络: 默认关闭                                         │ │
│  │  - 命名: sandbox_{8位随机hex}                              │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐    │ │
│  │  │  AsyncDockerizedTerminal                          │    │ │
│  │  │  (异步终端接口)                                    │    │ │
│  │  │                                                  │    │ │
│  │  │  ┌──────────────────────────────────────────┐   │    │ │
│  │  │  │  DockerSession                            │   │    │ │
│  │  │  │  (Socket 级通信)                           │   │    │ │
│  │  │  │                                          │   │    │ │
│  │  │  │  - exec_create() 创建交互式 bash          │   │    │ │
│  │  │  │  - socket.sendall() 发送命令              │   │    │ │
│  │  │  │  - socket.recv() 接收输出                 │   │    │ │
│  │  │  │  - 危险命令过滤                           │   │    │ │
│  │  │  └──────────────────────────────────────────┘   │    │ │
│  │  └──────────────────────────────────────────────────┘    │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件说明

#### DockerSandbox（`app/sandbox/core/sandbox.py`）

单个 Docker 容器的封装。创建时：

1. 通过 `docker.from_env()` 连接本地 Docker
2. 配置资源限制（内存、CPU、网络模式）
3. 在宿主机 `%TEMP%` 目录创建 volume 映射目录
4. 启动容器（`tail -f /dev/null` 保持运行）
5. 初始化 `AsyncDockerizedTerminal` 交互终端

支持操作：

- `run_command(cmd, timeout)` — 在容器内执行 Shell 命令
- `read_file(path)` — 读取容器内文件
- `write_file(path, content)` — 写入容器内文件
- `copy_from(container_path, local_path)` — 从容器复制文件到宿主机
- `copy_to(local_path, container_path)` — 从宿主机复制文件到容器

文件传输通过 **tar 归档** 实现（Docker API 的标准方式）。

#### AsyncDockerizedTerminal（`app/sandbox/core/terminal.py`）

在容器内维护一个**持久的 bash 会话**。通过 Docker Exec + Socket 实现：

1. `exec_create` 创建 exec 实例，启动 `bash --norc --noprofile`
2. `exec_start` 获取 socket 连接，设为非阻塞模式
3. 后续命令通过 socket 发送，通过 `$ ` 提示符识别输出边界
4. 支持超时控制（`asyncio.wait_for`）

#### DockerSession（`app/sandbox/core/terminal.py`）

底层 Socket 通信层：

- 非阻塞 I/O（`socket.setblocking(False)`）
- 循环读取直到出现 `$ ` 提示符
- 内置命令安全检查（拒绝 `rm -rf /`、`mkfs`、fork 炸弹等）

#### SandboxManager（`app/sandbox/core/manager.py`）

多沙箱实例管理器：

| 参数                 | 默认值  | 说明         |
| -------------------- | ------- | ------------ |
| `max_sandboxes`    | 100     | 最大沙箱数量 |
| `idle_timeout`     | 3600 秒 | 空闲回收时间 |
| `cleanup_interval` | 300 秒  | 清理检查间隔 |

特性：

- 自动拉取 Docker 镜像（`ensure_image`）
- 并发控制（每个沙箱独立 `asyncio.Lock`）
- 自动清理空闲沙箱（后台 `asyncio.Task`）
- 优雅关闭（`cleanup()` 并发清理所有沙箱，30 秒超时）

#### LocalSandboxClient（`app/sandbox/client.py`）

对外暴露的统一接口，模块级单例 `SANDBOX_CLIENT`：

```python
from app.sandbox.client import SANDBOX_CLIENT

# 创建沙箱
await SANDBOX_CLIENT.create(config, volume_bindings)

# 执行命令
output = await SANDBOX_CLIENT.run_command("python -c 'print(1+1)'")

# 文件操作
await SANDBOX_CLIENT.write_file("/workspace/script.py", "print('hello')")
content = await SANDBOX_CLIENT.read_file("/workspace/script.py")
await SANDBOX_CLIENT.copy_to("./local.csv", "/workspace/data.csv")

# 清理
await SANDBOX_CLIENT.cleanup()
```

### 3.3 部署步骤

#### 前置条件

1. **安装 Docker Desktop**（Windows）

   - 下载：https://www.docker.com/products/docker-desktop/
   - 安装后确保 Docker Engine 正在运行（任务栏鲸鱼图标）
   - 验证：`docker --version` 和 `docker ps`
2. **Python 环境**

   ```powershell
   # 确认在正确的 conda 环境中
   conda activate open_manus

   # 安装 docker Python SDK
   pip install docker
   ```

#### 配置启用

编辑 `config/config.toml`，取消注释并修改 `[sandbox]` 段：

```toml
[sandbox]
use_sandbox = true                # 启用沙箱
image = "python:3.12-slim"        # Docker 镜像
work_dir = "/workspace"           # 容器内工作目录
memory_limit = "512m"             # 内存限制 (支持: 512m, 1g, 2g)
cpu_limit = 1.0                   # CPU 核心数限制
timeout = 300                     # 命令默认超时(秒)
network_enabled = false           # 是否允许网络访问
```

#### 拉取镜像（可选，提前准备）

```powershell
docker pull python:3.12-slim
```

`SandboxManager` 在创建沙箱时会自动拉取镜像，但提前拉取可以避免首次运行的等待。

#### 验证部署

```python
# 测试脚本 test_sandbox.py
import asyncio
from app.config import config, SandboxSettings
from app.sandbox.client import create_sandbox_client

async def test():
    client = create_sandbox_client()
    await client.create(config=config.sandbox)

    # 测试命令执行
    result = await client.run_command("python -c 'print(1 + 1)'")
    print(f"命令执行结果: {result}")

    # 测试文件写入
    await client.write_file("/workspace/hello.txt", "Hello Sandbox!")
    content = await client.read_file("/workspace/hello.txt")
    print(f"文件内容: {content}")

    await client.cleanup()
    print("测试通过！")

asyncio.run(test())
```

### 3.4 当前集成状态

> **集成状态**：Docker Sandbox 已通过 Web 层接入——`agent_runner.py` 创建会话时可注入沙箱（`set_sandbox()`），DataAnalysis / QuickQuery / WechatPublish 的执行类工具改为在容器内执行。`main.py` / `run_flow.py` 的 CLI 路径默认仍走本地多进程。

---

## 4. 运行指南

### 4.1 两种运行模式

#### 模式一：单智能体（`python main.py`）

```powershell
# 交互式
python main.py
# 输出: Enter your prompt: _

# 命令行参数
python main.py --prompt "帮我写一个冒泡排序的 Python 函数"

# 指定使用哪个 LLM 配置（需要 config.toml 中有对应配置段）
# 默认使用 [llm]，可通过代码指定
```

**执行流程**：

```
main.py → Manus.create() → agent.run(prompt)
         → think() ↔ act() 循环
         → PythonExecute (多进程) / BrowserUseTool / StrReplaceEditor
```

#### 模式二：多智能体编排（`python run_flow.py`）

```powershell
# 交互式
python run_flow.py
# 输出: Enter your prompt: _

# 启用 DataAnalysis Agent（需在 config.toml 中配置）
```

**执行流程**：

```
run_flow.py → 创建 Manus + (可选) DataAnalysis
           → FlowFactory.create_flow(PLANNING)
           → LLM 生成执行计划
           → 逐步执行，每步选择最合适的 Agent
           → 各 Agent 通过各自工具完成任务
```

**config.toml 配置**：

```toml
[runflow]
use_data_analysis_agent = true   # 启用数据分析智能体
```

当 `use_data_analysis_agent = true` 时，LLM 会在生成计划时看到两个可选 Agent：

| Agent            | 标签                | 适用步骤类型                    |
| ---------------- | ------------------- | ------------------------------- |
| `Manus`        | `[MANUS]`         | 网页浏览、文件编辑、Python 执行 |
| `DataAnalysis` | `[DATA_ANALYSIS]` | 数据处理、图表可视化、数据报告  |

### 4.2 模式选择决策树

```
需要执行什么任务？
│
├─ 简单代码执行 / 文本处理
│   └─ python main.py （单智能体，本地多进程）
│
├─ 需要多个专业 Agent 协作
│   └─ python run_flow.py （多智能体编排）
│
└─ 需要容器级安全隔离
    └─ 自行编写代码调用 SANDBOX_CLIENT （Docker Sandbox 手动集成）
```

### 4.3 运行前置条件汇总

```powershell
# 1. 确认 Python 环境
C:\Users\hyh\anaconda3\envs\open_manus\python.exe --version
# 应输出: Python 3.12.x

# 2. 确认依赖已安装
pip list | findstr "openai docker pydantic playwright"

# 3. 确认配置文件存在
ls config\config.toml
# 应输出: config\config.toml

# 4. 确认 API Key 已配置
# 检查 config.toml 中 api_key 字段不是 "YOUR_API_KEY"
```

### 4.4 工作空间

所有模式共享同一个工作空间目录：

```
C:\Code\OpenManus\workspace\
```

Agent 执行 Python 代码时，`config.workspace_root` 指向此目录。代码中可以用以下方式引用：

```python
from app.config import config
print(config.workspace_root)  # C:\Code\OpenManus\workspace
```

---

## 5. 配置参考

### 5.1 完整配置项速查

#### `[llm]` — LLM 配置（所有模式必需）

```toml
[llm]
model = "claude-sonnet-4-20250514"    # 模型名称
base_url = "https://api.anthropic.com/v1/"  # API 地址
api_key = "sk-ant-..."                 # API 密钥
max_tokens = 8192                      # 最大输出 token
temperature = 0.0                      # 随机性 (0.0-1.0)
```

#### `[sandbox]` — Docker Sandbox 配置

```toml
[sandbox]
use_sandbox = false                    # ⚠️ 暂未使用
image = "python:3.12-slim"             # Docker 镜像
work_dir = "/workspace"                # 容器内工作目录
memory_limit = "512m"                  # 内存限制 (512m, 1g, 2g...)
cpu_limit = 1.0                        # CPU 核心数
timeout = 300                          # 命令超时 (秒)
network_enabled = false                # 网络访问开关
```

#### `[runflow]` — 多智能体编排配置

```toml
[runflow]
use_data_analysis_agent = false        # 启用 DataAnalysis Agent
```

#### `[browser]` — 浏览器配置（影响 Manus agent）

```toml
[browser]
headless = false                       # 无头模式
disable_security = true                # 禁用安全策略
chrome_instance_path = ""              # Chrome 路径 (留空=使用 Playwright 自带)
```

#### `[search]` — 搜索引擎配置

```toml
[search]
engine = "Google"                      # 主引擎 (Google/Baidu/DuckDuckGo/Bing)
fallback_engines = ["DuckDuckGo", "Baidu", "Bing"]
```

### 5.2 推荐配置组合

#### 开发环境（最低配置）

```toml
[llm]
model = "claude-sonnet-4-20250514"
base_url = "https://api.anthropic.com/v1/"
api_key = "sk-ant-..."
max_tokens = 8192
temperature = 0.0

[runflow]
use_data_analysis_agent = false
```

#### 数据分析环境

```toml
[llm]
model = "claude-sonnet-4-20250514"
base_url = "https://api.anthropic.com/v1/"
api_key = "sk-ant-..."
max_tokens = 8192
temperature = 0.0

[runflow]
use_data_analysis_agent = true

[sandbox]
use_sandbox = true
network_enabled = true   # 数据分析可能需要联网下载数据
```

---

## 6. 常见问题排查

### 6.1 通用问题

#### Q: 提示 "Empty prompt provided"

**原因**：直接按了回车，没有输入任务描述。

**解决**：输入具体的任务描述，例如：

```
Enter your prompt: 帮我爬取 https://example.com 的新闻标题
```

#### Q: 运行很久没有输出

**原因**：

1. LLM API 调用卡住（网络问题或 API 限流）
2. Agent 进入了较长的工具调用链
3. 浏览器操作耗时较长

**排查**：

```powershell
# 检查网络连通性
curl -I https://api.anthropic.com

# 检查日志输出（logger 会打印每个步骤）
# 正常日志示例：
# ✨ Manus's thoughts: ...
# 🛠️ Manus selected 1 tools to use
# 🔧 Activating tool: 'python_execute'...
# 🎯 Tool 'python_execute' completed its mission!
```

#### Q: 执行超时错误

**现象**：`Command execution timed out after 30 seconds`

**原因**：代码执行时间超过 30 秒（多进程模式）或配置的超时时间。

**解决**：

- 多进程模式：修改 `PythonExecute.execute(timeout=...)` 默认值
- Docker Sandbox：修改 `config.toml` 中 `[sandbox].timeout`

### 6.2 LLM / API 问题

#### Q: "Error: Invalid API key"

**原因**：`config.toml` 中 `api_key` 未配置或错误。

**解决**：

1. 检查 `config/config.toml` 是否存在
2. 确认 `api_key` 字段不是 `"YOUR_API_KEY"`
3. 从对应平台重新获取有效的 API Key

#### Q: "Token limit exceeded"

**现象**：`🚨 Token limit error: ...`

**原因**：对话上下文超过了模型的 token 上限。

**解决**：

1. 减少单次任务复杂度，拆分为多个小任务
2. 增大 `max_tokens` 配置
3. 使用支持更大上下文的模型

### 6.3 Docker Sandbox 问题

#### Q: "docker.errors.DockerException: Error while fetching server API version"

**原因**：Docker Desktop 未启动或未安装。

**解决**：

```powershell
# 检查 Docker 是否运行
docker ps

# 如果报错，启动 Docker Desktop
# Windows: 在开始菜单找到 "Docker Desktop" 并启动
# 等待任务栏鲸鱼图标变为静止状态
```

#### Q: "Failed to pull image python:3.12-slim"

**原因**：网络问题导致无法从 Docker Hub 拉取镜像。

**解决**：

```powershell
# 手动拉取
docker pull python:3.12-slim

# 如果国内网络慢，配置 Docker 镜像加速器
# Docker Desktop → Settings → Docker Engine → 添加 registry-mirrors
```

#### Q: "Maximum number of sandboxes (100) reached"

**原因**：创建了过多沙箱实例未释放。

**解决**：

1. 正常情况下 `SandboxManager` 会自动回收空闲沙箱（3600s 超时）
2. 手动清理：

```powershell
# 查看运行中的 sandbox 容器
docker ps --filter "name=sandbox_"

# 手动删除
docker rm -f sandbox_<id>
```

### 6.4 Python 环境问题

#### Q: ImportError: No module named 'xxx'

**原因**：缺少 Python 依赖。

**解决**：

```powershell
# 确认在正确的 conda 环境
conda activate open_manus

# 安装项目依赖
pip install -r requirements.txt

# 安装可选依赖
pip install playwright
playwright install
```

#### Q: 中文编码问题（Windows）

**现象**：中文输出显示乱码。

**解决**：

```powershell
# 设置终端编码
chcp 65001

# 或在 PowerShell 中
[Console]::OutputEncoding = [Text.Encoding]::UTF8
```

---

## 附录 A：项目文件结构速查

```
OpenManus/
├── main.py                    # 单智能体入口 (Manus)
├── run_flow.py                # 多智能体编排入口 (PlanningFlow)
├── config/
│   ├── config.toml            # ⚠️ 主配置文件（需手动创建）
│   └── config.example.toml    # 配置模板
├── app/
│   ├── agent/
│   │   ├── base.py            # BaseAgent (导入了 SANDBOX_CLIENT)
│   │   ├── react.py           # ReActAgent (think+act 循环)
│   │   ├── toolcall.py        # ToolCallAgent (LLM 工具调用)
│   │   ├── manus.py           # Manus (通用智能体, 本地多进程)
│   │   └── data_analysis.py   # DataAnalysis (数据分析智能体)
│   ├── sandbox/               # Docker Sandbox 模块
│   │   ├── client.py          # LocalSandboxClient + SANDBOX_CLIENT 单例
│   │   └── core/
│   │       ├── sandbox.py     # DockerSandbox 容器封装
│   │       ├── terminal.py    # AsyncDockerizedTerminal 终端接口
│   │       ├── manager.py     # SandboxManager 生命周期管理
│   │       └── exceptions.py  # 异常定义
│   ├── tool/
│   │   ├── python_execute.py  # PythonExecute (多进程执行)
│   ├── flow/
│   │   ├── base.py            # BaseFlow 基类
│   │   ├── planning.py        # PlanningFlow (多智能体编排)
│   │   └── flow_factory.py    # FlowFactory 工厂
│   └── config.py              # Config 单例 (配置加载)
├── workspace/                 # 工作空间目录
└── docs/
    └── sandbox-guide.md       # 📖 本手册
```

## 附录 B：关键概念速查

| 术语                    | 说明                                                   |
| ----------------------- | ------------------------------------------------------ |
| **Agent**         | 智能体，能自主使用工具完成任务的 AI 实体               |
| **Flow**          | 编排多个 Agent 协作执行的流程                          |
| **Tool**          | Agent 可调用的工具（Python执行、浏览器、文件编辑等）   |
| **ReAct**         | Reasoning + Acting 循环模式（think → act → observe） |
| **MCP**           | Model Context Protocol，用于连接远程工具服务器         |
| **sandbox_ 前缀** | Docker 容器命名规范，如`sandbox_a1b2c3d4`            |
