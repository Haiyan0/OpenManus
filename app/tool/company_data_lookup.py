"""
公司数据资源查找工具。

在 company_data_resource 目录中按企业名称和项目名称匹配用户的查询，
返回匹配的本地 CSV 数据文件列表，供数据分析使用。
"""

import os
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.logger import logger
from app.tool.base import BaseTool, ToolResult


class CompanyDataLookup(BaseTool):
    """在 company_data_resource 目录中查找与用户查询匹配的本地公司数据文件。"""

    name: str = "company_data_lookup"
    description: str = (
        "在 company_data_resource 目录中查找与用户查询匹配的本地公司数据文件。"
        "当用户提及公司、企业、业务数据分析时，优先调用此工具检查本地是否有相关数据。"
        "返回匹配的公司名称、项目名称及 CSV 文件列表。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用户的原始提问或数据分析需求描述，用于匹配公司名称和项目名称",
            },
        },
        "required": ["query"],
    }

    # 公司数据资源目录（相对于项目根目录）
    DATA_DIR: str = "company_data_resource"

    async def execute(self, query: str) -> ToolResult:
        """
        在 company_data_resource 中查找匹配的公司数据文件。

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

        # 检查目录是否存在
        if not data_root.exists() or not data_root.is_dir():
            logger.warning(f"公司数据目录不存在: {data_root}")
            return self.fail_response(
                f"公司数据目录 '{self.DATA_DIR}' 不存在或不可访问。"
                f"请使用常规数据分析流程，直接通过用户提供的文件路径读取数据。"
            )

        query_lower = query.lower()

        try:
            # 遍历所有企业目录
            companies = [d for d in sorted(data_root.iterdir()) if d.is_dir()]
            if not companies:
                logger.warning(f"公司数据目录为空: {data_root}")
                return self.fail_response(
                    f"公司数据目录 '{self.DATA_DIR}' 下没有企业数据。"
                    f"请使用常规数据分析流程。"
                )

            for company_dir in companies:
                company_name = company_dir.name

                # 不区分大小写的子串匹配
                if company_name.lower() not in query_lower:
                    continue

                logger.info(f"命中企业: {company_name}")

                # 遍历项目目录
                projects = [
                    d for d in sorted(company_dir.iterdir()) if d.is_dir()
                ]
                for project_dir in projects:
                    project_name = project_dir.name

                    # 项目名也做子串匹配
                    if project_name.lower() not in query_lower:
                        continue

                    logger.info(f"命中项目: {company_name}/{project_name}")

                    # 收集该目录下所有 CSV 文件
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

                    # 构建成功响应信息
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
                        f"请使用 NormalPythonExecute（pandas.read_csv）读取上述文件进行数据分析，"
                        f"并在分析前告知用户已找到以下本地数据文件：{', '.join(f['name'] for f in csv_files)}"
                    )

                    return ToolResult(
                        output=output_message,
                        system=(
                            f"已匹配本地公司数据：企业={company_name}，项目={project_name}，"
                            f"文件数={len(csv_files)}。告知用户后自动读取 CSV 进行分析。"
                        ),
                    )

                # 命中企业但未命中具体项目 —— 列出可用项目供参考
                available_projects = [d.name for d in projects]
                return self.fail_response(
                    f"在 '{company_name}' 企业下未找到与查询完全匹配的项目。\n"
                    f"该企业下有以下可用项目：{', '.join(available_projects)}\n"
                    f"请确认用户需要分析哪个项目的数据，或提示用户补充项目名称。"
                )

            # 没有任何企业命中
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
