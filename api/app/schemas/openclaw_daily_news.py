from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

DeliveryChannel = Literal["telegram", "discord"]


class OpenClawDailyNewsConfigRequest(BaseModel):
    instance_id: str
    enabled: bool = True
    brief_name: str = "Daily News Brief"
    topic: str = ""
    keywords: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    source_domains: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_exclude: list[str] = Field(default_factory=list)
    focus_points: list[str] = Field(default_factory=list)
    output_format: Literal["summary", "bullets", "table", "comparison"] = "summary"
    delivery_channel: DeliveryChannel = "telegram"
    telegram_target: str = ""
    discord_channel_id: str = ""
    schedule_timezone: str = "Asia/Tokyo"
    schedule_time: str = "09:00"


class OpenClawDailyNewsConfigResponse(OpenClawDailyNewsConfigRequest):
    last_scheduled_date: Optional[str] = None
    last_run_id: Optional[str] = None
    last_delivery_status: Optional[str] = None
    last_delivery_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
