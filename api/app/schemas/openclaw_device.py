from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenClawDeviceSummary(BaseModel):
    id: str
    name: str
    status: str = "unknown"
    platform: Optional[str] = None
    pending_action: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenClawDeviceActionRequest(BaseModel):
    # device id 在 path，但 instance_id 仍需由 body 指定到正確 Gateway。
    instance_id: str
