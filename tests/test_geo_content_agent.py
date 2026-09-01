from app.agent.geo_content import GeoContent


def test_geo_content_agent_has_expected_tools():
    agent = GeoContent()

    assert agent.name == "geo_content"
    assert agent.available_tools.get_tool("geo_content") is not None
    assert agent.available_tools.get_tool("ask_human") is not None
    assert agent.available_tools.get_tool("terminate") is not None


def test_geo_content_set_sandbox_updates_tool_workspace():
    agent = GeoContent()
    fake_sandbox = object()

    agent.set_sandbox(
        fake_sandbox, workspace="/workspace", host_workspace="C:/tmp/chat"
    )

    tool = agent.available_tools.get_tool("geo_content")
    assert agent.sandbox is fake_sandbox
    assert tool.workspace_dir == "/workspace"
    assert "/workspace" in agent.system_prompt
