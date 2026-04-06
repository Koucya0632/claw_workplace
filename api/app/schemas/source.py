from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


SourceType = Literal["local", "google_drive", "notion", "web_page", "rss_feed", "url_list"]


class SourceConfig(BaseModel):
    # source 的細節設定統一收在 config，這樣不同 connector 才能保有彈性。
    path: Optional[str] = None
    url: Optional[str] = None
    urls: list[str] = Field(default_factory=list)
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


class SourceUpdateRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[SourceConfig] = None
    is_enabled: Optional[bool] = None


class SourceSyncResult(BaseModel):
    scanned_count: int = 0
    skipped_count: int = 0
    error_count: int = 0


class SourceSummaryResponse(BaseModel):
    id: str
    name: str
    type: SourceType
    status: str
    is_enabled: bool = True
    config: SourceConfig
    document_count: int = 0
    last_sync_status: str = "never_scanned"
    last_sync_error: Optional[str] = None
    last_successful_sync_at: Optional[datetime] = None
    last_failed_sync_at: Optional[datetime] = None
    last_sync_result: SourceSyncResult = Field(default_factory=SourceSyncResult)
    last_scan_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SourceSyncEventResponse(BaseModel):
    id: str
    source_id: str
    status: str
    message: str
    scanned_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    created_at: datetime


class SourceDetailResponse(SourceSummaryResponse):
    version_count: int = 0
    recent_activity: list[SourceSyncEventResponse] = Field(default_factory=list)


class SourceMetricsResponse(BaseModel):
    total_sources: int = 0
    healthy_sources: int = 0
    warning_sources: int = 0
    failed_sources: int = 0
    syncing_sources: int = 0
    disabled_sources: int = 0
    recently_updated_sources: int = 0
    recent_sync_failures: int = 0


class SourceResponse(SourceSummaryResponse):
    pass


class ScanSourceResponse(BaseModel):
    source_id: str
    scanned_count: int
    skipped_count: int
    errors: list[str] = Field(default_factory=list)
    scanned_at: datetime
