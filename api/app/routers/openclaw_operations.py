from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response


router = APIRouter(tags=["openclaw"])

operation_log_repository = OpenClawOperationLogRepository()


@router.get("/openclaw/operations", response_model=OpenClawApiResponse)
def list_openclaw_operations(
    limit: int = Query(default=20, ge=1, le=100),
    instance_id: Optional[str] = Query(default=None, alias="instanceId"),
):
    # Overview 頁需要最近操作紀錄，因此額外暴露本專案自己的審計清單。
    try:
        return build_openclaw_success_response(
            operation_log_repository.list_recent(limit=limit, instance_id=instance_id),
            instance_id=instance_id,
            source_mode="repository",
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)
