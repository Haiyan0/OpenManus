"""QuickQuery.set_sandbox 接线测试（Bug3：host_workspace 注入）。

验证 set_sandbox 把宿主机挂载源目录传到 CompanyDataLookup 工具，
使其在 sandbox 模式下把 CSV 写到容器可见的宿主目录。
"""
from app.agent.quick_query import QuickQuery
from app.tool.company_data_lookup import CompanyDataLookup


class TestSetSandboxWiring:
    def test_set_sandbox_injects_host_workspace_to_company_lookup(self, tmp_path):
        agent = QuickQuery()
        fake_sandbox = object()
        host_ws = str(tmp_path / "host_ws")

        agent.set_sandbox(fake_sandbox, workspace="/workspace", host_workspace=host_ws)

        cdl = agent.available_tools.get_tool("company_data_lookup")
        assert isinstance(cdl, CompanyDataLookup)
        assert cdl.sandbox is fake_sandbox
        assert cdl.workspace_dir == "/workspace"
        assert cdl.host_workspace_dir == host_ws

    def test_set_sandbox_without_host_workspace_leaves_empty(self):
        agent = QuickQuery()
        agent.set_sandbox(object(), workspace="/workspace")

        cdl = agent.available_tools.get_tool("company_data_lookup")
        assert cdl.host_workspace_dir == ""
