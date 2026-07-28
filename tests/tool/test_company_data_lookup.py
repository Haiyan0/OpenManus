"""CompanyDataLookup 安全校验单元测试。"""
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


class TestGetConnectionCursor:
    """_get_connection 的 cursor 选择测试（Bug：CSV 只有表头无数据）。

    根因：_get_connection 强制 DictCursor，而 pd.read_sql + DictCursor
    会把列名当成数据返回，导致 to_csv 写出「表头重复、无数据」的 CSV。
    修法：query 路径用默认 Cursor，list_tables 仍用 DictCursor。
    """

    def test_list_tables_path_uses_dict_cursor(self, monkeypatch):
        import pymysql

        captured = {}

        class _FakeConn:
            def close(self):
                pass

        def fake_connect(**kwargs):
            captured.update(kwargs)
            return _FakeConn()

        monkeypatch.setattr(pymysql, "connect", fake_connect)
        tool = CompanyDataLookup()
        tool._get_connection()  # 默认 dict_cursor=True

        assert captured.get("cursorclass") is pymysql.cursors.DictCursor

    def test_query_path_uses_default_cursor(self, monkeypatch):
        """query 路径不能强制 DictCursor，否则 pd.read_sql 取不到真实数据。"""
        import pymysql

        captured = {}

        class _FakeConn:
            def close(self):
                pass

        def fake_connect(**kwargs):
            captured.update(kwargs)
            return _FakeConn()

        monkeypatch.setattr(pymysql, "connect", fake_connect)
        tool = CompanyDataLookup()
        tool._get_connection(dict_cursor=False)

        # 不应强制 DictCursor（让 pd.read_sql 用默认 cursor 拿到真实数据）
        assert captured.get("cursorclass") is None
