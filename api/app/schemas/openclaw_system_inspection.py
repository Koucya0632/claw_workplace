from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

DeliveryChannel = Literal["telegram", "discord"]


class OpenClawSystemInspectionConfigRequest(BaseModel):
    instance_id: str
    enabled: bool = False
    schedule_timezone: str = "Asia/Tokyo"
    schedule_time: str = "09:30"
    delivery_channel: DeliveryChannel = "telegram"
    telegram_target: str = ""
    discord_channel_id: str = ""
    version_check_enabled: bool = True
    log_review_enabled: bool = True
    log_review_window_hours: int = Field(default=24, ge=1, le=168)
    log_review_limit: int = Field(default=500, ge=50, le=5000)
    official_release_url: str = "https://docs.openclaw.ai/cli/agents"


class OpenClawSystemInspectionConfigResponse(OpenClawSystemInspectionConfigRequest):
    last_scheduled_date: Optional[str] = None
    last_run_id: Optional[str] = None
    last_delivery_status: Optional[str] = None
    last_delivery_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
