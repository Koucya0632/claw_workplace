from __future__ import annotations

from app.connectors.base import BaseConnector
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.local_folder import LocalFolderConnector
from app.connectors.notion import NotionConnector


class ConnectorRegistry:
    # ConnectorRegistry 集中管理各資料源對應實作，service 就不需要知道具體類別。
    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {
            "local": LocalFolderConnector(),
            "google_drive": GoogleDriveConnector(),
            "notion": NotionConnector(),
        }

    def get(self, source_type: str) -> BaseConnector:
        connector = self._connectors.get(source_type)
        if connector is None:
            raise KeyError(f"不支援的資料源型別：{source_type}")
        return connector

