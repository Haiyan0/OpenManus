# 按项目分档的业务数据说明文档 — 设计

日期：2026-08-19
状态：已确认，待实现

## 1. 背景与问题

DataAnalysis / QuickQuery 智能体通过 `CompanyDataLookup` 工具查询业务数据库：先用
`list_tables` 拉取 information_schema 数据字典（表名、字段名、类型、注释），再自行编写
SELECT SQL 拉数分析。

问题：仅凭表注释和字段注释，模型对业务口径的理解经常出错——不知道哪个字段是
"合同金额"、两张表如何关联、状态枚举值含义、常见查询模式。表/字段注释不足以承载
这些业务知识。

方案：引入**按项目分档的业务说明文档**，由人工维护，agent 在查询前按需读取，
降低 SQL 与口径错误率。

## 2. 目标与非目标

### 目标

- 每个项目一份业务说明文档（markdown 模板化），git 版本管理
- agent 按需读取：用户提到企业/项目名时优先读文档，再写 SQL
- 文档缺失时降级走原流程，绝不阻塞
- local / mysql 双数据模式通用

### 非目标（明确不做）

- 不做前端项目选择 UI、不做会话级 project 字段（定位靠用户提问自然提及 + 清单 action）
- 不做文档的在线编辑/管理界面（人工直接编辑文件）
- 不做文档自动生成（从数据字典自动反推文档）
- 不新增 config 配置项（文档根目录用类常量，对齐 `DATA_DIR` 先例）

## 3. 方案概览

采用**方案 A：按需工具拉取**（备选：list_tables 自动附带文档——上下文浪费、耦合；
system prompt 静态注入——上下文爆炸，已排除）。

```
用户提到企业/项目 → get_doc 读对应项目业务文档（字段口径/表关联/SQL 示例）
   未命中或未提及项目 → list_projects 列项目清单（含有无文档）确认归属
                  → list_tables 核对表结构 → 反驳自省 → query
```

## 4. 文档资产

### 目录结构

项目根新建 `project_docs/`（与 `company_data_resource/` 平级、结构对齐）：

```
project_docs/
├── TEMPLATE.md                      # 文档模板（维护者复制填写）
└── 示例企业/                         # 示例：企业目录
    └── 示例项目/                     # 示例：项目目录
        └── 业务说明.md               # 该项目的业务文档（目录下所有 .md 合并返回）
```

- 文档根：新模块 `app/tool/project_docs.py` 定义模块常量 `DOCS_DIR = "project_docs"`
  （对齐 `DATA_DIR = "company_data_resource"` 的常量先例；CompanyDataLookup 只做分发，
  不重复定义）
- 一个项目一个目录；目录下所有 `.md` 文件按文件名排序拼接返回
  （允许拆分为 `01-字段口径.md`、`02-SQL示例.md` 等多文件）

### 模板章节（TEMPLATE.md）

1. **项目概述**：项目是什么、核心业务对象、数据来源
2. **涉及数据表**：本项目相关的表清单（主键、时间字段）
3. **字段口径说明**（核心章节）：关键字段的业务含义、枚举值、单位、
   易用错的字段与正确替代（如"合同金额用 xxx 字段，勿用 yyy"）
4. **表关联关系**：JOIN 键、一对多/多对一、关联时的坑（去重、时间对齐）
5. **常用查询 SQL 示例**：2-5 个高频查询的完整 SQL 模板
6. **注意事项**：数据更新频率、脏数据、特殊业务规则

同时提交一份**填充好的示例文档**（`示例企业/示例项目/业务说明.md`），
既是示例也是冒烟测试对象。

### 编写约定（模板头部固化）

> 本文档只描述表、字段、SQL 口径与业务规则，**不包含任何文件路径**
> （数据获取统一走 company_data_lookup 的 query action，路径由工具自动告知）。

文档读取在宿主机、数据处理在 sandbox（容器内路径）——文档内容若写宿主机路径，
模型会拿着容器外的路径去容器内读而失败；此约定从源头消除该混淆。

## 5. 工具扩展：CompanyDataLookup

### 新增 action（签名保持兼容）

`execute(action, query_or_sql)` 签名不变，`action` 枚举扩为 4 个：

| action | query_or_sql 语义 | 行为 |
|--------|------------------|------|
| `list_projects` | 可选（空串即可，可传企业名过滤） | 列出 project_docs 下全部 企业/项目 及有无文档 |
| `get_doc` | 企业名/项目名（自由文本） | 匹配并返回该项目的业务文档 |
| `list_tables` / `query` | 不变 | 不变 |

`parameters.required` 从 `["action", "query_or_sql"]` 放宽为 `["action"]`
（对现有调用无破坏）。

`description` 与 `parameters` 同步补充两个新 action 说明，使用流程引导改为：

> 先 `get_doc` 读项目业务文档（若有）→ 再 `list_tables` 核对表结构 → `query` 执行

### 模块拆分：`app/tool/project_docs.py`（新文件）

`company_data_lookup.py` 已 600+ 行且自带 local/mysql 双模式；文档检索是独立职责，
拆为纯函数模块（只依赖标准库 + `ToolResult`，无状态、好单测）：

```python
DOCS_DIR = "project_docs"

def list_projects(query: str = "", root: Path | None = None) -> ToolResult
def get_doc(query: str, root: Path | None = None) -> ToolResult
```

- `root` 缺省为 `PROJECT_ROOT / DOCS_DIR`，测试注入 tmp_path
- CompanyDataLookup.execute 顶部加分发（约 6 行），先于 local/mysql 分发判断；
  文档机制与数据模式无关，两种模式均可用

### 匹配算法（与现有 local 模式同构）

1. query 含 `/` 且路径存在 → 精确命中
2. 企业名 in query（子串、忽略大小写）→ 命中企业；企业内再项目名 in query
   → 唯一项目 → 返回文档
3. 未命中企业名 → 全树搜项目名：唯一命中 → 返回；多命中 → 列出候选
   （`企业/项目` 完整路径）；零命中 → 返回可用项目清单

### 返回格式与上下文保护

- 文档 ≤ 8000 字符（按 `len(str)` 计字符数）：全文走 output
- 文档 > 8000 字符：output 给前 2000 字符摘要 + 来源说明（相对路径、字符数）；
  全文走 `ToolResult.system`（沿用 `_list_tables` 数据字典的双通道先例，
  不受 `max_observe` 截断）
- output 始终带文档来源（如"已读取 `示例企业/示例项目/业务说明.md`"），
  保证前端（Web 聊天 tool 消息落库）可见 agent 读了哪份文档

## 6. prompt 流程改造

`app/prompt/quick_query.py` 与 `app/prompt/visualization.py` 的
"company_data_lookup 使用流程"同步改造（在 list_tables 之前插入文档步骤）：

```
a. 用户提到明确企业/项目名 → 先 get_doc 读业务文档（字段口径/表关联/SQL 示例，
   文档口径优先于表注释）
b. 文档未命中或用户未提及项目 → 按需 list_projects 确认项目归属
   （纯通用查询可直接跳过，跳到 c —— 不违背 QuickQuery「最少步骤」原则）
c. list_tables 拿表结构
d. 反驳自省（比对 用户需求 + 文档口径 + 表字段 三方覆盖）
e. query 执行 → python_execute 分析
```

关键平衡：**文档是加速器不是门槛**——读不到文档时流程照走，绝不因无文档而
阻塞或反复重试。

## 7. 错误处理与降级

| 场景 | 行为 |
|------|------|
| `project_docs/` 目录不存在 | 返回"未配置项目业务文档，可直接 list_tables"，不报错阻塞 |
| 项目目录存在但无 .md | list_projects 标注"[无文档]"；get_doc 提示该文档未维护 |
| get_doc 多命中 | 列候选（`企业/项目` 完整路径），让 agent 精确重试 |
| get_doc 零命中 | 返回可用项目清单 + 提示走 list_tables |
| 文档读取异常（编码/权限） | 返回错误原因 + 引导 list_tables |

## 8. 前端可见性

文档全文走 system 通道 → 不落库为 tool 消息，前端只看到 output 摘要。
get_doc 的 output 摘要带文档来源（第 5 节），用户能知道 agent 读了哪份文档。
与 list_tables 的落库表现一致，**无需改动 ws_handler 与前端**。

## 9. 测试策略

### 新增 `tests/tool/test_project_docs.py`（核心测试）

用 tmp_path 搭建 project_docs 目录树，注入 `root` 参数：

| 测试组 | 用例 |
|--------|------|
| list_projects | 正常列出 企业/项目 + 有/无文档标注；目录不存在降级；空 query 列全部；企业名过滤 |
| get_doc 匹配 | 精确命中（`企业/项目`）；仅项目名唯一命中；多命中返回候选；零命中返回清单；大小写不敏感 |
| get_doc 内容 | 多 .md 按文件名排序拼接；>8000 字符时 output 摘要 + system 全文；项目无文档提示 |
| execute 分发 | CompanyDataLookup 的 4 个 action 路由正确，现有 list_tables/query 无回归 |

### 更新 `tests/tool/test_company_data_lookup.py`

- 补 execute 分发新 action 的用例（复用现有 fixture 风格）
- 现有用例不动（验证无回归）

### 明确排除

- 沙箱相关测试：文档在宿主机文件系统，工具本就在宿主机执行，无容器路径问题
- 示例文档本身：静态资产不单测，仅作手工冒烟对象

## 10. 影响范围（文件清单）

| 文件 | 变更 |
|------|------|
| `app/tool/project_docs.py` | **新增**：list_projects / get_doc 纯函数模块 |
| `project_docs/TEMPLATE.md` | **新增**：文档模板 |
| `project_docs/示例企业/示例项目/业务说明.md` | **新增**：填充好的示例文档 |
| `tests/tool/test_project_docs.py` | **新增**：核心测试 |
| `app/tool/company_data_lookup.py` | 修改：DOCS_DIR 常量、execute 分发、description/parameters |
| `app/prompt/quick_query.py` | 修改：使用流程插入文档步骤 |
| `app/prompt/visualization.py` | 修改：同上 |
| `tests/tool/test_company_data_lookup.py` | 修改：补分发用例 |
