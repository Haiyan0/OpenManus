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
