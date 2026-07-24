# MySQL 数据查询工具 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 CompanyDataLookup 从本地 CSV 文件匹配升级为 MySQL 实时查询，同时保留旧逻辑作为可切换的备份模式

**Architecture:** pymysql + asyncio.to_thread() 同步驱动方案，工具 execute() 按 config.web.data_lookup_mode 分发到 _execute_local（旧）或 _execute_mysql（新）。_execute_mysql 走 action="list_tables" 拉数据字典 → LLM 反驳自省 → action="query" 写 CSV 到 workspace → Agent 后续分析流程不变

**Tech Stack:** Python 3.12, pymysql, pandas, asyncio, re (stdlib)

## Global Constraints

- `data_lookup_mode` 默认值为 `"local"`（向后兼容，未配置时走旧逻辑）
- `action` 固定为 `"list_tables"` | `"query"` 两个枚举值
- SQL 只允许 SELECT/WITH（CTE），硬过滤非读操作
- _execute_local() 原封不动保留
- Agent 代码一行不改（DataAnalysis/QuickQuery 的 available_tools 不动）
- 数据库 username/password/database 等从 config.web 读取

---

## 文件结构

```
app/tool/company_data_lookup.py    ← 重写：新增 _execute_mysql/_list_tables/_execute_query/_validate_sql
                                       新增 sandbox/workspace_dir 属性
app/config.py                      ← 修改：WebSettings 新增 data_lookup_mode 字段
config/config.toml                 ← 修改：[web] 段新增 data_lookup_mode = "mysql"
config/config.example.toml         ← 修改：[web] 段新增 data_lookup_mode 注释
app/prompt/visualization.py        ← 修改：DataAnalysis 提示词公司数据段落替换
app/prompt/quick_query.py          ← 修改：QuickQuery 提示词公司数据段落替换
```

---

### Task 1: 配置层 — WebSettings + config.toml

**Files:**
- Modify: `app/config.py:108-136`
- Modify: `config/config.toml:118-131`
- Modify: `config/config.example.toml:115-124`

**Interfaces:**
- Produces: `config.web.data_lookup_mode: str` 供 Task 2 的 `CompanyDataLookup.execute()` 读取

- [ ] **Step 1: WebSettings 新增 data_lookup_mode 字段**

编辑 `app/config.py`，在 `WebSettings` 类中 `jwt_expire_hours` 之后插入：

```python
    data_lookup_mode: str = Field(
        default="local",
        description='数据查询模式: "local"=本地CSV目录, "mysql"=MySQL实时查询',
    )
```

确保插入位置在 `jwt_expire_hours` 行之后、`sandbox_data_root` 行之前。

- [ ] **Step 2: 运行 Python 验证配置类加载正常**

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "from app.config import config; print('data_lookup_mode:', config.web.data_lookup_mode); print('mysql_host:', config.web.mysql_host)"
```

期望输出：
```
data_lookup_mode: local   (如果 config.toml 还未加，用默认值)
mysql_host: 192.168.0.32
```

- [ ] **Step 3: config.toml 添加配置项**

编辑 `config/config.toml`，在 `[web]` 段 `mysql_database` 行之后插入：

```toml
# 数据查询模式: "local" = 本地 company_data_resource 目录, "mysql" = MySQL 实时查询
data_lookup_mode = "mysql"
```

- [ ] **Step 4: config.example.toml 添加配置项**

编辑 `config/config.example.toml`，在 `[web]` 段 `mysql_database` 行之后插入：

```toml
# 数据查询模式: "local" = 本地 company_data_resource 目录, "mysql" = MySQL 实时查询
data_lookup_mode = "local"
```

- [ ] **Step 5: 再次验证配置加载**

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "from app.config import config; print('data_lookup_mode:', config.web.data_lookup_mode)"
```

期望：`data_lookup_mode: mysql`

- [ ] **Step 6: Commit**

```bash
git add app/config.py config/config.toml config/config.example.toml
git commit -m "feat: WebSettings 新增 data_lookup_mode 配置项"
```

---

### Task 2: 核心工具重写 — company_data_lookup.py

**Files:**
- Modify: `app/tool/company_data_lookup.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `config.web.data_lookup_mode` (Task 1), `config.web.mysql_host/port/user/password/database`
- Produces: `CompanyDataLookup.execute(action, query_or_sql)` — async method, returns ToolResult
- Produces: `CompanyDataLookup.sandbox: object | None`, `CompanyDataLookup.workspace_dir: str` — 供 set_sandbox() 注入
- Produces: `CompanyDataLookup._validate_sql(sql)` — 静态安全校验
- Produces: `CompanyDataLookup._list_tables()` — 数据字典查询
- Produces: `CompanyDataLookup._execute_query(sql)` — SQL 执行 + CSV 写入

- [ ] **Step 1: 写出完整的新文件内容**

用以下完整代码 **替换** `app/tool/company_data_lookup.py` 的全部内容：

```python
"""
公司数据资源查找工具。

支持两种模式（通过 config.toml [web] data_lookup_mode 切换）：
- "local"：遍历 company_data_resource/ 目录树，子串匹配返回本地 CSV 文件列表
- "mysql"：连接 MySQL，拉取数据字典 + 执行 SELECT 查询，结果写入 workspace CSV
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import PROJECT_ROOT, config
from app.logger import logger
from app.tool.base import BaseTool, ToolResult


# ── 安全配置常量 ──────────────────────────────────────────────

# 黑名单关键字：出现任何一个即拒绝执行
_DANGEROUS_SQL_KEYWORDS = {
    "DROP", "TRUNCATE", "ALTER", "CREATE", "INSERT",
    "UPDATE", "DELETE", "GRANT", "REVOKE", "REPLACE",
}

# 单次查询最大返回行数（SQL 无 LIMIT 时自动注入）
_DEFAULT_QUERY_LIMIT = 50000

# 单次查询超时秒数
_QUERY_TIMEOUT_SECONDS = 30


class CompanyDataLookup(BaseTool):
    """查找与用户查询匹配的公司数据。

    支持两种模式：
    - local: 在 company_data_resource/ 目录树中匹配本地 CSV
    - mysql: 连接 MySQL，list_tables 拉数据字典，query 执行 SELECT 并写 CSV
    """

    name: str = "company_data_lookup"
    description: str = (
        "公司数据查询工具。有两个 action：\n"
        "1. action='list_tables' — 获取数据库中所有表的表名、字段名、字段类型、注释，"
        "用于理解哪些数据维度可用。参数 query_or_sql 传入用户的数据分析需求描述。\n"
        "2. action='query' — 在确认表结构能支撑用户需求后，传入 SELECT SQL 执行查询，"
        "结果保存为 CSV 文件到工作目录。参数 query_or_sql 传入完整的 SELECT 语句。\n"
        "使用流程：先 list_tables 了解数据结构 → 确认数据能否支撑用户需求 "
        "→ 再 query 执行查询 → 用 python_execute 读取 CSV 继续分析。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_tables", "query"],
                "description": (
                    "操作类型: 'list_tables' 获取数据库全部表结构（表名+字段+注释），"
                    "'query' 执行 SELECT 语句并将结果保存为 CSV"
                ),
            },
            "query_or_sql": {
                "type": "string",
                "description": (
                    "当 action='list_tables' 时，传入用户的数据分析需求描述"
                    "（用于帮助理解上下文）；"
                    "当 action='query' 时，传入完整的 SELECT SQL 语句"
                ),
            },
        },
        "required": ["action", "query_or_sql"],
    }

    # ── Sandbox 注入属性 ────────────────────────────────────
    # 由 Agent.set_sandbox() 遍历 available_tools 自动注入
    sandbox: Optional[object] = None
    workspace_dir: str = ""

    # 公司数据资源目录（local 模式使用，相对于项目根目录）
    DATA_DIR: str = "company_data_resource"

    def __init__(self, **data):
        super().__init__(**data)

    # =================================================================
    #  公开入口
    # =================================================================

    async def execute(self, action: str, query_or_sql: str) -> ToolResult:
        """执行数据查询操作。

        根据 config.web.data_lookup_mode 分发到 local 或 mysql 模式。

        Args:
            action: "list_tables" 或 "query"
            query_or_sql: 用户需求描述（list_tables）或 SELECT 语句（query）

        Returns:
            ToolResult: 成功时 output 包含数据，失败时 error 包含原因
        """
        mode = getattr(config.web, "data_lookup_mode", "local")

        if mode == "local":
            return await self._execute_local(query_or_sql)
        else:
            return await self._execute_mysql(action, query_or_sql)

    # =================================================================
    #  Local 模式（旧逻辑，完整保留）
    # =================================================================

    async def _execute_local(self, query: str) -> ToolResult:
        """在 company_data_resource 中查找匹配的公司数据文件。

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

        if not data_root.exists() or not data_root.is_dir():
            logger.warning(f"公司数据目录不存在: {data_root}")
            return self.fail_response(
                f"公司数据目录 '{self.DATA_DIR}' 不存在或不可访问。"
                f"请使用常规数据分析流程，直接通过用户提供的文件路径读取数据。"
            )

        query_lower = query.lower()

        try:
            companies = [d for d in sorted(data_root.iterdir()) if d.is_dir()]
            if not companies:
                logger.warning(f"公司数据目录为空: {data_root}")
                return self.fail_response(
                    f"公司数据目录 '{self.DATA_DIR}' 下没有企业数据。"
                    f"请使用常规数据分析流程。"
                )

            company_no_project_matches = []
            for company_dir in companies:
                company_name = company_dir.name

                if company_name.lower() not in query_lower:
                    continue

                logger.info(f"命中企业: {company_name}")

                projects = [
                    d for d in sorted(company_dir.iterdir()) if d.is_dir()
                ]
                for project_dir in projects:
                    project_name = project_dir.name

                    if project_name.lower() not in query_lower:
                        continue

                    logger.info(f"命中项目: {company_name}/{project_name}")

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
                        f"请使用 python_execute（pandas.read_csv）读取上述文件进行数据分析，"
                        f"并在分析前告知用户已找到以下本地数据文件："
                        f"{', '.join(f['name'] for f in csv_files)}"
                    )

                    return ToolResult(
                        output=output_message,
                        system=(
                            f"已匹配本地公司数据：企业={company_name}，"
                            f"项目={project_name}，文件数={len(csv_files)}。"
                            f"告知用户后自动读取 CSV 进行分析。"
                        ),
                    )

                available_projects = [d.name for d in projects]
                company_no_project_matches.append(
                    f"  - {company_name}（可用项目：{', '.join(available_projects)}）"
                )
                continue

            if company_no_project_matches:
                return self.fail_response(
                    f"以下企业名称匹配但未找到匹配的项目：\n"
                    f"{chr(10).join(company_no_project_matches)}\n"
                    f"请确认用户需要分析哪个项目的数据，或提示用户补充项目名称。"
                )

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

    # =================================================================
    #  MySQL 模式
    # =================================================================

    async def _execute_mysql(self, action: str, query_or_sql: str) -> ToolResult:
        """MySQL 模式的入口，按 action 分发。

        Args:
            action: "list_tables" 或 "query"
            query_or_sql: 用户需求描述或 SELECT 语句
        """
        if action == "list_tables":
            return await asyncio.to_thread(self._list_tables)
        elif action == "query":
            return await self._execute_query(query_or_sql)
        else:
            return self.fail_response(
                f"不支持的 action: '{action}'，可选值为 'list_tables' 或 'query'"
            )

    # ── 数据库连接 ──────────────────────────────────────────

    def _get_connection(self):
        """创建一个 pymysql 同步连接。

        使用 config.web 中的 MySQL 配置。
        调用方负责在 asyncio.to_thread() 中调用，并在使用后关闭连接。

        Returns:
            pymysql.Connection

        Raises:
            ImportError: pymysql 未安装
            Exception: 连接失败
        """
        try:
            import pymysql
        except ImportError:
            raise ImportError(
                "pymysql 未安装，请执行: pip install pymysql"
            )

        try:
            conn = pymysql.connect(
                host=config.web.mysql_host,
                port=config.web.mysql_port,
                user=config.web.mysql_user,
                password=config.web.mysql_password,
                database=config.web.mysql_database,
                charset="utf8mb4",
                connect_timeout=10,
                read_timeout=_QUERY_TIMEOUT_SECONDS,
                cursorclass=pymysql.cursors.DictCursor,
            )
            return conn
        except Exception as e:
            raise ConnectionError(
                f"无法连接到 MySQL 数据库 "
                f"({config.web.mysql_host}:{config.web.mysql_port}/"
                f"{config.web.mysql_database}): {e}"
            ) from e

    # ── 数据字典查询 ────────────────────────────────────────

    def _list_tables(self) -> ToolResult:
        """从 MySQL information_schema 查询所有表结构，格式化返回。

        在线程池中同步执行（由 _execute_mysql 的 asyncio.to_thread 包裹）。

        Returns:
            ToolResult: 成功时 output 为格式化的数据字典
        """
        sql = (
            "SELECT "
            "  t.TABLE_NAME, "
            "  t.TABLE_COMMENT, "
            "  c.COLUMN_NAME, "
            "  c.COLUMN_TYPE, "
            "  c.DATA_TYPE, "
            "  c.CHARACTER_MAXIMUM_LENGTH, "
            "  c.NUMERIC_PRECISION, "
            "  c.NUMERIC_SCALE, "
            "  c.IS_NULLABLE, "
            "  c.COLUMN_DEFAULT, "
            "  c.COLUMN_COMMENT, "
            "  c.ORDINAL_POSITION "
            "FROM information_schema.TABLES t "
            "JOIN information_schema.COLUMNS c "
            "  ON t.TABLE_SCHEMA = c.TABLE_SCHEMA "
            " AND t.TABLE_NAME = c.TABLE_NAME "
            "WHERE t.TABLE_SCHEMA = %s "
            "  AND t.TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION"
        )

        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (config.web.mysql_database,))
                rows = cursor.fetchall()

            if not rows:
                return self.fail_response(
                    f"数据库 '{config.web.mysql_database}' 中未找到任何用户表。"
                    f"请确认数据库中已创建业务数据表。"
                )

            # 按表分组
            from collections import OrderedDict
            tables: dict[str, dict] = OrderedDict()
            for row in rows:
                tname = row["TABLE_NAME"]
                if tname not in tables:
                    tables[tname] = {
                        "comment": row["TABLE_COMMENT"] or "",
                        "columns": [],
                    }
                tables[tname]["columns"].append(row)

            # 格式化输出
            lines = [
                f"📊 数据库: {config.web.mysql_database}"
                f" | 共 {len(tables)} 张业务表",
                "",
            ]

            for tname, tinfo in tables.items():
                tcomment = tinfo["comment"]
                comment_str = f" | {tcomment}" if tcomment else ""
                lines.append("─" * 60)
                lines.append(f"📋 表: {tname}{comment_str}")
                lines.append("─" * 60)
                lines.append("  字段:")
                for col in tinfo["columns"]:
                    cname = col["COLUMN_NAME"]
                    ctype = col["COLUMN_TYPE"]
                    ccomment = col["COLUMN_COMMENT"] or ""
                    nullable = "NULL" if col["IS_NULLABLE"] == "YES" else "NOT NULL"
                    default = col["COLUMN_DEFAULT"]
                    extras = []
                    if default is not None:
                        extras.append(f"默认={default}")
                    extras.append(nullable)
                    extra_str = f" [{', '.join(extras)}]" if extras else ""
                    comment_str = f" | {ccomment}" if ccomment else ""
                    lines.append(f"  - {cname} ({ctype}){extra_str}{comment_str}")
                lines.append("")

            output = "\n".join(lines)
            logger.info(f"数据字典查询成功: {len(tables)} 张表")
            return ToolResult(output=output)

        except ImportError as e:
            logger.error(f"pymysql 未安装: {e}")
            return self.fail_response(
                f"MySQL 驱动未安装: {e}\n"
                f"请执行 pip install pymysql 后重试，"
                f"或切换为 local 模式: 修改 config.toml [web] data_lookup_mode = 'local'"
            )
        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self.fail_response(str(e))
        except Exception as e:
            logger.error(f"数据字典查询失败: {e}", exc_info=True)
            return self.fail_response(
                f"查询数据字典时发生错误: {e}\n"
                f"请检查数据库连接和权限。"
            )
        finally:
            if conn:
                conn.close()

    # ── SQL 查询执行 ────────────────────────────────────────

    def _execute_query(self, sql: str) -> ToolResult:
        """执行 SELECT 查询，结果写入 workspace CSV 文件。

        在线程池中同步执行（由 _execute_mysql 的 asyncio.to_thread 包裹）。

        流程：
        1. 安全校验 SQL
        2. 连接数据库执行查询
        3. pandas 读取结果 → 写 CSV 到 workspace
        4. 返回行数/列名/预览

        Args:
            sql: 要执行的 SELECT 语句

        Returns:
            ToolResult: 成功时 output 包含摘要和 CSV 路径
        """
        # ── 1. 安全校验 ──────────────────────────────────
        is_valid, result = self._validate_sql(sql)
        if not is_valid:
            return self.fail_response(
                f"SQL 安全校验未通过: {result}\n"
                f"仅允许执行 SELECT 查询，请修改 SQL 语句后重试。"
            )
        safe_sql = result  # result 可能是修改后的 SQL（追加了 LIMIT）

        # ── 2. 解析 workspace 路径 ────────────────────────
        ws = self.workspace_dir if self.workspace_dir else str(config.workspace_root)

        # ── 3. 执行查询 ──────────────────────────────────
        conn = None
        try:
            import pandas as pd

            conn = self._get_connection()
            df = pd.read_sql(safe_sql, conn)
        except ImportError:
            return self.fail_response(
                "查询执行需要 pandas 库，但未安装。请执行 pip install pandas 后重试。"
            )
        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self.fail_response(str(e))
        except Exception as e:
            logger.error(f"SQL 执行失败: {e}")
            return self.fail_response(
                f"SQL 执行失败: {e}\n"
                f"SQL 语句:\n{safe_sql}\n\n"
                f"请修正 SQL 后重试。"
            )
        finally:
            if conn:
                conn.close()

        # ── 4. 写 CSV ────────────────────────────────────
        if df.empty:
            return self.fail_response(
                f"查询返回 0 行。SQL 语句:\n{safe_sql}\n"
                f"请检查过滤条件是否正确，或调用 list_tables 确认表中是否有数据。"
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"_query_result_{timestamp}.csv"
        csv_path = os.path.join(ws, csv_filename)

        try:
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.error(f"CSV 写入失败: {e}")
            return self.fail_response(f"查询结果写入 CSV 失败: {e}")

        # ── 5. 构建输出 ──────────────────────────────────
        col_names = df.columns.tolist()
        try:
            preview = df.head(5).to_string(index=False)
        except Exception:
            preview = "(预览生成失败)"

        logger.info(
            f"SQL 查询成功: {len(df)} 行 {len(col_names)} 列 → {csv_path}"
        )

        return ToolResult(
            output=(
                f"查询成功：返回 {len(df):,} 行，{len(col_names)} 列。\n"
                f"列名: {', '.join(col_names)}\n"
                f"数据已保存至: {csv_path}\n\n"
                f"前5行预览:\n{preview}\n\n"
                f"请使用 python_execute (pandas.read_csv('{csv_path}')) 读取该文件继续分析。"
            ),
        )

    # ═══════════════════════════════════════════════════════════
    #  安全校验
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _validate_sql(sql: str) -> tuple[bool, str]:
        """校验 SQL 安全性，并在必要时自动注入 LIMIT。

        三道防线：
        1. 必须以 SELECT 或 WITH (CTE) 开头
        2. 不包含黑名单危险关键字（独立单词匹配，不误伤列名）
        3. 无 LIMIT 时自动追加 LIMIT {_DEFAULT_QUERY_LIMIT}

        Args:
            sql: 原始 SQL 字符串

        Returns:
            (是否合法, 处理后的SQL或错误信息)
            - (True, safe_sql): 校验通过，safe_sql 可能已追加 LIMIT
            - (False, error_message): 校验失败，error_message 说明原因
        """
        stripped = sql.strip()
        if not stripped:
            return False, "SQL 语句为空"

        upper = stripped.upper()

        # ── 防线 1: 语句类型白名单 ──────────────────────
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            return (
                False,
                f"仅允许 SELECT 查询，当前语句以 '{stripped[:20].upper()}...' 开头。",
            )

        # ── 防线 2: 危险关键字黑名单 ─────────────────────
        # 使用 \b 边界匹配，避免误伤列名（如 update_time 中的 UPDATE）
        words_in_sql = set(re.findall(r"\b([A-Z_]+)\b", upper))
        for kw in _DANGEROUS_SQL_KEYWORDS:
            if kw in words_in_sql:
                return (
                    False,
                    f"SQL 中包含危险关键字 '{kw}'，仅允许 SELECT（只读）查询。"
                    f"请移除该关键字后重试。",
                )

        # ── 防线 3: 自动注入 LIMIT ──────────────────────
        if "LIMIT" not in upper:
            # 去除末尾分号后追加 LIMIT
            clean = stripped.rstrip(";")
            safe_sql = f"{clean} LIMIT {_DEFAULT_QUERY_LIMIT}"
            logger.info(f"SQL 自动追加 LIMIT {_DEFAULT_QUERY_LIMIT}")
            return True, safe_sql

        return True, stripped
```

- [ ] **Step 2: 确认 pymysql 在 requirements.txt 中**

`requirements.txt` 中尚无 `pymysql`，需新增一行：

```
pymysql~=1.1.2
```

插入到 `aiomysql~=0.2.0` 行之后（与其他数据库驱动相邻）。

也可以先安装验证：

```powershell
pip show pymysql 2>&1 || pip install pymysql
```

- [ ] **Step 3: 验证语法和导入**

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "from app.tool.company_data_lookup import CompanyDataLookup; print('import OK'); print('name:', CompanyDataLookup.name); print('params keys:', list(CompanyDataLookup.parameters['properties'].keys()))"
```

期望输出：
```
import OK
name: company_data_lookup
params keys: ['action', 'query_or_sql']
```

- [ ] **Step 3: 单元测试 — _validate_sql 合法 SELECT**

创建 `tests/tool/test_company_data_lookup.py`：

```python
"""CompanyDataLookup 安全校验单元测试。"""
import pytest
from app.tool.company_data_lookup import CompanyDataLookup


class TestValidateSql:
    """_validate_sql 安全校验测试。"""

    def test_simple_select_passes(self):
        ok, result = CompanyDataLookup._validate_sql(
            "SELECT * FROM users"
        )
        assert ok is True
        assert "LIMIT 50000" in result

    def test_select_with_where_passes(self):
        ok, result = CompanyDataLookup._validate_sql(
            "SELECT id, name FROM orders WHERE status = 'pending'"
        )
        assert ok is True
        assert "LIMIT 50000" in result

    def test_cte_with_passes(self):
        ok, result = CompanyDataLookup._validate_sql(
            "WITH regional_sales AS (SELECT region, SUM(amount) AS total FROM sales GROUP BY region) SELECT * FROM regional_sales"
        )
        assert ok is True
        # WITH 开头的 CTE 也应该通过
        assert "LIMIT 50000" in result

    def test_already_has_limit_preserved(self):
        ok, result = CompanyDataLookup._validate_sql(
            "SELECT * FROM orders LIMIT 100"
        )
        assert ok is True
        assert result == "SELECT * FROM orders LIMIT 100"
        # 不应追加第二个 LIMIT
        assert result.count("LIMIT") == 1

    def test_insert_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql(
            "INSERT INTO users (name) VALUES ('test')"
        )
        assert ok is False
        assert "SELECT" in msg or "仅允许" in msg

    def test_update_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql(
            "UPDATE orders SET status = 'done'"
        )
        assert ok is False
        assert "UPDATE" in msg or "危险关键字" in msg

    def test_delete_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql(
            "DELETE FROM orders WHERE id = 1"
        )
        assert ok is False
        assert "DELETE" in msg or "危险关键字" in msg

    def test_drop_table_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql(
            "DROP TABLE users"
        )
        assert ok is False
        assert "DROP" in msg or "危险关键字" in msg

    def test_alter_table_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql(
            "ALTER TABLE users ADD COLUMN age INT"
        )
        assert ok is False
        assert "ALTER" in msg or "危险关键字" in msg

    def test_column_name_containing_update_not_falsely_flagged(self):
        """列名 update_time 不应触发 UPDATE 黑名单误报。"""
        ok, result = CompanyDataLookup._validate_sql(
            "SELECT id, update_time FROM users"
        )
        assert ok is True
        assert "LIMIT 50000" in result

    def test_column_name_containing_delete_not_falsely_flagged(self):
        """列名 is_deleted 不应触发 DELETE 黑名单误报。"""
        ok, result = CompanyDataLookup._validate_sql(
            "SELECT id, is_deleted FROM users WHERE is_deleted = 0"
        )
        assert ok is True
        assert "LIMIT 50000" in result

    def test_empty_sql_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql("   ")
        assert ok is False

    def test_select_with_semicolon_stripped(self):
        ok, result = CompanyDataLookup._validate_sql(
            "SELECT * FROM users;"
        )
        assert ok is True
        # 分号被去除，然后追加 LIMIT
        assert "LIMIT 50000" in result
        assert ";" not in result

    def test_keyword_in_string_not_falsely_flagged(self):
        """引号内的 DROP 字符串不应触发黑名单。
        
        注意：当前实现基于单词边界匹配，引号内的内容也会被匹配。
        这是一个已知的保守策略——宁可误杀也不放过。
        如果 SQL 中需要包含这些关键字的字符串字面量，
        应由 LLM 改写 SQL 来避免。
        """
        ok, msg = CompanyDataLookup._validate_sql(
            "SELECT * FROM logs WHERE action = 'DROP'"
        )
        # 当前实现会匹配到引号内的 DROP 关键字，返回 False
        # 这是预期行为（保守策略）
        assert ok is False
```

- [ ] **Step 4: 运行测试**

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/tool/test_company_data_lookup.py -v
```

期望：全部 PASS

- [ ] **Step 5: 本地模式向后兼容验证**

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
import asyncio
from app.tool.company_data_lookup import CompanyDataLookup

async def test():
    tool = CompanyDataLookup()
    # 强制 local 模式（不依赖 config）
    old_execute = tool._execute_local
    result = await old_execute('不存在的公司名')
    print('local 模式正常返回:', 'error' in str(result))

asyncio.run(test())
"
```

期望：`local 模式正常返回: True`（因为查不到匹配公司，走 fail_response，说明旧逻辑完整运行）

- [ ] **Step 6: Commit**

```bash
git add app/tool/company_data_lookup.py tests/tool/test_company_data_lookup.py
git commit -m "feat: CompanyDataLookup 升级为 MySQL/local 双模式数据查询工具"
```

---

### Task 3: Agent 提示词更新

**Files:**
- Modify: `app/prompt/visualization.py` (lines 7-8)
- Modify: `app/prompt/quick_query.py` (lines 22-25)

**Interfaces:**
- Consumes: 无（独立变更）
- Produces: DataAnalysis 和 QuickQuery 的 system_prompt 中包含新的反驳自省流程

- [ ] **Step 1: 更新 visualization.py 公司数据段落**

编辑 `app/prompt/visualization.py`，将第 7-8 行：

```python
2. 公司数据目录: company_data_resource/；用户提到公司/企业/业务数据分析时，优先调用 company_data_lookup 工具检查是否有匹配的本地 CSV 数据
3. 如果 company_data_lookup 返回了匹配的数据文件，先告知用户找到了哪些文件，然后自动用 python_execute (pandas.read_csv) 加载并分析
```

替换为：

```python
2. 数据库查询工具: company_data_lookup；用户提到公司/企业/业务数据分析时，优先使用此工具查询数据
3. company_data_lookup 使用流程：
   a. 先调用 action="list_tables" 获取数据库全部表结构（表名、字段名、字段类型、注释）
   b. **反驳自省**（必须执行，不可跳过）：
      - 将用户的分析需求拆解为数据维度清单（时间、地域、指标、分类等）
      - 逐一比对每个维度是否在现有表字段中有对应
      - 覆盖充分 → 继续编写 SQL
      - 部分缺失 → 调用 ask_human 告知用户"现有数据能分析 X，但缺少 Y 维度，无法分析 Z"，询问是否在当前约束下继续
      - 完全无法支撑 → 直接告知用户原因，调用 terminate 结束，**绝不强行分析**
   c. 确认可继续后，基于表结构编写精准的 SELECT SQL，调用 action="query" 执行
   d. 查询结果 CSV 用 python_execute (pandas.read_csv) 加载并分析
```

- [ ] **Step 2: 更新 quick_query.py 公司数据段落**

编辑 `app/prompt/quick_query.py`，将第 22-25 行：

```python
2. 公司数据目录: company_data_resource/；用户提到公司/企业/业务数据分析时，
   优先调用 company_data_lookup 工具检查是否有匹配的本地 CSV 数据
3. 如果 company_data_lookup 返回了匹配的数据文件，先告知用户找到了哪些文件，
   然后自动用 python_execute (pandas.read_csv) 加载并分析
```

替换为：

```python
2. 数据库查询工具: company_data_lookup；用户提到公司/企业/业务数据查询时，优先使用此工具
3. company_data_lookup 使用流程：
   a. 先调用 action="list_tables" 获取数据库全部表结构（表名、字段名、字段类型、注释）
   b. **反驳自省**（必须执行，不可跳过）：
      - 逐一比对用户需要的数据维度与现有表字段的覆盖情况
      - 部分缺失时调用 ask_human 告知用户，确认后再继续
      - 完全无法支撑时直接 terminate，不要强行查询
   c. 确认可继续后编写 SELECT SQL，调用 action="query" 执行
   d. 查询结果 CSV 用 python_execute 读取并计算
```

- [ ] **Step 3: 验证提示词加载正常**

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
from app.prompt.visualization import SYSTEM_PROMPT as vp
from app.prompt.quick_query import SYSTEM_PROMPT as qp
print('visualization 包含反驳自省:', '反驳自省' in vp)
print('quick_query 包含反驳自省:', '反驳自省' in qp)
print('visualization 包含 company_data_lookup:', 'company_data_lookup' in vp)
print('quick_query 包含 company_data_lookup:', 'company_data_lookup' in qp)
"
```

期望：全部 `True`

- [ ] **Step 4: Commit**

```bash
git add app/prompt/visualization.py app/prompt/quick_query.py
git commit -m "feat: Agent 提示词加入 MySQL 查询流程与反驳自省阶段"
```

---

### Task 4: 集成验证

**Files:**
- 无需修改文件（验证用）

**Interfaces:**
- Consumes: Task 1 (config), Task 2 (tool), Task 3 (prompts)

- [ ] **Step 1: 启动服务验证配置加载**

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -c "
from app.config import config
# 验证所有配置项就绪
print('data_lookup_mode:', config.web.data_lookup_mode)
print('mysql_host:', config.web.mysql_host)
print('mysql_database:', config.web.mysql_database)
# 验证工具导入
from app.tool.company_data_lookup import CompanyDataLookup
tool = CompanyDataLookup()
print('Tool name:', tool.name)
print('Action param enum:', tool.parameters['properties']['action']['enum'])
# 验证 DataAnalysis 导入
from app.agent.data_analysis import DataAnalysis
print('DataAnalysis 导入 OK')
# 验证 QuickQuery 导入
from app.agent.quick_query import QuickQuery
print('QuickQuery 导入 OK')
print('=== 所有验证通过 ===')
"
```

期望：所有输出正常，无异常

- [ ] **Step 2: Commit（如有遗留文件）**

```bash
git status
# 如有未提交文件则 add + commit
```
