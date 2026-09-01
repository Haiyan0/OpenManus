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
    assert tool.host_workspace_dir == "C:/tmp/chat"
    assert "/workspace" in agent.system_prompt


def test_geo_content_prompt_requires_stage_knowledge_and_state_saves():
    prompt = GeoContent().system_prompt

    for topic in (
        "data_collection_fields",
        "style_analysis",
        "dimension_channel_matrix",
        "section_templates",
        "quality_checklist",
        "scoring_rubric",
        "deliverable_spec",
    ):
        assert topic in prompt
    assert "阶段变化" in prompt
    assert "素材实质更新" in prompt
    assert "大纲确认" in prompt
    assert "质量检查结果" in prompt
    assert 'action="save_state"' in prompt
