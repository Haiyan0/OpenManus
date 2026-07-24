# MySQL 数据查询工具设计文档

> 状态：已审批 | 日期：2026-07-24 | 作者：baojingyu

## 1. 背景与目标

### 1.1 现状

`CompanyDataLookup` 工具通过遍历 `company_data_resource/` 目录树，子串匹配企业名称和项目名称，返回匹配的本地 CSV 文件列表供 Agent 分析。此方案存在以下局限：

- **无法实时增量更新**：数据依赖人工维护的 CSV 文件，新增数据需要手动放入目录
- **查询能力弱**：不支持灵活的过滤、聚合，只能按固定目录结构匹配
- **扩展性差**：数据量大后目录遍历变慢，无法利用数据库索引

### 1.2 目标

将 `CompanyDataLookup` 从本地文件匹配升级为 MySQL 实时查询，同时保留旧逻辑作为可切换的备份模式。

### 1.3 非目标

- 不涉及分析流程的变更（python_execute、可视化等后续链路保持不变）
- 不涉及数据库写入
- 不新建工具名称（保持 `company_data_lookup` 不变，零侵入替换）

---

## 2. 架构设计

### 2.1 工具接口

```
company_data_lookup
├── action="list_tables"   → 查询 information_schema → 返回格式化数据字典
└── action="query"         → 执行 SELECT SQL → 写 CSV 到 workspace → 返回摘要+预览
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `action` | `"list_tables"` \| `"query"` | 是 | 操作类型 |
| `query_or_sql` | string | 是 | `list_tables` 时传用户需求描述；`query` 时传 SELECT 语句 |

### 2.2 数据流

```
用户: "分析华南区Q3销售趋势"
  │
  ▼ Agent ReAct 循环
① company_data_lookup(action="list_tables", query_or_sql="华南区Q3销售趋势")
  │ MySQL: information_schema.TABLES + information_schema.COLUMNS
  ▼ 返回: 格式化的数据字典（表名+注释+字段名+类型+注释）
② Agent **反驳自省** → 逐一比对用户需求的数据维度与现有表字段的覆盖度
  │ ┌─ 覆盖充分 → 继续下一步
  │ ├─ 部分缺失 → 告知用户哪些维度缺失、能做/不能做什么 → 调用 ask_human 确认是否继续
  │ └─ 完全无法支撑 → 直接告知用户原因，调用 terminate 结束，不强行执行
  │
③ Agent 确认可继续后 → 编写 SQL
  │
④ company_data_lookup(action="query", query_or_sql="SELECT ... FROM sales_order WHERE region='华南' AND year(created_at)=2024 AND quarter(created_at)=3")
  │ 安全校验 → 执行 SQL → pandas 写 CSV → 返回摘要+预览
  ▼
⑤ python_execute(code="df = pd.read_csv('/workspace/_query_result_xxx.csv') ...")
  │ 后续分析流程完全不变
  ▼
⑥ 分析结果 + 可视化 → 返回用户
```

### 2.3 反驳自省阶段（关键）

`list_tables` 返回数据字典后，Agent **必须**进行反驳自省，不可跳过：

1. **需求拆解**：将用户的分析需求拆解为数据维度清单（时间维度、地域维度、指标维度、分类维度等）
2. **字段匹配**：逐一比对每个数据维度是否在现有表结构中能找到对应字段
3. **覆盖度判定**：

   | 覆盖度 | 处理方式 |
   |--------|---------|
   | **完全覆盖** | 继续编写 SQL，进入查询阶段 |
   | **部分缺失** | 明确告知用户"现有数据有 X 但没有 Y，因此我可以分析 A，但无法分析 B"。调用 `ask_human` 询问用户是否在当前约束下继续，或建议补充数据 |
   | **完全无法支撑** | 直接告知用户无法完成的原因（如"数据库中没有任何销售相关的表"），调用 `terminate` 结束，**绝不强行执行** |

4. **原则**：宁可拒绝也不乱做。数据不足时强行分析会产出误导性的结论，比不做更差。

### 2.4 安全层

`action="query"` 执行前强制校验：

1. **仅允许 SELECT**：SQL 去除前导空白后，必须不区分大小写地以 `SELECT` 或 `WITH`（CTE）开头。拒绝 INSERT/UPDATE/DELETE/ALTER/DROP/TRUNCATE 等任何写操作
2. **自动 LIMIT 注入**：若传入 SQL 中未出现 `LIMIT` 关键字，自动追加 `LIMIT 50000`
3. **执行超时**：单次查询超时 30 秒，超时则终止并返回错误
4. **黑名单关键字**：额外扫描 SQL 中是否包含危险关键字（DROP、TRUNCATE、ALTER、CREATE、INSERT、UPDATE、DELETE、GRANT、REVOKE），拒绝执行

### 2.4 数据库连接

直接复用 `config.toml` 中 `[web]` 段的 MySQL 配置：

```toml
[web]
mysql_host = "192.168.0.32"
mysql_port = 3306
mysql_user = "liudaichuang"
mysql_password = "123456"
mysql_database = "openmanus_web"
```

代码中通过 `config.web` 获取 `WebSettings`，从中提取 `mysql_host`、`mysql_port`、`mysql_user`、`mysql_password`、`mysql_database` 字段。

为实现独立连接池（避免和 FastAPI 的 `aiomysql` 连接池混用），在 `CompanyDataLookup` 内部维护一个**懒初始化的 pymysql 同步连接**（`execute()` 方法本身是 async，但 SQL 执行通过 `asyncio.to_thread()` 在线程池中运行，避免阻塞事件循环）。

**选择 pymysql 而非 aiomysql 的理由**：Tool 的 `execute()` 不在 FastAPI 请求生命周期内，不适用 `Depends(get_db)` 模式。pymysql 作为同步驱动更简单可靠，配合 `asyncio.to_thread()` 使用不影响事件循环性能。

### 2.5 模式切换

`config.toml` 的 `[web]` 段新增配置项：

```toml
# 数据查询模式: "local" = 本地 company_data_resource 目录, "mysql" = MySQL 实时查询
data_lookup_mode = "mysql"
```

`CompanyDataLookup.execute()` 实现：

```python
async def execute(self, action: str, query_or_sql: str) -> ToolResult:
    if config.web.data_lookup_mode == "local":
        return await self._execute_local(query_or_sql)      # 旧逻辑，完整保留
    else:
        return await self._execute_mysql(action, query_or_sql)  # 新逻辑
```

- 旧的 `_execute_local()` 原封不动保留
- 切换模式只需改一行配置，重启服务即生效
- `data_lookup_mode` 未配置时默认走 `"local"`（向后兼容）

---

## 3. 详细设计

### 3.1 数据字典查询（`action="list_tables"`）

**SQL**：

```sql
SELECT
    t.TABLE_NAME,
    t.TABLE_COMMENT,
    c.COLUMN_NAME,
    c.COLUMN_TYPE,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.IS_NULLABLE,
    c.COLUMN_DEFAULT,
    c.COLUMN_COMMENT,
    c.ORDINAL_POSITION
FROM information_schema.TABLES t
JOIN information_schema.COLUMNS c
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
    AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_SCHEMA = '{database}'
ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
```

**返回格式**（标准版）：

```
📊 数据库: openmanus_web | 共 5 张表

─────────────────────────────────────────────
📋 表: sales_order | 销售订单表
─────────────────────────────────────────────
  字段:
  - id (bigint) | 主键ID
  - order_no (varchar(50)) | 订单编号
  - customer_id (int) | 客户ID，关联 customer_info.id
  - region (varchar(20)) | 地区: 华北/华东/华南/西南
  - amount (decimal(12,2)) | 订单金额（元）
  - status (varchar(10)) | 状态: pending/confirmed/shipped/cancelled
  - created_at (datetime) | 创建时间

─────────────────────────────────────────────
📋 表: customer_info | 客户信息表
─────────────────────────────────────────────
  字段:
  - id (int) | 客户ID
  - name (varchar(100)) | 客户名称
  - contact (varchar(50)) | 联系人
  - phone (varchar(20)) | 联系电话
  - address (text) | 地址
  ...
```

要点：
- 按表分组，表内按 `ORDINAL_POSITION` 排序
- 表注释 `TABLE_COMMENT` 为重点，帮助 LLM 理解表用途
- 字段注释中的枚举值说明保留原文（如 `状态: pending/confirmed/shipped/cancelled`）
- 如果某个数据库下没有任何用户表，返回明确提示

### 3.2 SQL 执行（`action="query"`）

**安全校验**：

```python
def _validate_sql(self, sql: str) -> tuple[bool, str]:
    """校验 SQL 安全性。返回 (是否合法, 错误信息)。"""
    stripped = sql.strip()
    
    # 1. 必须以 SELECT 或 WITH (CTE) 开头
    upper = stripped.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return False, f"仅允许 SELECT 查询，不支持此语句类型"
    
    # 2. 黑名单关键字检测
    dangerous = {"DROP", "TRUNCATE", "ALTER", "CREATE", "INSERT", 
                 "UPDATE", "DELETE", "GRANT", "REVOKE", "REPLACE"}
    # 使用正则匹配独立单词，避免误匹配列名中的 "update_time"
    words = set(re.findall(r'\b([A-Z_]+)\b', upper))
    for kw in dangerous:
        if kw in words:
            return False, f"检测到危险关键字: {kw}，仅允许 SELECT 查询"
    
    # 3. 自动注入 LIMIT（若无）
    if "LIMIT" not in upper:
        sql = f"{stripped.rstrip(';')} LIMIT 50000"
    
    return True, sql
```

**执行逻辑**：

```python
async def _execute_query(self, sql: str) -> ToolResult:
    # 连接数据库 → 用 pandas.read_sql 读取 → 写 CSV → 返回摘要
    import pandas as pd
    
    conn = await self._get_connection()
    try:
        # pandas read_sql 在线程池中执行以不阻塞事件循环
        df = await asyncio.to_thread(
            pd.read_sql, sql, conn
        )
    finally:
        conn.close()
    
    # 写入 CSV 到 workspace
    csv_path = os.path.join(self._workspace_dir, 
                            f"_query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    # 构建预览
    preview = df.head(5).to_string(index=False)
    
    return ToolResult(
        output=(
            f"查询成功：返回 {len(df)} 行，{len(df.columns)} 列。\n"
            f"列名: {', '.join(df.columns.tolist())}\n"
            f"数据已保存至: {csv_path}\n\n"
            f"前5行预览:\n{preview}\n\n"
            f"请使用 python_execute (pandas.read_csv) 读取该文件继续分析。"
        )
    )
```

### 3.3 Workspace 目录

`_workspace_dir` 来源：
- **Sandbox 模式**：Agent 注入的 `workspace_dir`（容器内 `/workspace`），CSV 写入后立即可被 Sandbox 内的 `python_execute` 读取
- **本地模式**：`config.workspace_root`（宿主机路径），兼容命令行运行场景

`CompanyDataLookup` 需新增 `sandbox` 和 `workspace_dir` 属性，接受 `set_sandbox()` 的注入（与 `PythonExecute` 一致）。

### 3.4 错误处理

| 场景 | 处理方式 |
|------|---------|
| 数据库连接失败 | `ToolResult(error=...)` 返回具体错误信息 |
| `list_tables` 无表 | 返回 "数据库 xxx 中未找到任何用户表" |
| `query` SQL 语法错误 | 返回 MySQL 原始错误信息，LLM 据此修正 SQL |
| `query` 超时 30s | 终止查询，返回 "查询超时（30s），请优化 SQL 或缩小查询范围" |
| `query` 返回 0 行 | 正常返回，提示 "查询返回 0 行，请检查过滤条件" |
| 不安全 SQL 被拒绝 | 返回明确的安全策略提示 |

### 3.5 Agent 提示词变更

为将反驳自省阶段固化到 Agent 行为中，需更新 DataAnalysis 和 QuickQuery 的系统提示词。

**`app/prompt/visualization.py`（DataAnalysis）**：

将第 7-8 行的旧描述：
```
2. 公司数据目录: company_data_resource/；用户提到公司/企业/业务数据分析时，优先调用 company_data_lookup 工具检查是否有匹配的本地 CSV 数据
3. 如果 company_data_lookup 返回了匹配的数据文件，先告知用户找到了哪些文件，然后自动用 python_execute (pandas.read_csv) 加载并分析
```

替换为：
```
2. 数据库查询工具: company_data_lookup；用户提到公司/企业/业务数据分析时，优先使用此工具查询数据字典，确认数据是否存在

3. company_data_lookup 使用流程：
   a. 先调用 action="list_tables" 获取数据库全部表结构（表名、字段名、字段类型、注释）
   b. **反驳自省**（必须执行，不可跳过）：
      - 将用户的分析需求拆解为数据维度清单
      - 逐一比对清单中每个维度是否在现有表字段中有对应
      - 覆盖充分 → 继续编写 SQL
      - 部分缺失 → 调用 ask_human 告知用户"现有数据能分析 X，但缺少 Y 维度，无法分析 Z"，询问用户是否在当前约束下继续
      - 完全无法支撑 → 直接告知用户原因，调用 terminate 结束，**绝不强行分析**
   c. 确认可继续后，基于表结构编写精准的 SELECT SQL，调用 action="query" 执行
   d. 查询结果会保存为 CSV 文件到工作目录，用 python_execute (pandas.read_csv) 加载并分析
```

**`app/prompt/quick_query.py`（QuickQuery）**：

将第 22-24 行的旧描述：
```
2. 公司数据目录: company_data_resource/；用户提到公司/企业/业务数据分析时，
   优先调用 company_data_lookup 工具检查是否有匹配的本地 CSV 数据
3. 如果 company_data_lookup 返回了匹配的数据文件，先告知用户找到了哪些文件，
   然后自动用 python_execute (pandas.read_csv) 加载并分析
```

替换为：
```
2. 数据库查询工具: company_data_lookup；用户提到公司/企业/业务数据查询时，优先使用此工具
3. company_data_lookup 使用流程：
   a. 先调用 action="list_tables" 获取数据库全部表结构
   b. **反驳自省**（必须执行）：
      - 逐一比对用户需要的数据维度与现有表字段
      - 数据不足时调用 ask_human 告知用户，不要强行查询
      - 完全无法支撑时直接 terminate
   c. 确认可继续后编写 SELECT SQL，调用 action="query" 执行
   d. 查询结果 CSV 用 python_execute 读取并计算
```

---

## 4. 文件变更清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `app/tool/company_data_lookup.py` | 重写 | `execute()` 拆分为 local/mysql 两模式；新增 `_execute_mysql()`、`_list_tables()`、`_execute_query()`、`_validate_sql()`；新增 `sandbox` / `workspace_dir` 属性 |
| `app/config.py` | 修改 | `WebSettings` 新增 `data_lookup_mode: str = "local"` 字段 |
| `config/config.toml` | 修改 | `[web]` 段新增 `data_lookup_mode = "mysql"` |
| `config/config.example.toml` | 修改 | `[web]` 段新增 `data_lookup_mode` 注释说明 |
| `app/prompt/visualization.py` | 修改 | DataAnalysis 系统提示词替换公司数据段落，加入反驳自省流程 |
| `app/prompt/quick_query.py` | 修改 | QuickQuery 系统提示词替换公司数据段落，加入反驳自省流程 |
| `requirements.txt` | 审查 | 确认 `pymysql` 已在依赖中（或新增） |

**不需要改的文件**：
- `app/agent/data_analysis.py` — 工具注册不变
- `app/agent/quick_query.py` — 工具注册不变
- `app/agent/manus.py` — 通用 Agent 不涉及
- `app/web/*` — Web 层无变更

---

## 5. 测试策略

### 5.1 单元测试

| 测试项 | 说明 |
|--------|------|
| `_validate_sql` 通过合法 SELECT | 普通 SELECT、WITH CTE、子查询均通过 |
| `_validate_sql` 拒绝非 SELECT | INSERT、UPDATE、DELETE 等被拒绝 |
| `_validate_sql` 检测危险关键字 | 独立单词匹配，不误伤列名（如 `update_time`） |
| `_validate_sql` 自动注入 LIMIT | 无 LIMIT 的 SQL 自动追加 `LIMIT 50000` |
| `_validate_sql` 已有 LIMIT 不重复 | 自带 `LIMIT 100` 的 SQL 保持不变 |

### 5.2 集成测试

| 测试项 | 说明 |
|--------|------|
| `list_tables` 获取真实数据字典 | 连接测试库，验证返回格式 |
| `query` 执行并生成 CSV | 执行 SELECT，验证 CSV 文件存在且内容正确 |
| `query` 执行超时 | 构造慢查询，验证 30s 超时生效 |
| `local` 模式向后兼容 | `data_lookup_mode="local"` 时旧逻辑正常运作 |
| 连接失败友好报错 | 错误连接配置时返回可读的错误信息 |

### 5.3 手工验证

1. 启动服务，确认 `data_lookup_mode = "mysql"`
2. 在 Web 聊天界面选择 DataAnalysis Agent
3. 发送："帮我查一下华南区的销售数据，做一个趋势分析"
4. 观察 Agent 是否正确完成：list_tables → 写 SQL → query → python_execute 分析

---

## 6. 兼容性

- **Agent 层零侵入**：DataAnalysis 和 QuickQuery 的 `available_tools` 代码一行不改
- **`local` 模式完整保留**：旧目录遍历逻辑封装在 `_execute_local()` 中，代码不动
- **默认 `"local"` 模式**：`data_lookup_mode` 未配置时默认走旧逻辑，现有部署不受影响
- **工具参数变更**：旧参数 `query` 改为 `query_or_sql`，但语义兼容——`_execute_local` 只用到 `query_or_sql` 传入的原始需求文本

---

## 7. 未决与风险

- **多库切换**：当前复用 `[web]` 段的 MySQL 配置，后续换库需要改 config.toml。如果未来有独立数据源的需求，可在 `[web]` 段新增 `data_mysql_*` 一组独立配置
- **大表查询**：LIMIT 50000 和 30s 超时是硬上限，极端场景下可能需要调优。这些值用类常量定义，方便后续改为配置项
- **pymysql vs aiomysql**：pymysql 同步驱动 + `asyncio.to_thread()` 是最简单的方案。如果后续发现阻塞问题，可升级为 aiomysql
