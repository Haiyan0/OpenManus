"""文件操作请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    chat_id: int | None
    filename: str
    file_size: int
    mime_type: str | None
    created_at: datetime
