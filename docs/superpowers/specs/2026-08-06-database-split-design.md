# Web 业务库与数据查询库分离设计文档

> 状态：已审批 | 日期：2026-08-06 | 作者：bao (AI)

## 1. 背景与目标

### 1.1 现状

`config.toml [web]` 段只有单一 `mysql_database = "openmanus_web"`，该库名被两处消费：

- **Web 端（`app/web/database.py`）**：SQLAlchemy 异步引擎（aiomysql）连接池，承载 `users`、`chats`、`messages`、`user_files` 等 web 端表
- **业务数据查询（`app/tool/company_data_lookup.py`）**：pymysql 同步连接，`list_tables` 按 `TABLE_SCHEMA = mysql_database` 过滤数据字典，`query` 执行 SELECT 查询

两者共用同一库，web 端系统表与公司项目业务数据混在一个库中。

### 1.2 目标

在**同一 MySQL 实例（同 host/port/user/password，仅库名不同）**上实现库分离：

- Web 端表继续使用 `openmanus_web` 库
- `company_data_lookup` 业务数据查询切换到 `dev_data` 库

### 1.3 非目标

- 不涉及 web 端表结构的任何变更
- 不涉及数据库写入或数据迁移（`dev_data` 库已在 MySQL 侧建好并完成数据迁移）
- 不涉及连接账号/权限调整（同一账号对两个库均有访问权限）
- 不涉及 `list_tables` 数据字典之外的查询行为变更

---

## 2. 架构设计

### 2.1 配置项变更

`WebSettings`（`app/config.py`）新增字段：

```python
mysql_data_database: Optional[str] = Field(
    None,
    description="业务数据查询库（company_data_lookup 使用），缺省时回退 mysql_database",
)
```

- `mysql_database` 语义不变：仍为 **web 端库**（`openmanus_web`）
- `mysql_data_database`：**业务数据查询库**（`dev_data`），缺省回退 `mysql_database`，保证旧配置向后兼容
- `mysql_url` 属性不变（仍指向 web 库）

### 2.2 代码变更

`app/tool/company_data_lookup.py` 新增一个取库名的内部方法：

```python
def _data_database(self) -> str:
    """业务数据查询库名：优先 mysql_data_database，缺省回退 mysql_database。"""
    return config.web.mysql_data_database or config.web.mysql_database
```

替换全部 5 处 `config.web.mysql_database` 引用：

| 位置 | 用途 |
|------|------|
| `_get_connection()` | pymysql.connect(database=...) |
| `_get_connection()` 报错文案 | 连接失败提示中显示库名 |
| `_list_tables()` SQL 参数 | `WHERE t.TABLE_SCHEMA = %s` 过滤 |
| `_list_tables()` 空库提示 | "数据库 '{name}' 中未找到任何用户表" |
| `_list_tables()` 输出标题 | "📊 数据库: {name}" |

**不改动**：

- `app/web/database.py`（web 引擎仍用 `mysql_url` / `mysql_database`）
- `app/prompt/visualization.py`、`app/prompt/quick_query.py`（提示词仅描述工具使用流程，无库名硬编码）

### 2.3 配置与文档变更

| 文件 | 变更 |
|------|------|
| `config/config.toml` | `[web]` 段 `mysql_database` 之后插入 `mysql_data_database = "dev_data"` |
| `config/config.example.toml` | 同样插入，示例值 `"your_data_database"` |
| `docs/openmanus-web-ops-manual.md` | 补充 `mysql_data_database` 配置项说明 |

---

## 3. 数据流

```
company_data_lookup(action=..., query_or_sql=...)
  │
  ├─ mode = config.web.data_lookup_mode
  │    ├─ "local" → _execute_local（不变）
  │    └─ "mysql" → _execute_mysql
  │                   │
  │                   ├─ _get_connection()
  │                   │    database = _data_database()  ← dev_data（或回退 openmanus_web）
  │                   │
  │                   ├─ action="list_tables"
  │                   │    TABLE_SCHEMA = _data_database()  ← 只列业务库表
  │                   │
  │                   └─ action="query"
  │                        SELECT 执行于 _data_database() 连接的库
  │
  └─ web 端引擎（app/web/database.py）完全不受影响，仍连 openmanus_web
```

## 4. 错误处理

- `mysql_data_database` 未配置（旧配置或漏配）：回退 `mysql_database`，行为与现状完全一致，无报错
- 连接失败报错文案显示 `_data_database()` 解析后的实际库名，便于定位
- `list_tables` 空库提示同样显示实际库名

## 5. 测试

### 5.1 单元测试（`tests/web/test_config.py` 新增）

- `test_mysql_data_database_fallback`：`mysql_data_database` 为 None 时 `_data_database()` 返回 `mysql_database`
- `test_mysql_data_database_configured`：配置后返回业务库名

现有 `test_mysql_url_format` 保持通过（`mysql_url` 仍指向 web 库，不受新字段影响）。

### 5.2 验证方式

- `python -m pytest tests/web/test_config.py -v`
- `data_lookup_mode = "mysql"` 下运行一次 `list_tables`，确认只列出 `dev_data` 库的表（即 `_list_tables` 的 `TABLE_SCHEMA` 过滤生效）

## 6. 风险与权衡

- **回退逻辑的隐式行为**：若用户期望"配错库名时报错而非静默回退"，当前设计无法区分"未配置"与"配空值"。回退是向后兼容的合理默认，且文档会明确说明
- **`dev_data` 库中若仍有 web 相关表**：`list_tables` 会一并列出，需用户自行保证业务库纯净（MySQL 侧已迁移完成，此点已确认）
