from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_agent import OpenClawAgentCreateRequest
from app.schemas.openclaw_agent_capability import OpenClawAgentCapabilityUpsertRequest
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.services.openclaw_agent_capability_service import OpenClawAgentCapabilityService
from app.services.openclaw_service import OpenClawManagementService


router = APIRouter(tags=["openclaw"])

management_service = OpenClawManagementService()
capability_service = OpenClawAgentCapabilityService()


@router.get("/openclaw/agents", response_model=OpenClawApiResponse)
def list_openclaw_agents(instance_id: str = Query(..., alias="instanceId")):
    try:
        agents, duration_ms = management_service.list_agents(instance_id)
        return build_openclaw_success_response(
            agents,
            instance_id=instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)


@router.post("/openclaw/agents", response_model=OpenClawApiResponse, status_code=status.HTTP_201_CREATED)
def create_openclaw_agent(payload: OpenClawAgentCreateRequest):
    try:
        agent, duration_ms = management_service.create_agent(payload)
        return build_openclaw_success_response(
            agent,
            instance_id=payload.instance_id,
            source_mode=management_service.cli_adapter.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)


@router.get("/openclaw/agents/{agent_id}/capabilities", response_model=OpenClawApiResponse)
def list_openclaw_agent_capabilities(agent_id: str, instance_id: str = Query(..., alias="instanceId")):
    try:
        records, duration_ms = capability_service.list_capabilities(instance_id, agent_id)
        return build_openclaw_success_response(
            records,
            instance_id=instance_id,
            source_mode=capability_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=instance_id)


@router.post("/openclaw/agents/{agent_id}/capabilities/search", response_model=OpenClawApiResponse)
def configure_openclaw_agent_search_capability(agent_id: str, payload: OpenClawAgentCapabilityUpsertRequest):
    try:
        response, duration_ms = capability_service.set_search_capability(agent_id, payload)
        return build_openclaw_success_response(
            response,
            instance_id=payload.instance_id,
            source_mode=capability_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)
