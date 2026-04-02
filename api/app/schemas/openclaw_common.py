from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenClawApiError(BaseModel):
    # 管理 API 的錯誤物件會保留簡短訊息與可診斷細節。
    message: str
    detail: Optional[str] = None


class OpenClawApiMeta(BaseModel):
    # 這裡沿用方案中的 camelCase，讓前端直接對齊 envelope 規格。
    instanceId: Optional[str] = None
    sourceMode: Optional[str] = None
    durationMs: Optional[int] = None


class OpenClawApiResponse(BaseModel):
    # OpenClaw 專屬 API 全部走統一 envelope，避免前端每支 API 各自解讀格式。
    success: bool
    data: Any = None
    error: Optional[OpenClawApiError] = None
    meta: OpenClawApiMeta = Field(default_factory=OpenClawApiMeta)


class OpenClawOperationLogRecord(BaseModel):
    id: str
    instance_id: Optional[str] = None
    operation_type: str
    target_type: str
    target_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    request_summary: dict[str, Any] = Field(default_factory=dict)
    response_summary: Optional[dict[str, Any]] = None
    source_mode: str
    created_at: datetime


def build_openclaw_success_response(
    data: Any,
    *,
    instance_id: Optional[str] = None,
    source_mode: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> dict[str, Any]:
    # router 直接回 dict，讓 FastAPI 與 JSONResponse 都能共用同一個序列化出口。
    return OpenClawApiResponse(
        success=True,
        data=data,
        meta=OpenClawApiMeta(instanceId=instance_id, sourceMode=source_mode, durationMs=duration_ms),
    ).model_dump(mode="json")


def build_openclaw_error_response(
    message: str,
    *,
    detail: Optional[str] = None,
    instance_id: Optional[str] = None,
    source_mode: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> dict[str, Any]:
    return OpenClawApiResponse(
        success=False,
        data=None,
        error=OpenClawApiError(message=message, detail=detail),
        meta=OpenClawApiMeta(instanceId=instance_id, sourceMode=source_mode, durationMs=duration_ms),
    ).model_dump(mode="json")
