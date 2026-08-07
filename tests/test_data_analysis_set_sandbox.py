"""DataAnalysis.set_sandbox 接线测试。

验证 set_sandbox 把宿主机挂载源目录注入 DataVisualization 的
_host_workspace_dir（npx ts-node 写 chart 文件用），
避免 chart 写入公共 workspace 而非用户隔离目录（回归 d31c9d5 修复）。
"""
from app.agent.data_analysis import DataAnalysis
from app.tool.chart_visualization.data_visualization import DataVisualization
from app.tool.company_data_lookup import CompanyDataLookup


class TestDataAnalysisSetSandbox:
    def test_set_sandbox_injects_host_workspace_to_data_visualization(self, tmp_path):
        agent = DataAnalysis()
        fake_sandbox = object()
        host_ws = str(tmp_path / "host_ws")

        agent.set_sandbox(fake_sandbox, workspace="/workspace", host_workspace=host_ws)

        dv = agent.available_tools.get_tool("data_visualization")
        assert isinstance(dv, DataVisualization)
        assert dv.sandbox is fake_sandbox
        assert dv.workspace_dir == "/workspace"
        assert dv._host_workspace_dir == host_ws

    def test_set_sandbox_injects_host_workspace_to_company_lookup(self, tmp_path):
        agent = DataAnalysis()
        host_ws = str(tmp_path / "host_ws")

        agent.set_sandbox(object(), workspace="/workspace", host_workspace=host_ws)

        cdl = agent.available_tools.get_tool("company_data_lookup")
        assert isinstance(cdl, CompanyDataLookup)
        assert cdl.host_workspace_dir == host_ws
