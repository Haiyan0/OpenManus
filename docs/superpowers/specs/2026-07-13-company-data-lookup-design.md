# 公司数据本地查找功能 — 设计规格

**日期**: 2026-07-13
**状态**: 设计中
**分支**: feat/web-chat

---

## 1. 背景与动机

DataAnalysis agent 当前只能使用 `NormalPythonExecute` 等工具做通用数据分析，无法感知本地已有的公司数据资源。用户希望当提到公司/项目相关分析时，agent 能自动发现并使用 `company_data_resource/` 下的本地 CSV 数据，避免用户手动指定文件路径。

## 2. 需求概述

- **触发条件**: 用户消息中命中了 `company_data_resource/` 下某企业名称或项目名称（关键词匹配 + LLM 智能判断）
- **匹配逻辑**: 先按目录名（企业 → 项目）子串匹配，命中后列出 CSV 文件，由 LLM 判断是否与用户需求相关
- **行为**: 匹配后先告知用户发现了哪些本地数据，然后自动读取并用 Python 分析
- **实现方式**: 新增独立的 `CompanyDataLookup` 工具（选项 A）

## 3. 文件变更清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `app/tool/company_data_lookup.py` | **新增** | 公司数据查找工具 |
| `app/agent/data_analysis.py` | **修改** | 引入新工具 + 更新 system prompt |
| `app/tool/__init__.py` | **修改** | 导出 `CompanyDataLookup` |

## 4. 组件设计

### 4.1 CompanyDataLookup 工具

```
类名: CompanyDataLookup(BaseTool)
工具名: company_data_lookup
描述: 在 company_data_resource 目录中查找与用户查询匹配的本地公司数据文件
```

**参数**:
- `query` (string, required) — 用户的原始提问或需求描述

**核心流程**:
1. 读取 `company_data_resource/` 顶层目录，获取所有企业名称（文件夹名）
2. 在 query 中做子串匹配，检查是否命中任一企业名
3. 若命中，进入该企业目录，对项目名（子文件夹）做同样匹配
4. 收集匹配项目下的所有 CSV 文件的完整路径和文件名
5. 返回结构化 JSON

**返回格式**:
```json
{
  "matched": true/false,
  "company": "元梦空间",
  "project": "元租房空间项目数据",
  "files": [
    {"name": "tan_core_group_part_20260710_171809.csv", "path": "company_data_resource/元梦空间/元租房空间项目数据/tan_core_group_part_20260710_171809.csv"},
    ...
  ],
  "message": "在 company_data_resource 中发现匹配的公司数据：元梦空间/元租房空间项目数据，共 4 个 CSV 文件"
}
```

**未匹配时的返回**:
```json
{
  "matched": false,
  "company": null,
  "project": null,
  "files": [],
  "message": "未在 company_data_resource 中找到与查询匹配的公司数据，请使用常规数据分析流程"
}
```

**目录结构假设**:
```
company_data_resource/
  {企业名}/
    {项目名}/
      *.csv
```

### 4.2 DataAnalysis Agent 修改

**System Prompt 追加内容**:
```
# Company Data Resource:
1. The company data directory is: company_data_resource/
2. When user mentions company/enterprise data analysis, FIRST call `company_data_lookup` with the user's query to check for local data
3. If matched, inform the user about found data files, then use `NormalPythonExecute` (pandas) to read and analyze the CSV files
4. If not matched, proceed with normal data analysis workflow
```

**Tools 追加**: 在 `available_tools` 的 `ToolCollection` 中加入 `CompanyDataLookup()`

### 4.3 工具注册

在 `app/tool/__init__.py` 中导出 `CompanyDataLookup`，与其他工具保持一致。

## 5. 匹配规则详解

### 5.1 企业名称匹配
- 获取 `company_data_resource/` 下所有子目录名作为企业名称列表
- 遍历企业名称，检查是否为 `query` 的子串（`in` 操作）
- 不区分大小写（全转小写后比较）

### 5.2 项目名称匹配
- 命中企业后，对该企业目录下所有子目录（项目名）做同样匹配
- 支持部分匹配（如 query 含"租房"，命中"元租房空间项目数据"）

### 5.3 LLM 二次判断
- 工具返回文件列表后，由 DataAnalysis agent（LLM）结合用户需求判断哪些 CSV 文件是真正相关的
- 这一判断在 agent 的 `think()` 阶段自然完成，无需额外代码

## 6. 错误处理

- `company_data_resource/` 目录不存在 → 返回 `matched: false` + 目录不存在的提示
- 目录存在但无 CSV 文件 → 返回 `matched: true` + 空文件列表 + 相应提示
- 目录遍历异常 → 捕获异常，返回 `fail_response`

## 7. 测试策略

- **单元测试**: `CompanyDataLookup.execute()` 的各种场景（命中/未命中/空目录/目录不存在）
- **集成测试**: DataAnalysis agent 在 system prompt 引导下是否实际调用了 `company_data_lookup`

## 8. 优先级

**P0** — 核心功能，直接交付
