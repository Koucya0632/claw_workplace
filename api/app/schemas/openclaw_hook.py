from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenClawAgentHookRequest(BaseModel):
    instance_id: str
    agent_id: str
    session_key: str
    message: str
    deliver: bool = True
    channel: Optional[str] = None
    to: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenClawWakeHookRequest(BaseModel):
    instance_id: str
    agent_id: str
    session_key: str
    deliver: bool = True
    channel: Optional[str] = None
    to: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
