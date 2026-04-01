from __future__ import annotations

from pathlib import Path

from app.connectors.base import BaseConnector
from app.schemas.source import SourceConfig


class NotionConnector(BaseConnector):
    # Notion Phase 1 同樣只留結構，不提供真實接入。
    source_type = "notion"

    def validate_config(self, config: SourceConfig) -> None:
        raise NotImplementedError("Notion connector 將在 Phase 2 啟用。")

    def scan_documents(self, config: SourceConfig) -> list[Path]:
        raise NotImplementedError("Notion connector 將在 Phase 2 啟用。")

    def fetch_content(self, path: Path) -> bytes:
        raise NotImplementedError("Notion connector 將在 Phase 2 啟用。")

