from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenClawAgentCapabilityRecord(BaseModel):
    id: str
    instance_id: str
    agent_id: str
    capability_key: str
    is_enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class OpenClawAgentCapabilityUpsertRequest(BaseModel):
    instance_id: str
    enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)


class OpenClawAgentCapabilityResponse(BaseModel):
    id: str
    instance_id: str
    agent_id: str
    capability_key: str
    is_enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)
    native_plugin_id: Optional[str] = None
    native_plugin_ready: bool = False
    native_plugin_enabled: bool = False
    bridge_ready: bool = False
    last_sync_status: Optional[str] = None
    last_sync_message: Optional[str] = None
    workspace_synced: bool = False
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
