from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.schemas.openclaw_development import OpenClawDevelopmentConfigRequest
from app.services.workflow_service import OpenClawDevelopmentConfigService


router = APIRouter(tags=["openclaw"])

development_service = OpenClawDevelopmentConfigService()


@router.get("/openclaw/development-config", response_model=OpenClawApiResponse)
def get_openclaw_development_config(instance_id: str = Query(..., alias="instanceId")):
    try:
        config, duration_ms = development_service.get_config(instance_id)
        return build_openclaw_success_response(
            config,
            instance_id=instance_id,
            source_mode=development_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)


@router.post("/openclaw/development-config", response_model=OpenClawApiResponse)
def update_openclaw_development_config(payload: OpenClawDevelopmentConfigRequest):
    try:
        config, duration_ms = development_service.update_config(payload)
        return build_openclaw_success_response(
            config,
            instance_id=payload.instance_id,
            source_mode=development_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)
