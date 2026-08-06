# Web 业务库与数据查询库分离实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 同一 MySQL 实例上分离 web 库（`openmanus_web`）与业务数据查询库（`dev_data`），新增 `mysql_data_database` 配置项供 `company_data_lookup` 使用。

**Architecture:** `WebSettings` 新增可选字段 `mysql_data_database`；`CompanyDataLookup` 新增 `_data_database()` 方法（优先业务库、缺省回退 web 库），替换文件内全部 5 处 `config.web.mysql_database` 引用。web 引擎（`app/web/database.py`）与 `mysql_url` 属性不动。

**Tech Stack:** Python 3.12 / pydantic / pymysql / pytest / toml

**Spec:** `docs/superpowers/specs/2026-08-06-database-split-design.md`

## Global Constraints

- Python 解释器（本机固定）：`C:\Users\hyh\anaconda3\envs\open_manus\python.exe`，**不要用** `python`/`python3`
- Shell 为 PowerShell 5.1（Win11），不支持 `&&`，命令间用 `;` 衔接
- 跑测试用 `-m pytest` 形式避免入口被 `main.py` 拦截
- `config/config.toml` 被 gitignore：可本地修改，**不提交**；`config/config.example.toml` 被追踪，需提交
- 提交前运行 pre-commit：`pre-commit run --all-files`（链路 black → autoflake → isort）
- 代码注释用简体中文，标识符英文

---

### Task 1: `WebSettings` 新增 `mysql_data_database` 字段

**Files:**
- Modify: `app/config.py:115`（`mysql_database` 字段定义之后，`jwt_secret_key` 之前）
- Test: `tests/web/test_config.py`（追加两个测试）
- Modify: `config/config.toml:124`（`mysql_database` 行之后插入，仅本地、不提交）
- Modify: `config/config.example.toml:121`（`mysql_database` 行之后插入，需提交）

**Interfaces:**
- Consumes: 无（独立任务）
- Produces: `WebSettings.mysql_data_database: Optional[str] = None`（Task 2 消费）

- [ ] **Step 1: 写失败测试**

在 `tests/web/test_config.py` 末尾追加：

```python
from app.config import WebSettings


def test_mysql_data_database_field_optional():
    """mysql_data_database 应为可选字段，默认 None。"""
    field = WebSettings.model_fields["mysql_data_database"]
    assert field.default is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/web/test_config.py::test_mysql_data_database_field_optional -v`
Expected: FAIL，报 `KeyError: 'mysql_data_database'`

- [ ] **Step 3: 实现字段**

在 `app/config.py` 的 `WebSettings` 中，`mysql_database` 字段之后新增：

```python
    mysql_data_database: Optional[str] = Field(
        None,
        description="业务数据查询库（company_data_lookup 使用），缺省回退 mysql_database",
    )
```

确认文件顶部已 `from typing import Optional`（已存在，无需改动）。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/web/test_config.py -v`
Expected: 全部 PASS（含现有 `test_web_config_exists` / `test_mysql_url_format`，确认 `mysql_url` 仍指向 web 库）

- [ ] **Step 5: 更新配置文件**

`config/config.toml` `[web]` 段 `mysql_database = "openmanus_web"` 之后插入（本地生效，gitignore 不提交）：

```toml
# 业务数据查询库（company_data_lookup 使用，缺省回退 mysql_database）
mysql_data_database = "dev_data"
```

`config/config.example.toml` `[web]` 段 `mysql_database = "openmanus_web"` 之后插入（需提交）：

```toml
# 业务数据查询库（company_data_lookup 使用，缺省回退 mysql_database）
mysql_data_database = "your_data_database"
```

验证：`Get-Content config/config.toml | Select-String -Pattern "mysql_data_database"` 应输出 `mysql_data_database = "dev_data"`

- [ ] **Step 6: 回归验证 + 提交**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/web/test_config.py -v`
Expected: 全部 PASS

```bash
git add app/config.py tests/web/test_config.py config/config.example.toml
git commit -m "feat: WebSettings 新增 mysql_data_database 业务数据查询库配置项"
```

---

### Task 2: `CompanyDataLookup` 切换业务库

**Files:**
- Modify: `app/tool/company_data_lookup.py`（新增 `_data_database()`，替换 5 处 `config.web.mysql_database`）
  - `_get_connection()`: 第 286-296 行 `pymysql.connect(database=...)`、第 300-303 行报错文案
  - `_list_tables()`: 第 342 行 `cursor.execute(sql, (...,))`、第 347 行空库提示、第 365 行输出标题
- Test: `tests/tool/test_company_data_lookup.py`（追加两个测试类）
- Modify: `docs/openmanus-web-ops-manual.md:222-240`（"配置连接" 小节补一行配置说明）

**Interfaces:**
- Consumes: `WebSettings.mysql_data_database`（Task 1）
- Produces: `CompanyDataLookup._data_database() -> str`（实例方法，无外部消费者）

- [ ] **Step 1: 写失败测试**

在 `tests/tool/test_company_data_lookup.py` 顶部 import 追加：

```python
from app.config import config
```

文件末尾追加两个测试类：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/tool/test_company_data_lookup.py::TestDataDatabase tests/tool/test_company_data_lookup.py::TestListTablesUsesDataDatabase -v`
Expected: FAIL，报 `AttributeError: 'CompanyDataLookup' object has no attribute '_data_database'`

- [ ] **Step 3: 实现 `_data_database()` 并替换引用**

在 `app/tool/company_data_lookup.py` 的 `# ── 数据库连接 ──` 小节、`_get_connection()` 方法之前新增：

```python
    def _data_database(self) -> str:
        """业务数据查询库名：优先 mysql_data_database，缺省回退 mysql_database。"""
        return config.web.mysql_data_database or config.web.mysql_database
```

替换以下 5 处 `config.web.mysql_database` 为 `self._data_database()`：

1. `_get_connection()` 中 `database=config.web.mysql_database,` → `database=self._data_database(),`
2. `_get_connection()` 报错文案 `f"/{config.web.mysql_database}): {e}"` → `f"/{self._data_database()}): {e}"`
3. `_list_tables()` 中 `cursor.execute(sql, (config.web.mysql_database,))` → `cursor.execute(sql, (self._data_database(),))`
4. `_list_tables()` 空库提示 `f"数据库 '{config.web.mysql_database}' 中未找到任何用户表。"` → `f"数据库 '{self._data_database()}' 中未找到任何用户表。"`
5. `_list_tables()` 输出标题 `f"📊 数据库: {config.web.mysql_database}"` → `f"📊 数据库: {self._data_database()}"`

验证：`Select-String -Path app\tool\company_data_lookup.py -Pattern "config.web.mysql_database"` 应无匹配

- [ ] **Step 4: 跑测试确认通过**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/tool/test_company_data_lookup.py -v`
Expected: 全部 PASS（含现有 `TestValidateSql` / `TestResolveCsvPaths` / `TestExecuteQueryDataIntegrity` 回归）

- [ ] **Step 5: 更新运维手册**

`docs/openmanus-web-ops-manual.md` "### 3.4 配置连接" 的 toml 代码块（第 226-240 行）中，`mysql_database = "openmanus_web"` 之后插入：

```toml
mysql_data_database = "dev_data"   # 业务数据查询库（可选，缺省回退 mysql_database）
```

- [ ] **Step 6: 全量回归 + pre-commit + 提交**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/tool/test_company_data_lookup.py tests/web/test_config.py -v`
Expected: 全部 PASS

```bash
pre-commit run --all-files
```

修复 pre-commit 报出的格式问题（black/autoflake/isort）后：

```bash
git add app/tool/company_data_lookup.py tests/tool/test_company_data_lookup.py docs/openmanus-web-ops-manual.md
git commit -m "feat: CompanyDataLookup 切换到独立业务数据查询库（mysql_data_database）"
```

- [ ] **Step 7: 手动验证（可选，需 MySQL 可达）**

Run: `C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests/web/test_config.py::test_mysql_url_format -v` 后，用一条临时脚本确认 `_data_database()` 返回 `dev_data`：

```python
from app.config import config
from app.tool.company_data_lookup import CompanyDataLookup
print("data_database:", CompanyDataLookup()._data_database())
print("web_database :", config.web.mysql_database)
```

Expected: `data_database: dev_data`、`web_database : openmanus_web`

---

## Self-Review 记录

- **Spec 覆盖**：配置项（Task 1）、5 处引用替换（Task 2 Step 3）、config.toml/example（Task 1 Step 5）、运维手册（Task 2 Step 5）、回退逻辑测试（Task 2 Step 1）、`mysql_url` 不变回归（Task 1 Step 4）——全部覆盖
- **无占位符**：每个步骤含具体代码与命令
- **类型一致**：`_data_database() -> str` 在测试与实现中签名一致；`mysql_data_database: Optional[str] = None` 在 Task 1 定义、Task 2 消费，命名一致
