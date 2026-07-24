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
            return await asyncio.to_thread(self._execute_query, query_or_sql)
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
