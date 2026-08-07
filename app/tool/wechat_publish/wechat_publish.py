"""微信公众号发布工具。

通过 subprocess 调用自包含的 bun 脚本（scripts/wechat-api.ts）发布
markdown/html 文章到公众号草稿箱。凭据由脚本从 <cwd>/.baoyu-skills/.env
读取（cwd 必须是仓库根，见 spec §6）。
"""

import os
import shutil
import subprocess
from typing import Optional

from app.config import PROJECT_ROOT
from app.logger import logger
from app.tool.base import BaseTool, ToolResult


_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "scripts")
_SCRIPT_PATH = os.path.join(_SCRIPT_DIR, "wechat-api.ts")
_SUBPROCESS_TIMEOUT = 120


class WechatPublishTool(BaseTool):
    """发布文章到微信公众号草稿箱。"""

    name: str = "wechat_publish"
    description: str = (
        "微信公众号发布工具。两个 action：\n"
        "1. action='preview' — 本地渲染校验（--dry-run），不产生草稿，返回渲染结果或错误；"
        "发布前必须先用 preview 校验。\n"
        "2. action='publish' — 将 markdown 或 html 文件发布到公众号草稿箱，"
        "成功返回 media_id。\n"
        "参数：file_path 为文章文件绝对路径（markdown 优先，含 frontmatter 时标题/作者/摘要"
        "可自动读取）；title/summary/author/theme/cover 可选覆盖。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["preview", "publish"],
                "description": "preview=本地校验（推荐发布前先跑），publish=发布到草稿箱",
            },
            "file_path": {
                "type": "string",
                "description": "文章文件绝对路径（.md 或 .html）",
            },
            "title": {
                "type": "string",
                "description": "文章标题（可选，缺省读 frontmatter 或自动生成）",
            },
            "summary": {
                "type": "string",
                "description": "文章摘要（可选，最多 128 字符）",
            },
            "author": {
                "type": "string",
                "description": "作者名（可选，最多 16 字符）",
            },
            "theme": {
                "type": "string",
                "description": "渲染主题：default/grace/simple/modern（默认 default）",
            },
            "cover": {
                "type": "string",
                "description": "封面图片路径（可选，缺省用文章内第一张图）",
            },
        },
        "required": ["action", "file_path"],
    }

    # Sandbox 注入（可选，由 Agent.set_sandbox() 遍历 available_tools 自动注入）
    sandbox: Optional[object] = None
    # 容器内工作目录（sandbox 模式为 /workspace）
    workspace_dir: str = ""
    # 宿主机挂载源目录（sandbox 模式下容器 /workspace 的宿主映射）
    host_workspace_dir: str = ""

    def _resolve_host_path(self, file_path: str) -> str:
        """把容器内路径映射为宿主机路径（sandbox 模式）。

        容器 /workspace 与宿主机 host_workspace_dir 是同一 bind mount，
        替换前缀即得宿主可读路径；无沙箱或非 workspace 前缀路径原样返回。
        """
        if (
            self.sandbox is not None
            and self.workspace_dir
            and self.host_workspace_dir
            and file_path.startswith(self.workspace_dir)
        ):
            return file_path.replace(self.workspace_dir, self.host_workspace_dir, 1)
        return file_path

    def _resolve_runner(self) -> list[str]:
        """解析 bun 运行器：优先 bun，缺失时回退 npx -y bun。"""
        bun = shutil.which("bun")
        if bun:
            return [bun]
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if npx:
            return [npx, "-y", "bun"]
        raise RuntimeError("未找到 bun 运行时。请安装 bun（https://bun.sh）或确保 npm 可用。")

    def _build_command(
        self,
        action: str,
        file_path: str,
        title: str = "",
        summary: str = "",
        author: str = "",
        theme: str = "default",
        cover: str = "",
    ) -> list[str]:
        """拼装 wechat-api.ts 调用参数。"""
        cmd = self._resolve_runner() + [_SCRIPT_PATH, file_path]
        if title:
            cmd += ["--title", title]
        if summary:
            cmd += ["--summary", summary]
        if author:
            cmd += ["--author", author]
        cmd += ["--theme", theme]
        if cover:
            cmd += ["--cover", cover]
        if action == "preview":
            cmd += ["--dry-run"]
        return cmd

    def _run_script(self, cmd: list[str]) -> tuple[int, str, str]:
        """同步执行脚本（cwd 必须为仓库根，凭据 .baoyu-skills/.env 按 cwd 解析）。"""
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    async def execute(
        self,
        action: str,
        file_path: str,
        title: str = "",
        summary: str = "",
        author: str = "",
        theme: str = "default",
        cover: str = "",
    ) -> ToolResult:
        """执行发布操作。"""
        import asyncio

        if action not in ("preview", "publish"):
            return self.fail_response(
                f"不支持的 action: '{action}'，可选值为 'preview' 或 'publish'"
            )
        resolved_path = self._resolve_host_path(file_path)
        if not os.path.isfile(resolved_path):
            return self.fail_response(f"文章文件不存在: {file_path}")

        try:
            cmd = self._build_command(
                action, resolved_path, title, summary, author, theme, cover
            )
            code, stdout, stderr = await asyncio.to_thread(self._run_script, cmd)
        except subprocess.TimeoutExpired:
            return self.fail_response(f"发布脚本执行超时（>{_SUBPROCESS_TIMEOUT}s）。请重试或检查网络。")
        except RuntimeError as e:
            return self.fail_response(str(e))
        except Exception as e:
            logger.error(f"发布脚本执行异常: {e}", exc_info=True)
            return self.fail_response(f"发布脚本执行异常: {e}")

        if code != 0:
            logger.error(f"发布脚本失败(exit={code}): {stderr}")
            return self.fail_response(
                f"发布失败（脚本退出码 {code}）:\n{stderr}\n"
                f"常见原因：凭据缺失/错误（检查仓库根 .baoyu-skills/.env），"
                f"或 IP 不在公众号白名单（公众号后台 → 设置与开发 → 基本配置 → IP 白名单）。"
            )

        logger.info(f"发布成功: {stdout.strip()[:500]}")
        return ToolResult(output=stdout.strip() or "(脚本执行成功，无输出)")
