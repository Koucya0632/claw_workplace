from __future__ import annotations

from pathlib import Path

from app.connectors.base import BaseConnector
from app.schemas.source import SourceConfig


class GoogleDriveConnector(BaseConnector):
    # Google Drive Phase 1 只保留接口，避免未來接入時重改 service 入口。
    source_type = "google_drive"

    def validate_config(self, config: SourceConfig) -> None:
        raise NotImplementedError("Google Drive connector 將在 Phase 2 啟用。")

    def scan_documents(self, config: SourceConfig) -> list[Path]:
        raise NotImplementedError("Google Drive connector 將在 Phase 2 啟用。")

    def fetch_content(self, path: Path) -> bytes:
        raise NotImplementedError("Google Drive connector 將在 Phase 2 啟用。")

