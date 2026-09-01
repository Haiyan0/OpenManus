import asyncio

import pytest

from app.web.agent_runner import create_observable_agent
from app.web.chat.models import AGENT_TYPES


def test_agent_types_include_geo_content():
    assert "geo_content" in AGENT_TYPES


@pytest.mark.asyncio
async def test_create_observable_geo_content_agent():
    queue = asyncio.Queue()

    agent = await create_observable_agent("geo_content", queue)

    assert agent.name == "geo_content"
    assert agent.event_queue is queue
    assert agent.available_tools.get_tool("geo_content") is not None
