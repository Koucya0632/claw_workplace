from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.connectors.base import BaseConnector
from app.schemas.source import SourceConfig


class LocalFolderConnector(BaseConnector):
    # LocalFolderConnector 是 Phase 1 唯一真正可用的 connector。
    source_type = "local"

    def validate_config(self, config: SourceConfig) -> None:
        # 本地資料夾一定要提供 path，否則無法建立索引來源。
        if not config.path:
            raise ValueError("本地資料源必須提供 path。")

        requested_path = Path(config.path).expanduser().resolve()
        allowed_root = get_settings().source_root

        # 只允許掃描根目錄之內，避免使用者把整個家目錄或系統目錄接進來。
        if allowed_root not in requested_path.parents and requested_path != allowed_root:
            raise ValueError(f"本地資料夾必須位於允許根路徑內：{allowed_root}")

        # 路徑不存在時直接阻擋，前端才能即時顯示錯誤提示。
        if not requested_path.exists():
            raise FileNotFoundError(f"找不到資料夾：{requested_path}")

        # 只有目錄才可以作為 Phase 1 的本地來源。
        if not requested_path.is_dir():
            raise ValueError("本地資料源 path 必須是資料夾。")

    def scan_documents(self, config: SourceConfig) -> list[Path]:
        # 先重用驗證邏輯，確保掃描前的安全與存在性已被確認。
        self.validate_config(config)

        base_path = Path(config.path).expanduser().resolve()
        allowed_extensions = {f".{item}" for item in get_settings().allowed_extension_list}
        discovered_files: list[Path] = []

        # 以遞迴方式找出所有候選文件，並用副檔名做第一層篩選。
        for file_path in sorted(base_path.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in allowed_extensions:
                discovered_files.append(file_path)

        return discovered_files

    def fetch_content(self, path: Path) -> bytes:
        # 本地來源直接讀取 bytes 即可，讓 parser 自行決定如何解碼。
        return path.read_bytes()

