from __future__ import annotations

from fastapi import APIRouter

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.schemas.openclaw_hook import OpenClawAgentHookRequest, OpenClawWakeHookRequest
from app.services.openclaw_hook_service import OpenClawHookService


router = APIRouter(tags=["openclaw"])

hook_service = OpenClawHookService()


@router.post("/openclaw/hooks/agent", response_model=OpenClawApiResponse)
def dispatch_openclaw_agent_hook(payload: OpenClawAgentHookRequest):
    try:
        result, duration_ms = hook_service.dispatch_agent(payload)
        return build_openclaw_success_response(
            result,
            instance_id=payload.instance_id,
            source_mode=hook_service.hook_client.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)


@router.post("/openclaw/hooks/wake", response_model=OpenClawApiResponse)
def dispatch_openclaw_wake_hook(payload: OpenClawWakeHookRequest):
    try:
        result, duration_ms = hook_service.dispatch_wake(payload)
        return build_openclaw_success_response(
            result,
            instance_id=payload.instance_id,
            source_mode=hook_service.hook_client.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)
