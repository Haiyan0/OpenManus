"""DataVisualization 路径转换单元测试。

背景：sandbox 模式下 Node（npx ts-node）在宿主机写 chart，
返回的 chart_path 是宿主机绝对路径（如 C:\\data\\...\\visualization\\chart.html）。
LLM 后续用容器内 python_execute 读该路径会 FileNotFoundError——
容器内正确路径是 /workspace/visualization/...（bind mount 映射）。
返回给 LLM 前必须转换。
"""
import asyncio

from app.tool.chart_visualization.data_visualization import DataVisualization

HOST_WS = "C:\\data\\users\\1\\workspace\\2"


def _sandbox_tool() -> DataVisualization:
    """构造已注入 sandbox 的工具实例（宿主挂载源 → 容器 /workspace）。"""
    tool = DataVisualization()
    tool.sandbox = object()  # 非 None 即视为 sandbox 已注入
    tool.workspace_dir = "/workspace"
    tool._host_workspace_dir = HOST_WS
    return tool


class TestChartPathConversion:
    """sandbox 模式下返回给 LLM 的 chart 路径必须转换为容器内路径。"""

    def test_success_output_template_maps_host_path_to_container(self):
        """宿主 chart_path 应输出为 /workspace/visualization/... 容器路径。"""
        tool = _sandbox_tool()
        host_chart = f"{HOST_WS}\\visualization\\chart_a.html"
        out = tool.success_output_template(
            [{"title": "销售趋势", "chart_path": host_chart}]
        )
        assert "/workspace/visualization/chart_a.html" in out
        assert "C:\\data" not in out

    def test_add_insights_output_maps_host_path_to_container(self, monkeypatch):
        """insight 流程输出的 chartPath 同样应转换为容器路径。"""
        tool = _sandbox_tool()
        host_chart = f"{HOST_WS}\\visualization\\chart_a.html"

        async def _fake_invoke_vmind(self, **kwargs):
            # 返回含 chart_path 键即视为成功分支
            return {"chart_path": "ignored"}

        monkeypatch.setattr(DataVisualization, "invoke_vmind", _fake_invoke_vmind)

        out = asyncio.run(
            tool.add_insighs([{"chartPath": host_chart, "insights_id": [1]}], "html")
        )
        assert "/workspace/visualization/chart_a.html" in out["observation"]
        assert "C:\\data" not in out["observation"]


class TestChartPathPassthrough:
    """无 sandbox 时 chart_path 原样输出（本地模式行为不变）。"""

    def test_success_output_template_passthrough_without_sandbox(self):
        tool = DataVisualization()
        tool.sandbox = None
        host_chart = f"{HOST_WS}\\visualization\\chart_a.html"
        out = tool.success_output_template(
            [{"title": "销售趋势", "chart_path": host_chart}]
        )
        assert HOST_WS in out
