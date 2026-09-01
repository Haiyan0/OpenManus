import asyncio

import pytest

from app.web.agent_runner import create_observable_agent
from app.web.chat.models import AGENT_TYPES


def test_agent_types_include_geo_content():
    assert "geo_content" in AGENT_TYPES


@pytest.mark.asyncio
async def test_create_observable_geo_content_agent(tmp_path):
    queue = asyncio.Queue()
    host_workspace = tmp_path / "chat_workspace"

    agent = await create_observable_agent(
        "geo_content",
        queue,
        sandbox=object(),
        host_workspace=str(host_workspace),
    )

    assert agent.name == "geo_content"
    assert agent.event_queue is queue
    tool = agent.available_tools.get_tool("geo_content")
    assert tool.workspace_dir == "/workspace"
    assert tool.host_workspace_dir == str(host_workspace)

    result = await tool.execute(action="save_state", content="factory-injected-state")

    assert result.output["path"] == str(host_workspace / "_working-data.md")
    assert (host_workspace / "_working-data.md").read_text(
        encoding="utf-8"
    ) == "factory-injected-state"
