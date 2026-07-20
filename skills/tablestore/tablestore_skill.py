#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tablestore Skill — 阿里云表格存储数据拉取工具
用法:
  python tablestore_skill.py list
  python tablestore_skill.py pull <table_name> [--columns col1,col2] [--limit N]

配置文件：当前工作目录下的 .env 文件
输出目录：当前工作目录下的 output/
"""
import os
import csv
import argparse
import sys
from datetime import datetime

from dotenv import load_dotenv
from tablestore import OTSClient, INF_MIN, INF_MAX, Direction

# ============================================================
# 配置加载
# ============================================================


def load_config():
    """从当前工作目录的 .env 文件加载 Tablestore 连接配置。"""
    cwd = os.getcwd()
    env_path = os.path.join(cwd, ".env")

    if not os.path.exists(env_path):
        print(f"错误: 配置文件 {env_path} 不存在。", file=sys.stderr)
        print("请复制 .env.example 为 .env 并填入真实的 Tablestore 连接信息。", file=sys.stderr)
        print(f"模板文件位于: {os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.example')}", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_path)

    required_keys = [
        "TABLESTORE_ACCESS_KEY_ID",
        "TABLESTORE_ACCESS_KEY_SECRET",
        "TABLESTORE_ENDPOINT",
        "TABLESTORE_INSTANCE_NAME",
    ]

    config = {}
    missing = []
    for key in required_keys:
        val = os.getenv(key)
        if not val:
            missing.append(key)
        else:
            config[key] = val

    if missing:
        print(f"错误: .env 文件中缺少以下配置项: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    return config


def init_client(config):
    """初始化 Tablestore 客户端。"""
    return OTSClient(
        config["TABLESTORE_ENDPOINT"],
        config["TABLESTORE_ACCESS_KEY_ID"],
        config["TABLESTORE_ACCESS_KEY_SECRET"],
        config["TABLESTORE_INSTANCE_NAME"],
    )


# ============================================================
# list 命令
# ============================================================


def cmd_list(client):
    """列出实例下所有数据表名称。"""
    try:
        tables = client.list_table()
        if not tables:
            print("当前实例下没有数据表。")
            return
        print(f"共 {len(tables)} 张表:")
        for name in sorted(tables):
            print(f"  - {name}")
    except Exception as e:
        print(f"列出表失败: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================
# pull 命令
# ============================================================


def get_table_all_rows(client, table_name, columns_to_get=None,
                       max_version=1, row_limit=None):
    """使用 get_range 分页拉取表的全量数据。"""
    desc = client.describe_table(table_name)
    pk_names = [pk[0] for pk in desc.table_meta.schema_of_primary_key]

    inclusive_start = [(name, INF_MIN) for name in pk_names]
    exclusive_end = [(name, INF_MAX) for name in pk_names]

    all_rows = []
    next_start = inclusive_start
    page = 0

    print(f"\n开始拉取 [{table_name}] 全量数据...")

    while True:
        page += 1
        # 当设置 row_limit 时，仅请求所需剩余行数，避免过度拉取浪费带宽/配额
        fetch_limit = 100
        if row_limit is not None:
            remaining = row_limit - len(all_rows)
            fetch_limit = min(100, remaining)

        _consumed, next_pk, row_list, _next_token = client.get_range(
            table_name=table_name,
            direction=Direction.FORWARD,
            inclusive_start_primary_key=next_start,
            exclusive_end_primary_key=exclusive_end,
            columns_to_get=columns_to_get,
            limit=fetch_limit,
            max_version=max_version,
        )

        if row_list:
            all_rows.extend(row_list)
            print(f"  第 {page} 页: 本页 {len(row_list)} 行, 累计 {len(all_rows)} 行")

        if next_pk is None or len(row_list) == 0:
            break

        next_start = next_pk

        if row_limit is not None and len(all_rows) >= row_limit:
            all_rows = all_rows[:row_limit]
            break

    print(f"拉取完成，共 {len(all_rows)} 行。")
    return all_rows


def rows_to_records(rows):
    """将 Tablestore Row 对象列表转换为字典列表（合并主键列 + 属性列）。"""
    records = []
    for row in rows:
        record = {}
        for pk_name, pk_value in row.primary_key:
            record[pk_name] = pk_value
        for col_name, col_value, _ts in row.attribute_columns:
            record[col_name] = col_value
        records.append(record)
    return records


def collect_all_column_names(records):
    """从所有记录中收集不重复列名（保持插入顺序）。"""
    names = []
    seen = set()
    for rec in records:
        for key in rec:
            if key not in seen:
                names.append(key)
                seen.add(key)
    return names


def export_to_csv(rows, table_name, output_dir):
    """将行数据导出为 CSV 文件，返回文件路径。"""
    records = rows_to_records(rows)
    if not records:
        print(f"[{table_name}] 无数据，跳过导出。")
        return None

    os.makedirs(output_dir, exist_ok=True)
    column_names = collect_all_column_names(records)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{table_name}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=column_names)
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)

    print(f"[{table_name}] 已导出 {len(records)} 行 → {filepath}")
    return filepath


def cmd_pull(client, table_name, columns, limit):
    """拉取指定表全量数据并导出为 CSV。"""
    columns_to_get = [c.strip() for c in columns.split(",") if c.strip()] if columns else None
    output_dir = os.path.join(os.getcwd(), "output")

    try:
        rows = get_table_all_rows(
            client,
            table_name,
            columns_to_get=columns_to_get,
            row_limit=limit,
        )
    except Exception as e:
        print(f"错误: 表 [{table_name}] 拉取失败: {e}", file=sys.stderr)
        sys.exit(1)

    filepath = export_to_csv(rows, table_name, output_dir)
    if filepath:
        print(f"\n导出成功: {filepath}")


# ============================================================
# CLI 入口
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Tablestore 数据拉取工具"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list 子命令
    subparsers.add_parser("list", help="列出所有数据表")

    # pull 子命令
    pull_parser = subparsers.add_parser("pull", help="拉取指定表数据")
    pull_parser.add_argument("table_name", help="目标表名")
    pull_parser.add_argument(
        "--columns", "-c",
        help="指定拉取的列名，逗号分隔（默认拉取所有列）",
        default=None,
    )
    pull_parser.add_argument(
        "--limit", "-l",
        type=int,
        help="最多拉取行数（默认不限制）",
        default=None,
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit 必须是正整数")

    config = load_config()
    client = init_client(config)

    if args.command == "list":
        cmd_list(client)
    elif args.command == "pull":
        cmd_pull(client, args.table_name, args.columns, args.limit)


if __name__ == "__main__":
    main()
