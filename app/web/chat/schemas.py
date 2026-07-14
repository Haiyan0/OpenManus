"""会话与消息的请求/响应模型。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    agent_type: str = Field(..., description="general | data_analysis")
    title: str | None = Field(None, max_length=200)


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    agent_type: str
    sandbox_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: str
    content: str | None
    tool_name: str | None
    tool_args: dict[str, Any] | None
    event_type: str | None
    extra_data: dict[str, Any] | None
    created_at: datetime


class ChatDetail(ChatOut):
    messages: list[MessageOut] = []
