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
    q = (query or "").strip().lower()
    lines = ["📁 项目业务文档清单:"]
    matched_company = False
    for comp in companies:
        if q and q not in comp.name.lower():
            continue
        matched_company = True
        projects = _subdirs(comp)
        lines.append(f"企业「{comp.name}」:")
        if not projects:
            lines.append("  - [无项目目录]")
            continue
        for proj in projects:
            mds = sorted(proj.glob("*.md"), key=lambda p: p.name)
            if mds:
                lines.append(
                    f"  - 项目「{proj.name}」文档: {', '.join(p.name for p in mds)}"
                )
            else:
                lines.append(f"  - 项目「{proj.name}」[无文档]")
    if not matched_company:
        return ToolResult(
            error=f"未找到匹配 '{query}' 的企业。可用企业：\n"
            + "\n".join(f"  - {c.name}" for c in companies)
        )
    return ToolResult(output="\n".join(lines))


def _match_project(doc_root: Path, query: str):
    """按 query 匹配项目目录。

    匹配规则（与 company_data_lookup local 模式同构）：
    1. query 含 / 且对应目录在 doc_root 内 → 精确命中（绝对路径 query 直接拒绝）
    2. 企业名 in query（子串、忽略大小写）→ 企业内再项目名 in query：
       唯一 → 命中；多个 → 候选清单；零个 → 该企业可用项目
    3. 未命中企业名 → 全树项目名 in query：
       唯一 → 命中；多个 → 候选清单；零个 → 全量可用清单

    Returns:
        (status, data)：status 为 "hit" 时 data 是 Path；
        为 "ambiguous"/"none" 时 data 是提示文本
    """
    companies = _subdirs(doc_root)
    doc_root_r = doc_root.resolve()
    q_raw = query.strip()
    q = q_raw.lower()
    # 0. 拒绝绝对路径 query（防宿主机任意路径读取；仅接受企业/项目相对路径）
    if Path(q_raw.replace("\\", "/")).is_absolute():
        return "none", f"仅支持企业名/项目名相对路径，不支持绝对路径: {q_raw}"
    # 1. 精确路径：query 含路径分隔符且对应目录存在 → 精确命中
    #    （resolve 后须仍在 doc_root 内且非根目录本身，防 ../ 逃逸）
    direct = (doc_root_r / q_raw.replace("\\", "/")).resolve()
    if (
        ("/" in q_raw or "\\" in q_raw)
        and direct != doc_root_r
        and direct.is_relative_to(doc_root_r)
        and direct.is_dir()
    ):
        return "hit", direct
    # 2. 企业名 in query
    for comp in companies:
        if comp.name.lower() in q:
            projects = _subdirs(comp)
            hits = [p for p in projects if p.name.lower() in q]
            if len(hits) == 1:
                return "hit", hits[0]
            if len(hits) > 1:
                return "ambiguous", "\n".join(
                    f"  - {comp.name}/{p.name}" for p in hits
                )
            return "none", (
                f"企业「{comp.name}」匹配但未指定项目，该企业可用项目：\n"
                + "\n".join(f"  - {p.name}" for p in projects)
                + "\n请用「企业名/项目名」或项目名精确重试。"
            )
    # 3. 全树项目名 in query
    hits = [(c, p) for c in companies for p in _subdirs(c) if p.name.lower() in q]
    if len(hits) == 1:
        return "hit", hits[0][1]
    if len(hits) > 1:
        return "ambiguous", "\n".join(f"  - {c.name}/{p.name}" for c, p in hits)
    available = "\n".join(
        f"  - {c.name}/{p.name}" for c in companies for p in _subdirs(c)
    )
    return "none", f"未找到匹配 '{query}' 的项目。可用清单：\n{available}"


def get_doc(query: str, root: Optional[Path] = None) -> ToolResult:
    """读取指定项目的业务文档（企业/项目 目录下所有 .md 按文件名拼接）。

    Args:
        query: 企业名/项目名自由文本（如 "甲企业/项目A" 或 "项目A"）
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
    if not query or not query.strip():
        return ToolResult(
            error="get_doc 需要企业名/项目名，可先用 list_projects 查看可用项目。"
        )
    status, data = _match_project(doc_root, query)
    if status == "ambiguous":
        return ToolResult(error=f"匹配到多个项目，请精确指定：\n{data}")
    if status == "none":
        return ToolResult(error=data)
    proj_dir: Path = data
    mds = sorted(proj_dir.glob("*.md"), key=lambda p: p.name)
    if not mds:
        return ToolResult(
            error=(
                f"项目「{proj_dir.parent.name}/{proj_dir.name}」尚未维护业务文档。"
                f"请改用 list_tables 了解表结构。"
            )
        )
    parts = []
    for f in mds:
        try:
            parts.append(f.read_text(encoding="utf-8"))
        except Exception as e:
            return ToolResult(error=f"读取文档失败: {f} → {e}")
    full = "\n\n".join(parts)
    source = f"{proj_dir.parent.name}/{proj_dir.name}"
    if len(full) <= _DOC_OUTPUT_MAX:
        return ToolResult(
            output=(
                f"已读取项目业务文档：{source}（{len(mds)} 个文件，共 {len(full)} 字符）\n"
                f"{'─' * 60}\n{full}"
            )
        )
    # 大文档：output 给摘要，全文走 system 通道（对齐 list_tables 双通道惯例）
    summary = full[:_DOC_SUMMARY_MAX]
    return ToolResult(
        output=(
            f"已读取项目业务文档：{source}（{len(mds)} 个文件，共 {len(full)} 字符）\n"
            f"文档较长，以下为开头摘要；完整内容已通过 system 通道提供，请直接据此分析。\n"
            f"{'─' * 60}\n{summary}..."
        ),
        system=f"# 项目业务文档全文（{source}）\n{full}",
    )
