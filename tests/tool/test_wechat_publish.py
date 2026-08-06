"""WechatPublishTool 单元测试（mock subprocess，无真实网络）。"""
from pathlib import Path

from app.config import PROJECT_ROOT
from app.tool.wechat_publish.wechat_publish import WechatPublishTool


class TestBuildCommand:
    """_build_command 参数拼装测试。"""

    def test_publish_default_theme(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(
            action="publish",
            file_path="article.md",
            title="我的文章",
            summary="摘要",
            author="刻晴宇宙",
            theme="default",
            cover="",
        )
        joined = " ".join(cmd)
        assert "wechat-api.ts" in joined
        assert "article.md" in joined
        assert "--title" in joined and "我的文章" in joined
        assert "--summary" in joined and "摘要" in joined
        assert "--author" in joined and "刻晴宇宙" in joined
        assert "--theme" in joined and "default" in joined
        assert "--dry-run" not in joined

    def test_preview_includes_dry_run(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(action="preview", file_path="a.md")
        assert "--dry-run" in cmd

    def test_cover_passed_through(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(
            action="publish", file_path="a.md", cover="imgs/cover.png"
        )
        assert "--cover" in cmd and "imgs/cover.png" in cmd

    def test_empty_optional_params_omitted(self):
        tool = WechatPublishTool()
        cmd = tool._build_command(action="publish", file_path="a.md")
        joined = " ".join(cmd)
        assert "--title" not in joined
        assert "--summary" not in joined
        assert "--author" not in joined
        assert "--theme" in joined and "default" in joined  # theme 恒传


class TestRunScript:
    """_run_script 子进程执行测试。"""

    def test_success_returns_stdout(self, monkeypatch):
        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 0
            stdout = "OK output"
            stderr = ""

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        code, out, err = tool._run_script(["bun", "x.ts"])
        assert code == 0
        assert out == "OK output"

    def test_failure_returns_stderr(self, monkeypatch):
        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 2
            stdout = ""
            stderr = "boom"

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        code, out, err = tool._run_script(["bun", "x.ts"])
        assert code == 2
        assert err == "boom"

    def test_cwd_is_project_root(self, monkeypatch):
        tool = WechatPublishTool()
        captured = {}

        class _FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""

        def _fake_run(cmd, **kwargs):
            captured["cwd"] = kwargs.get("cwd")
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        tool._run_script(["bun", "x.ts"])
        assert Path(captured["cwd"]) == PROJECT_ROOT


class TestExecute:
    """execute 入口测试。"""

    def test_execute_publish_success(self, monkeypatch):
        """execute 成功路径：透传脚本 stdout。"""
        import asyncio

        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 0
            stdout = '{"media_id": "abc123"}'
            stderr = ""

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        result = asyncio.run(
            tool.execute(action="publish", file_path=str(Path(__file__)))
        )
        assert result.error is None
        assert "abc123" in str(result.output)

    def test_execute_publish_failure(self, monkeypatch):
        """execute 失败路径：返回 error 且不含 crash。"""
        import asyncio

        tool = WechatPublishTool()

        class _FakeProc:
            returncode = 1
            stdout = ""
            stderr = "access_token invalid"

        def _fake_run(cmd, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("subprocess.run", _fake_run)
        result = asyncio.run(
            tool.execute(action="publish", file_path=str(Path(__file__)))
        )
        assert result.error is not None
        assert "access_token invalid" in result.error

    def test_execute_file_not_found(self):
        import asyncio

        tool = WechatPublishTool()
        result = asyncio.run(tool.execute(action="publish", file_path="no_such.md"))
        assert result.error is not None
        assert "不存在" in result.error
