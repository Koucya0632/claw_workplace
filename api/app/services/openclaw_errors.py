from __future__ import annotations

from typing import Optional


class OpenClawServiceError(Exception):
    # service 與 adapter 都用同一種錯誤型別，router 才能一致轉成 envelope。
    def __init__(
        self,
        message: str,
        *,
        detail: Optional[str] = None,
        status_code: int = 400,
        source_mode: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.status_code = status_code
        self.source_mode = source_mode
