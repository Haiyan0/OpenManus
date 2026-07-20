---
name: tablestore
description: 连接阿里云 Tablestore（表格存储），查询实例下的所有数据表名称，或拉取指定表的全量数据并导出为本地 CSV 文件。
---

# Tablestore Skill

阿里云表格存储（Tablestore）数据查询与导出工具。

## 触发规则

当用户提到以下意图时调用此 skill：
- "查看 tablestore 有哪些表" / "列出表格存储的表" / "list tables"
- "拉取 tablestore 的 xxx 表" / "导出 xxx 表数据" / "pull table data"
- "从表格存储导出数据" / "下载表格存储数据"
- 任何涉及 Tablestore / 表格存储 数据查询或导出的请求

## 前置条件

1. 当前工作目录下需要有 `.env` 文件（复制 skill 目录下的 `.env.example` 并填入真实值）
2. Python 环境需安装 `tablestore` 和 `python-dotenv`（`pip install -r requirements.txt`）

## 使用方式

Skill 脚本位于 `~/.claude/skills/tablestore/tablestore_skill.py`，从项目目录执行：

### 列出所有表

```bash
python ~/.claude/skills/tablestore/tablestore_skill.py list
```

### 拉取表数据

```bash
python ~/.claude/skills/tablestore/tablestore_skill.py pull <表名> [--columns col1,col2] [--limit N]
```

**说明：**
- `--columns`（可选）：指定要拉取的列名，逗号分隔。不指定则拉取所有列
- `--limit`（可选）：最多拉取行数。不指定则全量拉取

**示例：**
```bash
# 拉取全量数据
python ~/.claude/skills/tablestore/tablestore_skill.py pull tan_core_rent_order

# 只拉取指定列，最多 500 行
python ~/.claude/skills/tablestore/tablestore_skill.py pull tan_core_rent_order --columns name,age --limit 500
```

## 输出

- **list 命令**：终端打印表名列表
- **pull 命令**：CSV 文件保存到当前工作目录下的 `.\output\{表名}_{时间戳}.csv`，终端打印拉取进度

## 配置文件

Skill 从当前工作目录读取 `.env` 文件，模板位于 `~/.claude/skills/tablestore/.env.example`：

```ini
TABLESTORE_ACCESS_KEY_ID=你的AK
TABLESTORE_ACCESS_KEY_SECRET=你的SK
TABLESTORE_ENDPOINT=https://xxx.cn-hangzhou.tablestore.aliyuncs.com
TABLESTORE_INSTANCE_NAME=实例名称
```

## 注意事项

- 执行前告知用户需要确保当前目录有 `.env` 文件
- `.env` 模板位于 `~/.claude/skills/tablestore/.env.example`
- 拉取大表时可能耗时较长，提醒用户耐心等待
- 每个项目可以有不同的 `.env`，连接不同的 Tablestore 实例
