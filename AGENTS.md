# AGENTS.md

面向 OpenCode/Claude Code 等 AI 编码助手的仓库工作指南。架构详解见 `CLAUDE.md`（权威），本文件只补充其中未覆盖或易踩坑的高信号事实。

## Python 解释器（关键）

本机台 Python 固定为 conda 环境，**不要用** `python` / `python3`：

```
C:\Users\hyh\anaconda3\envs\open_manus\python.exe
```

脚本运行于 PowerShell + Win11。所有 `python ...` 命令请替换为该绝对路径。

## 安装与配置陷阱

- **不要用 `pip install -e .` / `python setup.py`**：`setup.py` 第 4 行 `open("README.md")` 但仓库只有 `README_zh.md`，会直接报 FileNotFoundError。请用 `uv pip install -r requirements.txt`。
- 多环境配置：`OPENMANUS_ENV`（或入口位置参数 `[dev|test]`，经 `entry.py` 桥接）选择 `config/config_{env}.toml`；`dev` 缺失回退 `config.example.toml`，非 `dev` 缺失报错。`config/config_dev.toml`、`config/config_test.toml`、`config/mcp.json` 被 gitignore，**本地已存在**，无需重建。配置模板见 `config/config.example.toml`（含 Azure/Bedrock/Ollama/Jiekou 等多个 `[llm]` 注释模板）。
- 浏览器自动化可选：`playwright install`。
- `.env`（可选）覆盖配置文件的 `[web]` 段，键名前缀 `OPENMANUS_`（见 `.env.example`）。

## 入口脚本

| 命令 | 用途 |
|------|------|
| `python main.py [dev\|test] [--prompt "..."]` | 交互/单任务 Manus 智能体（CLI） |
| `python run_flow.py [dev\|test]` | PlanningFlow 多智能体编排（**整体 60 分钟硬超时**） |
| `python web_run.py [dev\|test]` | FastAPI Web 后端，监听 `0.0.0.0:8080`，前端见 `web_ui/` |
| `python sandbox_main.py [dev\|test]` | Docker 沙箱版 Manus |
| `python run_mcp_server.py [dev\|test]` / `run_mcp.py [dev\|test]` | MCP 服务端 / MCP 智能体客户端 |

环境位置参数须紧跟脚本名（`python xxx.py dev`），默认 `dev`。

## Lint / 格式化（提交前必跑）

CLAUDE.md 未提：仓库用 pre-commit（`.pre-commit-config.yaml`），链路为 **black → autoflake → isort**：

```
pre-commit run --all-files
# 或单独：black . && autoflake -i -r . && isort .
```

isort profile=black，且 `--lines-after-imports=2`；autoflake 会移除未用 import/变量，但 `__init__.py` 被排除——别手改 `__init__.py` 的导入。

## 测试要点

- 根目录 `pytest.ini` 已启用 `asyncio_mode = auto`，异步测试**无需**显式 `@pytest.mark.asyncio` 标记。
- 跑单个测试：`python -m pytest tests/sandbox/test_sandbox.py::test_sandbox_python_execution -v`（用 `-m pytest` 避免入口被 `main.py` 拦截）。
- **`tests/web/conftest.py` 的 autouse async fixture 不可删**：它在每个异步测试后于同 loop 上 dispose 数据库引擎连接池，否则 aiomysql 连接跨 event loop GC 会触发 `AttributeError: 'NoneType' object has no attribute 'send'`。新增 web 测试需保留。
- web 测试依赖 `[web]` MySQL 配置；配置文件中 `data_lookup_mode = "local"` 时走 `company_data_resource/`（本地，gitignore），`= "mysql"` 时实时查库。
- 沙箱测试需 Docker Desktop 运行中。

## Web 子系统（CLAUDE.md 已覆盖架构，此处补充操作细节）

- 前端是独立 Vue3 项目 `web_ui/`（Vite + Pinia + Tailwind）。`python web_run.py` 服务 `web_ui/dist` 构建产物；改前端须 `npm run build` 后再起后端。
- 另有 npm 子项目 `app/tool/chart_visualization/`（TypeScript + VChart，由 `DataVisualization` 工具调用），用 ts-node 运行 `src/chartVisualize.ts`。
- Web 后端启动会清理孤儿 Sandbox 容器（lifespan 钩子）；多用户隔离依赖 MySQL + JWT（`jwt_secret_key` 生产必改）。

## 运行期目录（均 gitignore，勿提交）

`workspace/`（智能体工作区）、`logs/`、`data/`、`company_data_resource/`（本地大数据 CSV）。`workspace/` 是智能体读写文件默认根，`WORKSPACE_ROOT` 见 `app/config.py:16`。

## 交流与编码规范（来自 CLAUDE.md，必须遵守）

- 计划、审查、逻辑解释用**中文**；代码注释用**简体中文**；标识符保持英文。
- 收到任务先查 skill；功能需求先用 brainstorming skill 做需求分析；写代码前先写测试（TDD）；声称完成前必须运行验证命令。
