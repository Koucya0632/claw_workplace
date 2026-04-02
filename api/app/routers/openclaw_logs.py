from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.services.openclaw_service import OpenClawManagementService


router = APIRouter(tags=["openclaw"])

management_service = OpenClawManagementService()


@router.get("/openclaw/logs", response_model=OpenClawApiResponse)
def get_openclaw_logs(
    instance_id: str = Query(..., alias="instanceId"),
    limit: int = Query(default=200, ge=1, le=500),
):
    try:
        entries, duration_ms = management_service.get_logs(instance_id, limit)
        return build_openclaw_success_response(
            entries,
            instance_id=instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)
