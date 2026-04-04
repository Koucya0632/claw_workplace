from __future__ import annotations

from fastapi import APIRouter

from app.routers.openclaw_router_utils import openclaw_error_response
from app.schemas.openclaw_agent_tool import OpenClawAgentToolDocumentRequest, OpenClawAgentToolSearchRequest
from app.schemas.openclaw_common import OpenClawApiResponse, build_openclaw_success_response
from app.services.openclaw_agent_tool_service import OpenClawAgentToolService


router = APIRouter(tags=["openclaw"])

agent_tool_service = OpenClawAgentToolService()


@router.post("/openclaw/agent-tools/search", response_model=OpenClawApiResponse)
def openclaw_agent_search(payload: OpenClawAgentToolSearchRequest):
    try:
        response, duration_ms, instance_id = agent_tool_service.search(payload)
        return build_openclaw_success_response(
            response,
            instance_id=instance_id,
            source_mode=agent_tool_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)


@router.post("/openclaw/agent-tools/document", response_model=OpenClawApiResponse)
def openclaw_agent_document(payload: OpenClawAgentToolDocumentRequest):
    try:
        response, duration_ms, instance_id = agent_tool_service.get_document(payload)
        return build_openclaw_success_response(
            response,
            instance_id=instance_id,
            source_mode=agent_tool_service.source_mode,
            duration_ms=duration_ms,
        )
    except Exception as error:  # noqa: BLE001
        return openclaw_error_response(error, instance_id=payload.instance_id)
