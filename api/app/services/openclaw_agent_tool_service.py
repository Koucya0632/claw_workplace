from __future__ import annotations

import time
from typing import Optional

from app.config import get_settings
from app.repositories.document_repository import DocumentRepository
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.schemas.openclaw_agent_tool import (
    OpenClawAgentToolDocumentPayload,
    OpenClawAgentToolDocumentRequest,
    OpenClawAgentToolDocumentResponse,
    OpenClawAgentToolSearchItem,
    OpenClawAgentToolSearchRequest,
    OpenClawAgentToolSearchResponse,
)
from app.schemas.search import SearchRequest
from app.services.openclaw_agent_capability_service import OpenClawAgentCapabilityService
from app.services.openclaw_errors import OpenClawServiceError
from app.services.search_service import SearchService


class OpenClawAgentToolService:
    # Agent tool bridge 只服務 OpenClaw agent，不直接暴露前端專用資料格式。
    source_mode = "bridge"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        capability_service: Optional[OpenClawAgentCapabilityService] = None,
        search_service: Optional[SearchService] = None,
        document_repository: Optional[DocumentRepository] = None,
    ) -> None:
        self.repository = repository or OpenClawInstanceRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.capability_service = capability_service or OpenClawAgentCapabilityService(
            repository=self.repository,
            operation_log_repository=self.operation_log_repository,
        )
        self.search_service = search_service or SearchService()
        self.document_repository = document_repository or DocumentRepository()
        self.settings = get_settings()

    def search(self, payload: OpenClawAgentToolSearchRequest) -> tuple[OpenClawAgentToolSearchResponse, int, str]:
        started_at = time.perf_counter()
        request_summary = {
            "agent_id": payload.agent_id,
            "session_id": payload.session_id,
            "query": payload.query,
            "source_id": payload.source_id,
            "limit": payload.limit,
        }

        try:
            capability = self.capability_service.assert_search_enabled(agent_id=payload.agent_id, instance_id=payload.instance_id)
            effective_instance_id = capability.instance_id
            effective_source_id = payload.source_id or _read_capability_intent(capability.config, "source_id")
            effective_limit = payload.limit or _read_capability_intent(capability.config, "limit") or self.settings.openclaw_agent_search_default_limit

            response = self.search_service.search(
                SearchRequest(
                    query=payload.query,
                    source_id=effective_source_id if isinstance(effective_source_id, str) else None,
                    mode="all",
                )
            )
            items = [
                OpenClawAgentToolSearchItem(
                    document_id=item.document_id,
                    source_id=item.source_id,
                    source_name=item.source_name,
                    filename=item.filename,
                    relative_path=item.relative_path,
                    snippet=item.snippet,
                    matched_on=item.matched_on,
                    modified_at=item.modified_at,
                )
                for item in response.items[: int(effective_limit)]
            ]
            bridge_response = OpenClawAgentToolSearchResponse(
                query=payload.query,
                total=response.total,
                query_time_ms=response.query_time_ms,
                items=items,
            )
            self.operation_log_repository.create(
                instance_id=effective_instance_id,
                operation_type="agent_search",
                target_type="agent_tool",
                target_id=payload.agent_id,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary={"total": bridge_response.total, "returned_count": len(bridge_response.items)},
                source_mode=self.source_mode,
            )
            return bridge_response, _elapsed_ms(started_at), effective_instance_id
        except OpenClawServiceError as error:
            self._log_failure(payload.instance_id, payload.agent_id, "agent_search", request_summary, error)
            raise
        except Exception as error:  # noqa: BLE001
            wrapped = OpenClawServiceError(
                "Agent 搜索橋接失敗。",
                detail=str(error),
                source_mode=self.source_mode,
            )
            self._log_failure(payload.instance_id, payload.agent_id, "agent_search", request_summary, wrapped)
            raise wrapped from error

    def get_document(self, payload: OpenClawAgentToolDocumentRequest) -> tuple[OpenClawAgentToolDocumentResponse, int, str]:
        started_at = time.perf_counter()
        request_summary = {
            "agent_id": payload.agent_id,
            "session_id": payload.session_id,
            "document_id": payload.document_id,
            "max_chars": payload.max_chars,
        }

        try:
            capability = self.capability_service.assert_search_enabled(agent_id=payload.agent_id, instance_id=payload.instance_id)
            effective_instance_id = capability.instance_id
            effective_max_chars = payload.max_chars or _read_capability_intent(capability.config, "max_chars") or self.settings.openclaw_agent_document_max_chars

            document = self.document_repository.get_document(payload.document_id)
            extracted_text = document.extracted_text[: int(effective_max_chars)]
            truncated = len(document.extracted_text) > len(extracted_text)

            bridge_response = OpenClawAgentToolDocumentResponse(
                document=OpenClawAgentToolDocumentPayload(
                    id=document.id,
                    source_id=document.source_id,
                    filename=document.filename,
                    relative_path=document.relative_path,
                    extension=document.extension,
                    modified_at=document.modified_at,
                    extracted_text=extracted_text,
                ),
                truncated=truncated,
                returned_chars=len(extracted_text),
            )
            self.operation_log_repository.create(
                instance_id=effective_instance_id,
                operation_type="agent_get_document",
                target_type="agent_tool",
                target_id=payload.agent_id,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary={"document_id": payload.document_id, "returned_chars": bridge_response.returned_chars},
                source_mode=self.source_mode,
            )
            return bridge_response, _elapsed_ms(started_at), effective_instance_id
        except OpenClawServiceError as error:
            self._log_failure(payload.instance_id, payload.agent_id, "agent_get_document", request_summary, error)
            raise
        except KeyError as error:
            wrapped = OpenClawServiceError(
                "找不到指定文件。",
                detail=str(error),
                status_code=404,
                source_mode=self.source_mode,
            )
            self._log_failure(payload.instance_id, payload.agent_id, "agent_get_document", request_summary, wrapped)
            raise wrapped from error
        except Exception as error:  # noqa: BLE001
            wrapped = OpenClawServiceError(
                "Agent 文件讀取橋接失敗。",
                detail=str(error),
                source_mode=self.source_mode,
            )
            self._log_failure(payload.instance_id, payload.agent_id, "agent_get_document", request_summary, wrapped)
            raise wrapped from error

    def _log_failure(
        self,
        instance_id: Optional[str],
        agent_id: str,
        operation_type: str,
        request_summary: dict[str, object],
        error: OpenClawServiceError,
    ) -> None:
        self.operation_log_repository.create(
            instance_id=instance_id,
            operation_type=operation_type,
            target_type="agent_tool",
            target_id=agent_id,
            status="failed",
            error_message=error.detail or error.message,
            request_summary=request_summary,
            response_summary=None,
            source_mode=error.source_mode or self.source_mode,
        )


def _read_capability_intent(payload: dict[str, object], key: str) -> object | None:
    return payload.get(key)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)
