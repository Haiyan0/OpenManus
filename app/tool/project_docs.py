"""项目业务文档检索模块。

从 project_docs/ 目录树（企业/项目 两级）按需读取业务说明文档，
供 CompanyDataLookup 的 list_projects / get_doc action 分发调用。

约束：只依赖标准库与 ToolResult；无状态纯函数；root 参数可注入（测试用 tmp_path）。
"""
from pathlib import Path
from typing import Optional

from app.config import PROJECT_ROOT
from app.tool.base import ToolResult

# 文档根目录名（相对项目根；对齐 company_data_lookup.DATA_DIR 的常量先例）
DOCS_DIR = "project_docs"

# output 通道全文上限：超出时摘要走 output、全文走 system（对齐 list_tables 双通道惯例）
_DOC_OUTPUT_MAX = 8000
# 大文档时 output 通道摘要长度
_DOC_SUMMARY_MAX = 2000


def _doc_root(root: Optional[Path]) -> Path:
    """解析文档根目录：root 显式传入时用之（测试注入），否则用项目根下 DOCS_DIR。"""
    return Path(root) if root is not None else PROJECT_ROOT / DOCS_DIR


def _subdirs(path: Path) -> list[Path]:
    """目录下按名称排序的子目录列表。"""
    return sorted([p for p in path.iterdir() if p.is_dir()], key=lambda p: p.name)


def list_projects(query: str = "", root: Optional[Path] = None) -> ToolResult:
    """列出 project_docs 下所有企业/项目及文档状态。

    Args:
        query: 可选企业名过滤（子串、忽略大小写），空串列全部
        root: 文档根目录（默认 PROJECT_ROOT / DOCS_DIR）
    """
    doc_root = _doc_root(root)
    if not doc_root.is_dir():
        return ToolResult(
            error=(
                f"未配置项目业务文档（目录不存在: {doc_root}）。"
                f"可直接使用 list_tables 查询数据库表结构。"
            )
        )
    companies = _subdirs(doc_root)
    if not companies:
        return ToolResult(
            error=f"项目文档目录 '{doc_root}' 为空，可直接使用 list_tables 查询。"
        )
    q = (query or "").lower()
    lines = ["📁 项目业务文档清单:"]
    total = 0
    for comp in companies:
        if q and q not in comp.name.lower():
            continue
        projects = _subdirs(comp)
        lines.append(f"企业「{comp.name}」:")
        for proj in projects:
            total += 1
            mds = sorted(proj.glob("*.md"), key=lambda p: p.name)
            if mds:
                lines.append(
                    f"  - 项目「{proj.name}」文档: {', '.join(p.name for p in mds)}"
                )
            else:
                lines.append(f"  - 项目「{proj.name}」[无文档]")
    if total == 0:
        return ToolResult(
            error=f"未找到匹配 '{query}' 的企业。可用企业：\n"
            + "\n".join(f"  - {c.name}" for c in companies)
        )
    return ToolResult(output="\n".join(lines))
