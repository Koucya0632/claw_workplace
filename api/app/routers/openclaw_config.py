from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.schemas.openclaw_config import OpenClawConfigSetRequest, OpenClawConfigValidateRequest
from app.services.openclaw_service import OpenClawManagementService


router = APIRouter(tags=["openclaw"])

management_service = OpenClawManagementService()


@router.get("/openclaw/config", response_model=OpenClawApiResponse)
def get_openclaw_config(
    instance_id: str = Query(..., alias="instanceId"),
    path: str = Query(...),
):
    try:
        config_value, duration_ms = management_service.get_config(instance_id, path)
        return build_openclaw_success_response(
            config_value,
            instance_id=instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)


@router.post("/openclaw/config/set", response_model=OpenClawApiResponse)
def set_openclaw_config(payload: OpenClawConfigSetRequest):
    try:
        config_value, duration_ms = management_service.set_config(payload)
        return build_openclaw_success_response(
            config_value,
            instance_id=payload.instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)


@router.post("/openclaw/config/validate", response_model=OpenClawApiResponse)
def validate_openclaw_config(payload: OpenClawConfigValidateRequest):
    try:
        validation_result, duration_ms = management_service.validate_config(payload)
        return build_openclaw_success_response(
            validation_result,
            instance_id=payload.instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)
