from __future__ import annotations

import time
from typing import Any, Optional, Tuple

from app.config import get_settings
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.schemas.openclaw_hook import OpenClawAgentHookRequest, OpenClawWakeHookRequest
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_hook_client import OpenClawHookClient
from app.services.openclaw_secret_cipher import OpenClawSecretCipher


class OpenClawHookService:
    # Hook service 專門處理業務事件到 OpenClaw 的手動派發，不混進 CLI 管理流程。
    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        hook_client: Optional[OpenClawHookClient] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.hook_client = hook_client or OpenClawHookClient()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)

    def dispatch_agent(self, payload: OpenClawAgentHookRequest) -> tuple[dict[str, Any], int]:
        started_at = time.perf_counter()
        instance, token = self._load_context(payload.instance_id)
        request_summary = {
            "agent_id": payload.agent_id,
            "session_key": payload.session_key,
            "deliver": payload.deliver,
            "channel": payload.channel,
        }

        try:
            result = self.hook_client.dispatch_agent(instance, token, payload.model_dump(exclude={"instance_id"}))
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="dispatch_agent_hook",
                target_type="hook",
                target_id=payload.agent_id,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary=_summarize_hook_response(result),
                source_mode=self.hook_client.source_mode,
            )
            return result, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="dispatch_agent_hook",
                target_type="hook",
                target_id=payload.agent_id,
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or self.hook_client.source_mode,
            )
            raise

    def dispatch_wake(self, payload: OpenClawWakeHookRequest) -> tuple[dict[str, Any], int]:
        started_at = time.perf_counter()
        instance, token = self._load_context(payload.instance_id)
        request_summary = {
            "agent_id": payload.agent_id,
            "session_key": payload.session_key,
            "deliver": payload.deliver,
            "channel": payload.channel,
        }

        try:
            result = self.hook_client.dispatch_wake(instance, token, payload.model_dump(exclude={"instance_id"}))
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="dispatch_wake_hook",
                target_type="hook",
                target_id=payload.agent_id,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary=_summarize_hook_response(result),
                source_mode=self.hook_client.source_mode,
            )
            return result, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="dispatch_wake_hook",
                target_type="hook",
                target_id=payload.agent_id,
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or self.hook_client.source_mode,
            )
            raise

    def _load_context(self, instance_id: str) -> Tuple[Any, Optional[str]]:
        instance = self.repository.get(instance_id)
        encrypted_token = self.repository.get_secret(instance_id)
        token = self.secret_cipher.decrypt(encrypted_token) if encrypted_token else None
        return instance, token


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _summarize_hook_response(payload: dict[str, Any]) -> dict[str, Any]:
    # Agent 派發回應可能很大，審計只保留最關鍵的幾個欄位。
    return {
        "status": payload.get("status") or payload.get("result") or "ok",
        "task_id": payload.get("task_id"),
        "accepted": payload.get("accepted"),
        "session_id": payload.get("session_id"),
    }
