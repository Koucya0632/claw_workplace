from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


SourceType = Literal["local", "google_drive", "notion"]


class SourceConfig(BaseModel):
    # source 的細節設定統一收在 config，這樣不同 connector 才能保有彈性。
    path: Optional[str] = None
    root_page_id: Optional[str] = None
    database_id: Optional[str] = None
    workspace_name: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SourceCreateRequest(BaseModel):
    # Phase 1 只開放 local，但 schema 仍保留多型別擴充能力。
    name: str
    type: SourceType = "local"
    config: SourceConfig
    role_hint: Optional[str] = "admin"


class SourceResponse(BaseModel):
    id: str
    name: str
    type: SourceType
    status: str
    config: SourceConfig
    last_scan_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ScanSourceResponse(BaseModel):
    source_id: str
    scanned_count: int
    skipped_count: int
    errors: list[str] = Field(default_factory=list)
    scanned_at: datetime
