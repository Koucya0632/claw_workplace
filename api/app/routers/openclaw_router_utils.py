from __future__ import annotations

from typing import Optional

from fastapi.responses import JSONResponse

from app.schemas.openclaw_common import build_openclaw_error_response
from app.services.openclaw_errors import OpenClawServiceError


def openclaw_error_response(
    error: Exception,
    *,
    instance_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> JSONResponse:
    # 這裡把不同類型的例外統一轉成 envelope，讓各 router 不必重複寫樣板。
    if isinstance(error, KeyError):
        message = str(error)
        detail = None
        status_code = 404
        source_mode = None
    elif isinstance(error, ValueError):
        message = str(error)
        detail = None
        status_code = 400
        source_mode = None
    elif isinstance(error, OpenClawServiceError):
        message = error.message
        detail = error.detail
        status_code = error.status_code
        source_mode = error.source_mode
    else:
        message = "OpenClaw API 發生未預期錯誤。"
        detail = str(error)
        status_code = 500
        source_mode = None

    return JSONResponse(
        status_code=status_code,
        content=build_openclaw_error_response(
            message,
            detail=detail,
            instance_id=instance_id,
            source_mode=source_mode,
            duration_ms=duration_ms,
        ),
    )
