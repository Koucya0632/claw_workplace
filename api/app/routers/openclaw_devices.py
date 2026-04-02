from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.schemas.openclaw_device import OpenClawDeviceActionRequest
from app.services.openclaw_service import OpenClawManagementService


router = APIRouter(tags=["openclaw"])

management_service = OpenClawManagementService()


@router.get("/openclaw/devices", response_model=OpenClawApiResponse)
def list_openclaw_devices(instance_id: str = Query(..., alias="instanceId")):
    try:
        devices, duration_ms = management_service.list_devices(instance_id)
        return build_openclaw_success_response(
            devices,
            instance_id=instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)


@router.post("/openclaw/devices/{device_id}/approve", response_model=OpenClawApiResponse)
def approve_openclaw_device(device_id: str, payload: OpenClawDeviceActionRequest):
    return _run_device_action("approve", device_id, payload.instance_id)


@router.post("/openclaw/devices/{device_id}/reject", response_model=OpenClawApiResponse)
def reject_openclaw_device(device_id: str, payload: OpenClawDeviceActionRequest):
    return _run_device_action("reject", device_id, payload.instance_id)


@router.post("/openclaw/devices/{device_id}/revoke", response_model=OpenClawApiResponse)
def revoke_openclaw_device(device_id: str, payload: OpenClawDeviceActionRequest):
    return _run_device_action("revoke", device_id, payload.instance_id)


def _run_device_action(action: str, device_id: str, instance_id: str):
    # 三種 device action 只差 CLI 方法名稱，因此共用這個小型分派器。
    try:
        service_method = getattr(management_service, f"{action}_device")
        result, duration_ms = service_method(instance_id, device_id)
        return build_openclaw_success_response(
            result,
            instance_id=instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)
