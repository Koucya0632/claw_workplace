from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.source import SourceConfig


class BaseConnector(ABC):
    # 每個 connector 都要宣告自己的資料源型別，方便 registry 做查找。
    source_type: str

    @abstractmethod
    def validate_config(self, config: SourceConfig) -> None:
        # validate_config 負責阻擋無效或危險設定，避免掃描階段才爆錯。
        raise NotImplementedError

    @abstractmethod
    def scan_documents(self, config: SourceConfig) -> list[Path]:
        # scan_documents 只負責找出候選檔案，不做解析與索引。
        raise NotImplementedError

    @abstractmethod
    def fetch_content(self, path: Path) -> bytes:
        # fetch_content 讓 parser 可以專注處理 byte payload，而不用在意來源細節。
        raise NotImplementedError

