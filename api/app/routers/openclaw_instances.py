from __future__ import annotations

from fastapi import APIRouter, status

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.schemas.openclaw_instance import OpenClawInstanceCreateRequest, OpenClawInstanceUpdateRequest
from app.services.openclaw_service import OpenClawInstanceService


router = APIRouter(tags=["openclaw"])

instance_service = OpenClawInstanceService()


@router.get("/openclaw/instances", response_model=OpenClawApiResponse)
def list_openclaw_instances() -> dict:
    # Instances 清單是所有 OpenClaw 管理頁的共同入口，因此先回傳本專案保存的快照資料。
    try:
        return build_openclaw_success_response(
            instance_service.list_instances(),
            source_mode="repository",
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error)


@router.post("/openclaw/instances", response_model=OpenClawApiResponse, status_code=status.HTTP_201_CREATED)
def create_openclaw_instance(payload: OpenClawInstanceCreateRequest):
    try:
        instance = instance_service.create_instance(payload)
        return build_openclaw_success_response(instance, instance_id=instance.id, source_mode="repository")
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error)


@router.patch("/openclaw/instances/{instance_id}", response_model=OpenClawApiResponse)
def update_openclaw_instance(instance_id: str, payload: OpenClawInstanceUpdateRequest):
    try:
        instance = instance_service.update_instance(instance_id, payload)
        return build_openclaw_success_response(instance, instance_id=instance_id, source_mode="repository")
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)


@router.get("/openclaw/instances/{instance_id}/health", response_model=OpenClawApiResponse)
def get_openclaw_instance_health(instance_id: str):
    try:
        health, duration_ms = instance_service.check_health(instance_id)
        return build_openclaw_success_response(
            health,
            instance_id=instance_id,
            source_mode=instance_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)
