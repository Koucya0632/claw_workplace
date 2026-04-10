from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


DevelopmentDeliveryChannel = Literal["discord"]
DevelopmentConfigSource = Literal["stored", "default"]
DevelopmentEffectiveDeliverySource = Literal["development_config", "runtime_route", "none"]


class OpenClawDevelopmentConfigRequest(BaseModel):
    instance_id: str
    enabled: bool = False
    delivery_channel: DevelopmentDeliveryChannel = "discord"
    discord_channel_id: str = ""


class OpenClawDevelopmentConfigResponse(OpenClawDevelopmentConfigRequest):
    last_run_id: Optional[str] = None
    last_delivery_status: Optional[str] = None
    last_delivery_error: Optional[str] = None
    config_source: DevelopmentConfigSource = "stored"
    effective_delivery_source: DevelopmentEffectiveDeliverySource = "none"
    effective_discord_channel_id: Optional[str] = None
    effective_delivery_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
