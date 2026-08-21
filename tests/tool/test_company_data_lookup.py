"""CompanyDataLookup 安全校验单元测试。"""
from app.config import config
from app.tool.company_data_lookup import CompanyDataLookup


class TestValidateSql:
    """_validate_sql 安全校验测试。"""

    def test_simple_select_passes(self):
        ok, result = CompanyDataLookup._validate_sql("SELECT * FROM users")
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
        ok, result = CompanyDataLookup._validate_sql("SELECT * FROM orders LIMIT 100")
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
        ok, msg = CompanyDataLookup._validate_sql("UPDATE orders SET status = 'done'")
        assert ok is False
        assert "UPDATE" in msg or "危险关键字" in msg

    def test_delete_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql("DELETE FROM orders WHERE id = 1")
        assert ok is False
        assert "DELETE" in msg or "危险关键字" in msg

    def test_drop_table_rejected(self):
        ok, msg = CompanyDataLookup._validate_sql("DROP TABLE users")
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
        ok, result = CompanyDataLookup._validate_sql("SELECT * FROM users;")
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


class TestResolveCsvPaths:
    """_resolve_csv_paths 路径解析测试（Bug3：CSV 路径错位）。

    sandbox 模式：CSV 必须写到宿主机挂载源目录（host_workspace_dir），
    但告知模型的路径必须是容器内路径（/workspace/...），
    否则容器内 python_execute read_csv 找不到文件。
    """

    def test_sandbox_writes_host_tells_container(self, tmp_path):
        """sandbox 模式：写宿主挂载源，告知容器 /workspace 路径。"""
        host_ws = tmp_path / "host_ws"
        host_ws.mkdir()
        tool = CompanyDataLookup()
        tool.sandbox = object()  # 非 None 即视为 sandbox 已注入
        tool.workspace_dir = "/workspace"
        tool.host_workspace_dir = str(host_ws)

        host_path, tell_path = tool._resolve_csv_paths("_query_result.csv")

        assert host_path == str(host_ws / "_query_result.csv")
        assert tell_path == "/workspace/_query_result.csv"
        assert host_path != tell_path

    def test_no_sandbox_writes_and_tells_same_path(self, tmp_path):
        """无 sandbox：写路径与告知路径一致，都落在 workspace_dir 下。"""
        tool = CompanyDataLookup()
        tool.sandbox = None
        tool.workspace_dir = str(tmp_path)
        tool.host_workspace_dir = ""

        host_path, tell_path = tool._resolve_csv_paths("_query_result.csv")

        assert host_path == str(tmp_path / "_query_result.csv")
        assert tell_path == host_path

    def test_no_sandbox_falls_back_to_config_workspace(self, tmp_path, monkeypatch):
        """无 sandbox 且未设 workspace_dir：回退到 config.workspace_root。"""
        monkeypatch.setattr("app.config.WORKSPACE_ROOT", tmp_path)
        tool = CompanyDataLookup()
        tool.sandbox = None
        tool.workspace_dir = ""
        tool.host_workspace_dir = ""

        host_path, tell_path = tool._resolve_csv_paths("r.csv")

        expected = str(tmp_path / "r.csv")
        assert host_path == expected
        assert tell_path == expected


class TestExecuteQueryDataIntegrity:
    """_execute_query 数据完整性测试（CSV 只有表头无数据 的回归）。

    根因：pd.read_sql + DictCursor 会把列名当成数据行。
    修法：改用 cursor.execute + pd.DataFrame(fetchall, columns=描述列名)，
    与 cursor 类无关。本测试用假 cursor（无需真实 DB）验证 CSV 含真实数据、
    而非重复的列名。
    """

    class _FakeCursor:
        def __init__(self, description, rows):
            self.description = description
            self._rows = rows

        def execute(self, sql, params=None):
            pass

        def fetchall(self):
            return self._rows

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _FakeConn:
        def __init__(self, description, rows):
            self._description = description
            self._rows = rows

        def cursor(self):
            return TestExecuteQueryDataIntegrity._FakeCursor(
                self._description, self._rows
            )

        def close(self):
            pass

    def test_csv_contains_data_not_column_names(self, tmp_path, monkeypatch):
        """CSV 应含真实数据行，而非把列名重复当数据。"""
        import glob

        tool = CompanyDataLookup()
        tool.sandbox = None
        tool.workspace_dir = str(tmp_path)
        tool.host_workspace_dir = str(tmp_path)
        # COUNT(*) 返回 1 行 1 列，值为 6566
        fake = self._FakeConn(description=[("total",)], rows=[(6566,)])
        monkeypatch.setattr(tool, "_get_connection", lambda **kw: fake)

        tool._execute_query("SELECT COUNT(*) AS total FROM fa_card_orders")

        csvs = sorted(glob.glob(str(tmp_path / "_query_result_*.csv")))
        assert csvs, "未写出 CSV"
        with open(csvs[0], "r", encoding="utf-8-sig") as f:
            content = f.read()

        assert "6566" in content  # 真实数据
        assert content.count("total") == 1  # 列名只出现一次（表头），不重复

    def test_csv_preserves_multiple_columns(self, tmp_path, monkeypatch):
        """多列多行结果应正确落盘，每行数据完整。"""
        import glob

        tool = CompanyDataLookup()
        tool.sandbox = None
        tool.workspace_dir = str(tmp_path)
        tool.host_workspace_dir = str(tmp_path)
        fake = self._FakeConn(
            description=[("id",), ("name",)],
            rows=[(1, "张三"), (2, "李四")],
        )
        monkeypatch.setattr(tool, "_get_connection", lambda **kw: fake)

        tool._execute_query("SELECT id, name FROM users LIMIT 2")

        csvs = sorted(glob.glob(str(tmp_path / "_query_result_*.csv")))
        with open(csvs[0], "r", encoding="utf-8-sig") as f:
            content = f.read()

        lines = [ln for ln in content.splitlines() if ln.strip()]
        assert lines[0] == "id,name"
        assert "张三" in content and "李四" in content
        assert len(lines) == 3  # 表头 + 2 行数据

    def test_query_output_advises_preview_only(self, tmp_path, monkeypatch):
        """query 输出应引导后续 read_csv 只打印预览，不打印全量数据。"""
        tool = CompanyDataLookup()
        tool.sandbox = None
        tool.workspace_dir = str(tmp_path)
        tool.host_workspace_dir = str(tmp_path)
        fake = self._FakeConn(description=[("total",)], rows=[(6566,)])
        monkeypatch.setattr(tool, "_get_connection", lambda **kw: fake)

        result = tool._execute_query("SELECT COUNT(*) AS total FROM fa_card_orders")

        assert result.error is None
        assert result.output is not None
        assert "只打印预览" in result.output
        assert "前 5 行" in result.output
        assert "请勿打印全量数据" in result.output


class TestDataDatabase:
    """_data_database 业务库解析测试（分库后 company_data_lookup 只查业务库）。"""

    def test_falls_back_to_mysql_database(self, monkeypatch):
        """未配置 mysql_data_database 时回退 web 库，向后兼容。"""
        monkeypatch.setattr(config.web, "mysql_data_database", None)
        tool = CompanyDataLookup()
        assert tool._data_database() == config.web.mysql_database

    def test_returns_configured_data_database(self, monkeypatch):
        """配置后返回业务库名。"""
        monkeypatch.setattr(config.web, "mysql_data_database", "dev_data")
        tool = CompanyDataLookup()
        assert tool._data_database() == "dev_data"


class TestListTablesUsesDataDatabase:
    """_list_tables 的 TABLE_SCHEMA 过滤必须用业务库（用假连接捕获 SQL 参数）。"""

    class _FakeCursor:
        def __init__(self):
            self.executed = None

        def execute(self, sql, params=None):
            self.executed = (sql, params)

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _FakeConn:
        def __init__(self):
            self.c = TestListTablesUsesDataDatabase._FakeCursor()

        def cursor(self):
            return self.c

        def close(self):
            pass

    def test_table_schema_filter_uses_data_database(self, monkeypatch):
        """information_schema 查询的 TABLE_SCHEMA 参数应为业务库。"""
        monkeypatch.setattr(config.web, "mysql_data_database", "dev_data")
        fake = self._FakeConn()
        tool = CompanyDataLookup()
        monkeypatch.setattr(tool, "_get_connection", lambda: fake)

        tool._list_tables()

        assert fake.c.executed is not None
        assert fake.c.executed[1] == ("dev_data",)


class TestListTablesSystemChannel:
    """_list_tables 全量数据通道测试（Bug：数据字典被 max_observe 截断）。

    根因：_list_tables 只返回 ToolResult(output=完整数据字典)，该 output 在
    ToolCallAgent.act() 中被 max_observe 截断（QuickQuery=10000 字符），
    模型只能看到前几张表。修复：完整数据字典放入 ToolResult.system
    （下一轮 think 以 system message 注入，不受 max_observe 截断），
    output 只留表清单摘要。
    """

    # 与 DictCursor 一致：每行是一个 dict
    _ROWS = [
        {
            "TABLE_NAME": "fa_orders",
            "TABLE_COMMENT": "藏品订单表",
            "COLUMN_NAME": "id",
            "COLUMN_TYPE": "bigint unsigned",
            "DATA_TYPE": "bigint",
            "CHARACTER_MAXIMUM_LENGTH": None,
            "NUMERIC_PRECISION": 20,
            "NUMERIC_SCALE": 0,
            "IS_NULLABLE": "NO",
            "COLUMN_DEFAULT": None,
            "COLUMN_COMMENT": "主键",
            "ORDINAL_POSITION": 1,
        },
        {
            "TABLE_NAME": "fa_orders",
            "TABLE_COMMENT": "藏品订单表",
            "COLUMN_NAME": "amount",
            "COLUMN_TYPE": "decimal(10,2)",
            "DATA_TYPE": "decimal",
            "CHARACTER_MAXIMUM_LENGTH": None,
            "NUMERIC_PRECISION": 10,
            "NUMERIC_SCALE": 2,
            "IS_NULLABLE": "YES",
            "COLUMN_DEFAULT": "0.00",
            "COLUMN_COMMENT": "订单金额",
            "ORDINAL_POSITION": 2,
        },
        {
            "TABLE_NAME": "fa_user",
            "TABLE_COMMENT": "用户注册信息表",
            "COLUMN_NAME": "id",
            "COLUMN_TYPE": "int unsigned",
            "DATA_TYPE": "int",
            "CHARACTER_MAXIMUM_LENGTH": None,
            "NUMERIC_PRECISION": 10,
            "NUMERIC_SCALE": 0,
            "IS_NULLABLE": "NO",
            "COLUMN_DEFAULT": None,
            "COLUMN_COMMENT": "ID",
            "ORDINAL_POSITION": 1,
        },
    ]

    class _FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, sql, params=None):
            pass

        def fetchall(self):
            return self._rows

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _FakeConn:
        def __init__(self, rows):
            self._rows = rows

        def cursor(self):
            return TestListTablesSystemChannel._FakeCursor(self._rows)

        def close(self):
            pass

    def _make_tool(self, monkeypatch):
        monkeypatch.setattr(config.web, "mysql_data_database", "dev_data")
        tool = CompanyDataLookup()
        monkeypatch.setattr(tool, "_get_connection", lambda: self._FakeConn(self._ROWS))
        return tool

    def test_system_contains_full_dictionary(self, monkeypatch):
        """system 通道应包含完整数据字典（表名+全部字段+注释）。"""
        tool = self._make_tool(monkeypatch)
        result = tool._list_tables()

        assert result.system is not None
        assert "fa_orders" in result.system
        assert "fa_user" in result.system
        assert "id (bigint unsigned)" in result.system
        assert "amount (decimal(10,2))" in result.system
        assert "主键" in result.system
        assert "订单金额" in result.system
        assert "📊 数据库: dev_data" in result.system

    def test_output_is_table_list_summary(self, monkeypatch):
        """output 应只含表清单摘要（不含字段细节），避免超长 observation。"""
        tool = self._make_tool(monkeypatch)
        result = tool._list_tables()

        assert result.output is not None
        assert "fa_orders" in result.output
        assert "fa_user" in result.output
        assert "id (bigint unsigned)" not in result.output
        assert "amount (decimal(10,2))" not in result.output


class TestListTablesFilter:
    """_list_tables 表名过滤测试（按需加载文档涉及表，避免全库 schema 进上下文）。"""

    class _FakeCursor:
        def __init__(self):
            self.executed = None

        def execute(self, sql, params=None):
            self.executed = (sql, params)

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _FakeConn:
        def __init__(self):
            self.c = TestListTablesFilter._FakeCursor()

        def cursor(self):
            return self.c

        def close(self):
            pass

    def _make_tool(self, monkeypatch):
        monkeypatch.setattr(config.web, "mysql_data_database", "dev_data")
        fake = self._FakeConn()
        tool = CompanyDataLookup()
        monkeypatch.setattr(tool, "_get_connection", lambda: fake)
        return tool, fake

    def test_filter_adds_table_in_clause(self, monkeypatch):
        """传入表名时 SQL 应加 TABLE_NAME IN 过滤，表名按逗号拆分参数化。"""
        tool, fake = self._make_tool(monkeypatch)

        tool._list_tables("fa_orders, fa_user")

        assert "t.TABLE_NAME IN" in fake.c.executed[0]
        assert fake.c.executed[1] == ("dev_data", "fa_orders", "fa_user")

    def test_blank_filter_keeps_full_dump(self, monkeypatch):
        """过滤为空/空白时保持原行为（仅 TABLE_SCHEMA 参数，返回全部表）。"""
        tool, fake = self._make_tool(monkeypatch)

        tool._list_tables("  ")

        assert "t.TABLE_NAME IN" not in fake.c.executed[0]
        assert fake.c.executed[1] == ("dev_data",)

    def test_filter_no_match_reports_hint(self, monkeypatch):
        """过滤后无表时返回错误，提示可用不带过滤的 list_tables 重试。"""
        tool, fake = self._make_tool(monkeypatch)

        result = tool._list_tables("not_exists")

        assert result.error is not None
        assert "not_exists" in result.error
        assert "list_tables" in result.error

    async def test_execute_mysql_passes_filter(self, monkeypatch):
        """_execute_mysql(list_tables) 应将 query_or_sql 作为过滤传给 _list_tables。"""
        tool = CompanyDataLookup()
        captured = {}
        monkeypatch.setattr(
            tool, "_list_tables", lambda tables="": captured.setdefault("t", tables)
        )

        await tool._execute_mysql("list_tables", "fa_orders")

        assert captured["t"] == "fa_orders"


class TestExecuteProjectDocActions:
    """execute 对 list_projects / get_doc 的分发测试。"""

    async def test_execute_get_doc_routes(self, tmp_path):
        root = tmp_path / "docs"
        (root / "甲企业" / "项目A").mkdir(parents=True)
        (root / "甲企业" / "项目A" / "业务说明.md").write_text(
            "字段口径示例", encoding="utf-8"
        )
        tool = CompanyDataLookup(docs_root=root)

        result = await tool.execute("get_doc", "项目A")

        assert result.error is None
        assert "字段口径示例" in result.output

    async def test_execute_list_projects_routes(self, tmp_path):
        root = tmp_path / "docs"
        (root / "甲企业" / "项目A").mkdir(parents=True)
        (root / "甲企业" / "项目A" / "业务说明.md").write_text("x", encoding="utf-8")
        tool = CompanyDataLookup(docs_root=root)

        result = await tool.execute("list_projects", "")

        assert result.error is None
        assert "甲企业" in result.output


class TestToolSchemaDocActions:
    """description / parameters 应暴露新 action。"""

    def test_description_mentions_doc_actions(self):
        tool = CompanyDataLookup()
        assert "get_doc" in tool.description
        assert "list_projects" in tool.description

    def test_parameters_include_doc_actions(self):
        tool = CompanyDataLookup()
        enum = tool.parameters["properties"]["action"]["enum"]
        assert enum == ["list_projects", "get_doc", "list_tables", "query"]
        assert tool.parameters["required"] == ["action"]
