from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApiMessage(BaseModel):
    # 簡單訊息模型用在健康檢查與操作成功回應。
    message: str


class RoleStatusEvent(BaseModel):
    # 角色狀態事件會用在任務時間線與前端像素流程欄。
    id: str
    role_name: str
    role_status: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
