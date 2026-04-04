from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OpenClawWorkflowConfigUpdateRequest(BaseModel):
    # 每個 instance 在第一版都必須明確指定三個固定 stage 的 agent。
    instance_id: str
    search_agent_id: str
    analysis_agent_id: str
    report_agent_id: str


class OpenClawWorkflowConfigResponse(BaseModel):
    # 管理台需要直接拿到目前 mapping，才能在流程頁與管理頁共用。
    instance_id: str
    search_agent_id: str
    analysis_agent_id: str
    report_agent_id: str
    created_at: datetime
    updated_at: datetime
