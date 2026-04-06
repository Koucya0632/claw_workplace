from __future__ import annotations

from pathlib import Path

from app.connectors.base import BaseConnector
from app.schemas.source import SourceConfig


class RssFeedConnector(BaseConnector):
    source_type = "rss_feed"

    def validate_config(self, config: SourceConfig) -> None:
        if not config.url and not config.urls and not config.extra.get("urls"):
            raise ValueError("rss_feed 資料源必須提供 url 或 urls。")

    def scan_documents(self, config: SourceConfig) -> list[Path]:
        raise NotImplementedError("rss_feed connector 將在後續版本補齊正式 refresh 邏輯。")

    def fetch_content(self, path: Path) -> bytes:
        raise NotImplementedError("rss_feed connector 將在後續版本補齊正式 refresh 邏輯。")

