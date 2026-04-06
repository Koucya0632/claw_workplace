from __future__ import annotations

from pathlib import Path

from app.connectors.base import BaseConnector
from app.schemas.source import SourceConfig


class UrlListConnector(BaseConnector):
    source_type = "url_list"

    def validate_config(self, config: SourceConfig) -> None:
        urls = config.urls or config.extra.get("urls") or []
        if not urls:
            raise ValueError("url_list 資料源必須提供 urls。")

    def scan_documents(self, config: SourceConfig) -> list[Path]:
        raise NotImplementedError("url_list 資料源請透過 knowledge ingest / external refresh 流程處理。")

    def fetch_content(self, path: Path) -> bytes:
        raise NotImplementedError("url_list 資料源請透過 knowledge ingest / external refresh 流程處理。")

