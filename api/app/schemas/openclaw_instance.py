from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OpenClawInstanceSnapshotSummary(BaseModel):
    # Overview 頁會用這組摘要數據快速顯示各實例近期狀態。
    health_status: Optional[str] = None
    agent_count: int = 0
    device_count: int = 0
    config_updated_at: Optional[datetime] = None


class OpenClawInstanceCreateRequest(BaseModel):
    # Phase 1 只支援 Gateway URL + Token，不擴充其他 auth mode。
    name: str
    gateway_url: str
    token: Optional[str] = None
    is_active: bool = True


class OpenClawInstanceUpdateRequest(BaseModel):
    name: Optional[str] = None
    gateway_url: Optional[str] = None
    token: Optional[str] = None
    clear_token: bool = False
    is_active: Optional[bool] = None


class OpenClawInstanceResponse(BaseModel):
    id: str
    name: str
    gateway_url: str
    is_active: bool
    has_token: bool
    last_health_status: Optional[str] = None
    last_health_checked_at: Optional[datetime] = None
    snapshot_summary: OpenClawInstanceSnapshotSummary = Field(default_factory=OpenClawInstanceSnapshotSummary)
    created_at: datetime
    updated_at: datetime


class OpenClawHealthResponse(BaseModel):
    status: str
    checked_at: datetime
    details: dict = Field(default_factory=dict)
