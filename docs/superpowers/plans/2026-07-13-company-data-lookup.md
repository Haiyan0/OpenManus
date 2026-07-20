# 公司数据本地查找功能 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 DataAnalysis agent 新增 CompanyDataLookup 工具，使其能在 `company_data_resource/` 目录中按企业名/项目名匹配本地 CSV 数据文件。

**Architecture:** 新增独立工具遵循 `BaseTool` 模式，扫描目录 → 子串匹配 → 返回结果。DataAnalysis 的 system prompt 引导 LLM 优先调用此工具。三层文件变更：新工具文件 → agent 集成 → 工具注册。

**Tech Stack:** Python 3.12, Pydantic, pathlib

## Global Constraints

- Python 版本: 3.12
- 工具必须继承 `app.tool.base.BaseTool`
- 返回类型使用 `ToolResult` 或 `fail_response()`
- 目录结构: `company_data_resource/{企业名}/{项目名}/*.csv`
- 匹配规则: 不区分大小写的子串匹配
- 新增文件编码: UTF-8

---

### Task 1: 创建 CompanyDataLookup 工具

**Files:**
- Create: `app/tool/company_data_lookup.py`

**Interfaces:**
- Produces: `CompanyDataLookup` 类，继承 `BaseTool`
  - `name: str = "company_data_lookup"`
  - `async execute(query: str) -> ToolResult`

- [ ] **Step 1: 编写 CompanyDataLookup 工具完整代码**

```python
"""
公司数据资源查找工具。

在 company_data_resource 目录中按企业名称和项目名称匹配用户的查询，
返回匹配的本地 CSV 数据文件列表，供数据分析使用。
"""

import os
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.logger import logger
from app.tool.base import BaseTool, ToolResult


class CompanyDataLookup(BaseTool):
    """在 company_data_resource 目录中查找与用户查询匹配的本地公司数据文件。"""

    name: str = "company_data_lookup"
    description: str = (
        "在 company_data_resource 目录中查找与用户查询匹配的本地公司数据文件。"
        "当用户提及公司、企业、业务数据分析时，优先调用此工具检查本地是否有相关数据。"
        "返回匹配的公司名称、项目名称及 CSV 文件列表。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用户的原始提问或数据分析需求描述，用于匹配公司名称和项目名称",
            },
        },
        "required": ["query"],
    }

    # 公司数据资源目录（相对于项目根目录）
    DATA_DIR: str = "company_data_resource"

    async def execute(self, query: str) -> ToolResult:
        """
        在 company_data_resource 中查找匹配的公司数据文件。

        流程：
        1. 检查 company_data_resource 目录是否存在
        2. 遍历企业子目录，子串匹配 query 中的企业名
        3. 命中后遍历项目子目录，子串匹配 query 中的项目名
        4. 收集匹配项目下所有 CSV 文件
        5. 返回结构化结果

        Args:
            query: 用户的原始提问或数据分析需求描述

        Returns:
            ToolResult: 匹配成功时 output 包含文件列表，失败时 error 包含提示
        """
        data_root = PROJECT_ROOT / self.DATA_DIR

        # 检查目录是否存在
        if not data_root.exists() or not data_root.is_dir():
            logger.warning(f"公司数据目录不存在: {data_root}")
            return self.fail_response(
                f"公司数据目录 '{self.DATA_DIR}' 不存在或不可访问。"
                f"请使用常规数据分析流程，直接通过用户提供的文件路径读取数据。"
            )

        query_lower = query.lower()

        try:
            # 遍历所有企业目录
            companies = [d for d in sorted(data_root.iterdir()) if d.is_dir()]
            if not companies:
                logger.warning(f"公司数据目录为空: {data_root}")
                return self.fail_response(
                    f"公司数据目录 '{self.DATA_DIR}' 下没有企业数据。"
                    f"请使用常规数据分析流程。"
                )

            for company_dir in companies:
                company_name = company_dir.name

                # 不区分大小写的子串匹配
                if company_name.lower() not in query_lower:
                    continue

                logger.info(f"命中企业: {company_name}")

                # 遍历项目目录
                projects = [
                    d for d in sorted(company_dir.iterdir()) if d.is_dir()
                ]
                for project_dir in projects:
                    project_name = project_dir.name

                    # 项目名也做子串匹配
                    if project_name.lower() not in query_lower:
                        continue

                    logger.info(f"命中项目: {company_name}/{project_name}")

                    # 收集该目录下所有 CSV 文件
                    csv_files = []
                    for file_path in sorted(project_dir.iterdir()):
                        if file_path.is_file() and file_path.suffix.lower() == ".csv":
                            rel_path = file_path.relative_to(PROJECT_ROOT)
                            csv_files.append(
                                {"name": file_path.name, "path": str(rel_path)}
                            )

                    if not csv_files:
                        return self.fail_response(
                            f"在 '{company_name}/{project_name}' 下未找到 CSV 数据文件。"
                            f"请使用常规数据分析流程。"
                        )

                    # 构建成功响应信息
                    file_lines = "\n".join(
                        f"  - {f['name']}（路径: {f['path']}）"
                        for f in csv_files
                    )
                    output_message = (
                        f"在 company_data_resource 中发现匹配的公司数据：\n"
                        f"  企业：{company_name}\n"
                        f"  项目：{project_name}\n"
                        f"  数据文件（共 {len(csv_files)} 个 CSV）：\n"
                        f"{file_lines}\n\n"
                        f"请使用 NormalPythonExecute（pandas.read_csv）读取上述文件进行数据分析，"
                        f"并在分析前告知用户已找到以下本地数据文件：{', '.join(f['name'] for f in csv_files)}"
                    )

                    return ToolResult(
                        output=output_message,
                        system=(
                            f"已匹配本地公司数据：企业={company_name}，项目={project_name}，"
                            f"文件数={len(csv_files)}。告知用户后自动读取 CSV 进行分析。"
                        ),
                    )

                # 命中企业但未命中具体项目 —— 列出可用项目供参考
                available_projects = [d.name for d in projects]
                return self.fail_response(
                    f"在 '{company_name}' 企业下未找到与查询完全匹配的项目。\n"
                    f"该企业下有以下可用项目：{', '.join(available_projects)}\n"
                    f"请确认用户需要分析哪个项目的数据，或提示用户补充项目名称。"
                )

            # 没有任何企业命中
            available_companies = [d.name for d in companies]
            logger.info(f"未命中任何企业，可用企业: {available_companies}")
            return self.fail_response(
                f"未在 company_data_resource 中找到与查询匹配的公司数据。\n"
                f"当前可用的企业数据：{', '.join(available_companies)}\n"
                f"请使用常规数据分析流程。"
            )

        except Exception as e:
            logger.error(f"CompanyDataLookup 执行出错: {e}", exc_info=True)
            return self.fail_response(f"查找公司数据时发生错误: {str(e)}")
```

- [ ] **Step 2: 验证文件语法正确**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "import ast; ast.parse(open('app/tool/company_data_lookup.py', encoding='utf-8').read()); print('语法检查通过')"
```

Expected: `语法检查通过`

- [ ] **Step 3: 提交**

```bash
git add app/tool/company_data_lookup.py
git commit -m "feat: add CompanyDataLookup tool for local company data matching"
```

---

### Task 2: 在工具注册中导出 CompanyDataLookup

**Files:**
- Modify: `app/tool/__init__.py`

**Interfaces:**
- Consumes: `CompanyDataLookup` from `app.tool.company_data_lookup`
- Produces: `CompanyDataLookup` 在 `__all__` 中导出

- [ ] **Step 1: 添加导入和导出**

将 `app/tool/__init__.py` 修改为以下内容（在现有导入后追加一行，在 `__all__` 中追加一项）：

```python
# 在现有导入区域追加
from app.tool.company_data_lookup import CompanyDataLookup

# __all__ 列表追加 'CompanyDataLookup'
```

具体编辑：

在文件头部的 import 区域末尾（`from app.tool.web_search import WebSearch` 之后）添加：
```python
from app.tool.company_data_lookup import CompanyDataLookup
```

在 `__all__` 列表中添加 `"CompanyDataLookup"`。

- [ ] **Step 2: 验证导入**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "from app.tool.company_data_lookup import CompanyDataLookup; print('导入成功:', CompanyDataLookup().name)"
```

Expected: `导入成功: company_data_lookup`

- [ ] **Step 3: 提交**

```bash
git add app/tool/__init__.py
git commit -m "feat: export CompanyDataLookup in tool __init__"
```

---

### Task 3: 集成 CompanyDataLookup 到 DataAnalysis Agent

**Files:**
- Modify: `app/agent/data_analysis.py`

**Interfaces:**
- Consumes: `CompanyDataLookup` from `app.tool.company_data_lookup`
- Produces: DataAnalysis agent 使用新工具和更新后的 system prompt

- [ ] **Step 1: 更新 data_analysis.py 完整代码**

将 `app/agent/data_analysis.py` 修改为：

```python
from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.prompt.visualization import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.chart_visualization.chart_prepare import VisualizationPrepare
from app.tool.chart_visualization.data_visualization import DataVisualization
from app.tool.chart_visualization.python_execute import NormalPythonExecute
from app.tool.company_data_lookup import CompanyDataLookup


class DataAnalysis(ToolCallAgent):
    """
    A data analysis agent that uses planning to solve various data analysis tasks.

    This agent extends ToolCallAgent with a comprehensive set of tools and capabilities,
    including Data Analysis, Chart Visualization, Data Report.
    """

    name: str = "Data_Analysis"
    description: str = "An analytical agent that utilizes python and data visualization tools to solve diverse data analysis tasks"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 15000
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            CompanyDataLookup(),
            NormalPythonExecute(),
            VisualizationPrepare(),
            DataVisualization(),
            Terminate(),
        )
    )
```

- [ ] **Step 2: 更新 system prompt 模板**

将 `app/prompt/visualization.py` 的 `SYSTEM_PROMPT` 修改为：

```python
SYSTEM_PROMPT = """You are an AI agent designed to data analysis / visualization task. You have various tools at your disposal that you can call upon to efficiently complete complex requests.
# Note:
1. The workspace directory is: {directory}; Read / write file in workspace
2. The company data directory is: company_data_resource/; When user mentions company/enterprise/business data analysis, FIRST call company_data_lookup tool to check for matching local CSV data before using other tools
3. If company_data_lookup returns matched data files, always inform the user about the found files, then automatically use NormalPythonExecute (pandas.read_csv) to load and analyze them
4. Generate analysis conclusion report in the end"""
```

- [ ] **Step 3: 验证 agent 工具加载**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
from app.agent.data_analysis import DataAnalysis
agent = DataAnalysis()
print('Tools:', [t.name for t in agent.available_tools])
print('company_data_lookup' in agent.available_tools.tool_map)
"
```

Expected:
```
Tools: ['company_data_lookup', 'normal_python_execute', 'visualization_preparation', 'data_visualization', 'terminate']
True
```

- [ ] **Step 4: 验证 CompanyDataLookup 工具实际运行**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
import asyncio
from app.tool.company_data_lookup import CompanyDataLookup

async def test():
    tool = CompanyDataLookup()
    result = await tool.execute(query='分析元梦空间 元租房空间的订单数据')
    print('Output:', result.output)
    print('Error:', result.error)

asyncio.run(test())
"
```

Expected: 输出应包含找到的 CSV 文件列表。

- [ ] **Step 5: 提交**

```bash
git add app/agent/data_analysis.py app/prompt/visualization.py
git commit -m "feat: integrate CompanyDataLookup into DataAnalysis agent"
```

---

### Task 4: 运行完整功能验证

**Files:**
- (无新建或修改 — 纯验证步骤)

- [ ] **Step 1: 验证未匹配场景（不应该找到数据）**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
import asyncio
from app.tool.company_data_lookup import CompanyDataLookup

async def test():
    tool = CompanyDataLookup()
    result = await tool.execute(query='分析一下全球气候变暖趋势')
    print('Matched:', result.error is None)
    print('Error:', result.error)

asyncio.run(test())
"
```

Expected: `Matched: False`，error 提示未找到匹配。

- [ ] **Step 2: 验证目录不存在时的容错**

```bash
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
import asyncio
from app.tool.company_data_lookup import CompanyDataLookup

async def test():
    tool = CompanyDataLookup()
    tool.DATA_DIR = 'nonexistent_dir'
    result = await tool.execute(query='分析元梦空间')
    print('Error:', result.error)

asyncio.run(test())
"
```

Expected: error 提示目录不存在。

- [ ] **Step 3: 运行完整测试**

```bash
cd C:\Code\OpenManus
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/ -v --tb=short -x -q 2>&1 | head -40
```

Expected: 现有所有测试通过，无回归。

- [ ] **Step 4: 提交（如有测试文件变更）**

```bash
git add tests/
git commit -m "test: add company data lookup verification tests"
```
