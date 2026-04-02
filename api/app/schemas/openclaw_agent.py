from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenClawAgentSummary(BaseModel):
    id: str
    name: str
    status: str = "unknown"
    channel_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenClawAgentCreateRequest(BaseModel):
    instance_id: str
    name: str
    prompt: Optional[str] = None
    role_hint: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
