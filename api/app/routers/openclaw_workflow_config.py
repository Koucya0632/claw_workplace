from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.schemas.openclaw_workflow_config import OpenClawWorkflowConfigUpdateRequest
from app.services.workflow_service import OpenClawWorkflowConfigService


router = APIRouter(tags=["openclaw"])

workflow_config_service = OpenClawWorkflowConfigService()


@router.get("/openclaw/workflow-config", response_model=OpenClawApiResponse)
def get_openclaw_workflow_config(instance_id: str = Query(..., alias="instanceId")):
    try:
        config, duration_ms = workflow_config_service.get_config(instance_id)
        return build_openclaw_success_response(
            config,
            instance_id=instance_id,
            source_mode=workflow_config_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)


@router.post("/openclaw/workflow-config", response_model=OpenClawApiResponse)
def update_openclaw_workflow_config(payload: OpenClawWorkflowConfigUpdateRequest):
    try:
        config, duration_ms = workflow_config_service.update_config(payload)
        return build_openclaw_success_response(
            config,
            instance_id=payload.instance_id,
            source_mode=workflow_config_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)
