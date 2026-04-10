from __future__ import annotations

import time
from typing import Any, Optional, Tuple

# 取得設定檔
from app.config import get_settings
# OpenClaw Agent 能力相關的 repository
from app.repositories.openclaw_agent_capability_repository import OpenClawAgentCapabilityRepository
# OpenClaw Instance 相關的資料存取
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
# 操作日誌相關的 repository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
# Agent 的 schema 定義
from app.schemas.openclaw_agent import OpenClawAgentCreateRequest, OpenClawAgentSummary
# 設定檔相關的 schema 定義
from app.schemas.openclaw_config import (
    OpenClawConfigResponse,
    OpenClawConfigSetRequest,
    OpenClawConfigValidateRequest,
    OpenClawConfigValidationResponse,
)
# 設備摘要資料的 schema
from app.schemas.openclaw_device import OpenClawDeviceSummary
# Instance 的 schema 定義
from app.schemas.openclaw_instance import (
    OpenClawHealthResponse,
    OpenClawInstanceCreateRequest,
    OpenClawInstanceResponse,
    OpenClawInstanceUpdateRequest,
)
# LogEntry 的 schema
from app.schemas.openclaw_log import OpenClawLogEntry
# CLI 適配器，用於與 OpenClaw 互動
from app.services.openclaw_cli_adapter import OpenClawCliAdapter
from app.services.openclaw_cron_service import OpenClawCronSchedulingService, summarize_cron_reconcile_error
# 服務端可能會遇到的錯誤型別
from app.services.openclaw_errors import OpenClawServiceError
# 機敏資訊加解密的工具
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
# 工具函式，用於截斷文字
from app.utils import truncate_text

class OpenClawInstanceService:
    # 負責管理 OpenClaw 實例的生命週期及健康狀態
    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
        cron_scheduling_service: Optional[OpenClawCronSchedulingService] = None,
    ) -> None:
        # 初始化設定
        settings = get_settings()
        # 初始化各 repository 及工具
        self.repository = repository or OpenClawInstanceRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)
        self.cron_scheduling_service = cron_scheduling_service or OpenClawCronSchedulingService(
            repository=self.repository,
            operation_log_repository=self.operation_log_repository,
            cli_adapter=self.cli_adapter,
            secret_cipher=self.secret_cipher,
        )

    def list_instances(self) -> list[OpenClawInstanceResponse]:
        # 列出所有 OpenClaw instances
        return self.repository.list_all()

    def create_instance(self, payload: OpenClawInstanceCreateRequest) -> OpenClawInstanceResponse:
        # 創建新 instance
        instance = self.repository.create(payload)

        # 儲存 token（如有）
        if payload.token:
            self._save_token(instance.id, payload.token)
            instance = self.repository.get(instance.id)

        # 建立操作日誌
        self.operation_log_repository.create(
            instance_id=instance.id,
            operation_type="create_instance",
            target_type="instance",
            target_id=instance.id,
            status="success",
            error_message=None,
            request_summary={"name": payload.name, "gateway_url": payload.gateway_url, "has_token": bool(payload.token)},
            response_summary={"instance_id": instance.id},
            source_mode="repository",
        )
        try:
            self.cron_scheduling_service.reconcile_instance(instance.id)
        except Exception as error:  # noqa: BLE001
            self.operation_log_repository.create(
                instance_id=instance.id,
                operation_type="create_instance_cron_reconcile",
                target_type="instance",
                target_id=instance.id,
                status="failed",
                error_message=summarize_cron_reconcile_error(error),
                request_summary={"instance_id": instance.id},
                response_summary=None,
                source_mode="repository",
            )
        return instance

    def update_instance(self, instance_id: str, payload: OpenClawInstanceUpdateRequest) -> OpenClawInstanceResponse:
        # 更新 instance 內容
        if payload.clear_token:
            self.repository.clear_secret(instance_id)

        if payload.token:
            self._save_token(instance_id, payload.token)

        instance = self.repository.update(instance_id, payload)
        # 記錄操作日誌
        self.operation_log_repository.create(
            instance_id=instance.id,
            operation_type="update_instance",
            target_type="instance",
            target_id=instance.id,
            status="success",
            error_message=None,
            request_summary={
                "name": payload.name,
                "gateway_url": payload.gateway_url,
                "clear_token": payload.clear_token,
                "has_token_update": bool(payload.token),
                "is_active": payload.is_active,
            },
            response_summary={"instance_id": instance.id},
            source_mode="repository",
        )
        try:
            self.cron_scheduling_service.reconcile_instance(instance.id)
        except Exception as error:  # noqa: BLE001
            self.operation_log_repository.create(
                instance_id=instance.id,
                operation_type="update_instance_cron_reconcile",
                target_type="instance",
                target_id=instance.id,
                status="failed",
                error_message=summarize_cron_reconcile_error(error),
                request_summary={"instance_id": instance.id},
                response_summary=None,
                source_mode="repository",
            )
        return instance

    def check_health(self, instance_id: str) -> tuple[OpenClawHealthResponse, int]:
        # 健康檢查：呼叫 OpenClaw instance 的 health API
        instance = self.repository.get(instance_id)
        token = self._resolve_token(instance_id)
        started_at = time.perf_counter()

        try:
            # 向底層 CLI Adapter 發出健康檢查請求
            payload = self.cli_adapter.get_health(instance, token)
            status = str(payload.get("status") or "healthy")
            # 更新 instance 健康狀態
            updated_instance = self.repository.update_health_status(instance_id, status)
            checked_at = updated_instance.last_health_checked_at or updated_instance.updated_at
            response = OpenClawHealthResponse(status=status, checked_at=checked_at, details=payload)
            # Snapshot 快照記錄
            self.repository.upsert_snapshot(instance_id, "health", response.model_dump(mode="json"))
            # 記錄成功操作日誌
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="health_check",
                target_type="instance",
                target_id=instance_id,
                status="success",
                error_message=None,
                request_summary={"gateway_url": instance.gateway_url},
                response_summary={"status": response.status},
                source_mode=self.cli_adapter.source_mode,
            )
            return response, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            # 異常時更新健康狀態為失敗，並記錄操作日誌
            self.repository.update_health_status(instance_id, "failed")
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="health_check",
                target_type="instance",
                target_id=instance_id,
                status="failed",
                error_message=error.detail or error.message,
                request_summary={"gateway_url": instance.gateway_url},
                response_summary=None,
                source_mode=error.source_mode or self.cli_adapter.source_mode,
            )
            raise

    def _save_token(self, instance_id: str, token: str) -> None:
        # 儲存密鑰至加密存儲（若未設定密鑰則拒絕）
        if not self.secret_cipher.is_enabled:
            raise ValueError("尚未設定 OPENCLAW_SECRET_KEY，無法保存 Gateway token。")

        self.repository.save_secret(instance_id, self.secret_cipher.encrypt(token))

    def _resolve_token(self, instance_id: str) -> Optional[str]:
        # 解密 token，如無密鑰則回傳 None
        encrypted_token = self.repository.get_secret(instance_id)
        if encrypted_token is None:
            return None
        return self.secret_cipher.decrypt(encrypted_token)


class OpenClawManagementService:
    # 管理介面服務：主要操作 agents、devices、config、log 等管理性事項
    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        capability_repository: Optional[OpenClawAgentCapabilityRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
    ) -> None:
        # 取得設定及初始化所有必要 repository 和工具
        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.capability_repository = capability_repository or OpenClawAgentCapabilityRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)

    def list_agents(self, instance_id: str) -> tuple[list[OpenClawAgentSummary], int]:
        # 取得 agent 列表，並自動組合相關能力摘要
        started_at = time.perf_counter()
        instance, token = self._load_context(instance_id)
        try:
            # 組能力摘要表
            capability_map = _build_capability_summary_map(self.capability_repository.list_for_instance(instance_id=instance_id))
            # 從 CLI 取出所有 agent，組合 agent summary
            agents = [
                self._to_agent_summary(item, capability_summary=capability_map.get(str(item.get("id") or item.get("agent_id") or ""), {}))
                for item in self.cli_adapter.list_agents(instance, token)
            ]
            # 更新 snapshot 並記錄日誌
            self.repository.upsert_snapshot(instance_id, "agents", {"items": [agent.model_dump() for agent in agents]})
            self._log_success(
                instance_id=instance_id,
                operation_type="list_agents",
                target_type="agent",
                target_id=None,
                request_summary={"instance_id": instance_id},
                response_summary={"count": len(agents)},
            )
            return agents, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            # 記錄失敗操作
            self._log_failure(
                instance_id=instance_id,
                operation_type="list_agents",
                target_type="agent",
                target_id=None,
                request_summary={"instance_id": instance_id},
                error=error,
            )
            raise

    def create_agent(self, payload: OpenClawAgentCreateRequest) -> tuple[OpenClawAgentSummary, int]:
        # 創建 agent，回傳摘要及耗時
        started_at = time.perf_counter()
        instance, token = self._load_context(payload.instance_id)
        try:
            raw_agent = self.cli_adapter.create_agent(instance, token, payload.model_dump())
            agent = self._to_agent_summary(raw_agent)
            self._log_success(
                instance_id=payload.instance_id,
                operation_type="create_agent",
                target_type="agent",
                target_id=agent.id,
                request_summary={"name": payload.name, "role_hint": payload.role_hint},
                response_summary={"agent_id": agent.id, "status": agent.status},
            )
            return agent, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self._log_failure(
                instance_id=payload.instance_id,
                operation_type="create_agent",
                target_type="agent",
                target_id=None,
                request_summary={"name": payload.name, "role_hint": payload.role_hint},
                error=error,
            )
            raise

    def list_devices(self, instance_id: str) -> tuple[list[OpenClawDeviceSummary], int]:
        # 列舉所有設備摘要
        started_at = time.perf_counter()
        instance, token = self._load_context(instance_id)
        try:
            devices = [self._to_device_summary(item) for item in self.cli_adapter.list_devices(instance, token)]
            # 更新設備快照
            self.repository.upsert_snapshot(
                instance_id,
                "devices",
                {"items": [device.model_dump() for device in devices]},
            )
            self._log_success(
                instance_id=instance_id,
                operation_type="list_devices",
                target_type="device",
                target_id=None,
                request_summary={"instance_id": instance_id},
                response_summary={"count": len(devices)},
            )
            return devices, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self._log_failure(
                instance_id=instance_id,
                operation_type="list_devices",
                target_type="device",
                target_id=None,
                request_summary={"instance_id": instance_id},
                error=error,
            )
            raise

    def approve_device(self, instance_id: str, device_id: str) -> tuple[dict[str, Any], int]:
        # 同意設備加入
        return self._run_device_action(instance_id, device_id, "approve")

    def reject_device(self, instance_id: str, device_id: str) -> tuple[dict[str, Any], int]:
        # 拒絕設備加入
        return self._run_device_action(instance_id, device_id, "reject")

    def revoke_device(self, instance_id: str, device_id: str) -> tuple[dict[str, Any], int]:
        # 撤銷設備權限
        return self._run_device_action(instance_id, device_id, "revoke")

    def get_config(self, instance_id: str, path: str) -> tuple[OpenClawConfigResponse, int]:
        # 查詢組態設定
        started_at = time.perf_counter()
        instance, token = self._load_context(instance_id)
        try:
            payload = self.cli_adapter.get_config(instance, token, path)
            response = OpenClawConfigResponse(path=path, value=payload.get("value", payload))
            # 快照目前 config 狀態
            self.repository.upsert_snapshot(
                instance_id,
                "config_summary",
                {"last_path": path, "value_preview": truncate_text(str(response.value))},
            )
            self._log_success(
                instance_id=instance_id,
                operation_type="get_config",
                target_type="config",
                target_id=path,
                request_summary={"path": path},
                response_summary={"path": path},
            )
            return response, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self._log_failure(
                instance_id=instance_id,
                operation_type="get_config",
                target_type="config",
                target_id=path,
                request_summary={"path": path},
                error=error,
            )
            raise

    def set_config(self, payload: OpenClawConfigSetRequest) -> tuple[OpenClawConfigResponse, int]:
        # 設定組態
        started_at = time.perf_counter()
        instance, token = self._load_context(payload.instance_id)
        try:
            result = self.cli_adapter.set_config(instance, token, payload.path, payload.value)
            response = OpenClawConfigResponse(path=payload.path, value=result.get("value", payload.value))
            # 紀錄最新 config 設定快照
            self.repository.upsert_snapshot(
                payload.instance_id,
                "config_summary",
                {"last_path": payload.path, "value_preview": truncate_text(str(response.value))},
            )
            self._log_success(
                instance_id=payload.instance_id,
                operation_type="set_config",
                target_type="config",
                target_id=payload.path,
                request_summary={"path": payload.path},
                response_summary={"path": payload.path},
            )
            return response, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self._log_failure(
                instance_id=payload.instance_id,
                operation_type="set_config",
                target_type="config",
                target_id=payload.path,
                request_summary={"path": payload.path},
                error=error,
            )
            raise

    def validate_config(self, payload: OpenClawConfigValidateRequest) -> tuple[OpenClawConfigValidationResponse, int]:
        # 驗證組態正確性
        started_at = time.perf_counter()
        instance, token = self._load_context(payload.instance_id)
        try:
            result = self.cli_adapter.validate_config(instance, token, payload.path, payload.value)
            response = OpenClawConfigValidationResponse(
                valid=bool(result.get("valid", True)),
                messages=_coerce_messages(result),
            )
            self._log_success(
                instance_id=payload.instance_id,
                operation_type="validate_config",
                target_type="config",
                target_id=payload.path,
                request_summary={"path": payload.path},
                response_summary={"valid": response.valid},
            )
            return response, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self._log_failure(
                instance_id=payload.instance_id,
                operation_type="validate_config",
                target_type="config",
                target_id=payload.path,
                request_summary={"path": payload.path},
                error=error,
            )
            raise

    def get_logs(self, instance_id: str, limit: int) -> tuple[list[OpenClawLogEntry], int]:
        # 取得 OpenClaw instance log 清單
        started_at = time.perf_counter()
        instance, token = self._load_context(instance_id)
        try:
            entries = [self._to_log_entry(item) for item in self.cli_adapter.get_logs(instance, token, limit)]
            self._log_success(
                instance_id=instance_id,
                operation_type="get_logs",
                target_type="log",
                target_id=None,
                request_summary={"limit": limit},
                response_summary={"count": len(entries)},
            )
            return entries, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self._log_failure(
                instance_id=instance_id,
                operation_type="get_logs",
                target_type="log",
                target_id=None,
                request_summary={"limit": limit},
                error=error,
            )
            raise

    def _run_device_action(self, instance_id: str, device_id: str, action: str) -> tuple[dict[str, Any], int]:
        # 呼叫適配器動作，進行設備管理（approve/reject/revoke）
        started_at = time.perf_counter()
        instance, token = self._load_context(instance_id)
        adapter_method = getattr(self.cli_adapter, f"{action}_device")
        try:
            result = adapter_method(instance, token, device_id)
            self._log_success(
                instance_id=instance_id,
                operation_type=f"{action}_device",
                target_type="device",
                target_id=device_id,
                request_summary={"device_id": device_id},
                response_summary={"status": result.get("status", "ok")},
            )
            return result, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self._log_failure(
                instance_id=instance_id,
                operation_type=f"{action}_device",
                target_type="device",
                target_id=device_id,
                request_summary={"device_id": device_id},
                error=error,
            )
            raise

    def _load_context(self, instance_id: str) -> Tuple[OpenClawInstanceResponse, Optional[str]]:
        # 載入 instance 狀態以及解密 token
        instance = self.repository.get(instance_id)
        encrypted_token = self.repository.get_secret(instance_id)
        token = self.secret_cipher.decrypt(encrypted_token) if encrypted_token else None
        return instance, token

    def _log_success(
        self,
        *,
        instance_id: str,
        operation_type: str,
        target_type: str,
        target_id: Optional[str],
        request_summary: dict[str, Any],
        response_summary: dict[str, Any],
    ) -> None:
        # 記錄成功的操作日誌
        self.operation_log_repository.create(
            instance_id=instance_id,
            operation_type=operation_type,
            target_type=target_type,
            target_id=target_id,
            status="success",
            error_message=None,
            request_summary=request_summary,
            response_summary=response_summary,
            source_mode=self.cli_adapter.source_mode,
        )

    def _log_failure(
        self,
        *,
        instance_id: str,
        operation_type: str,
        target_type: str,
        target_id: Optional[str],
        request_summary: dict[str, Any],
        error: OpenClawServiceError,
    ) -> None:
        # 記錄失敗的操作日誌
        self.operation_log_repository.create(
            instance_id=instance_id,
            operation_type=operation_type,
            target_type=target_type,
            target_id=target_id,
            status="failed",
            error_message=error.detail or error.message,
            request_summary=request_summary,
            response_summary=None,
            source_mode=error.source_mode or self.cli_adapter.source_mode,
        )

    def _to_agent_summary(
        self,
        payload: dict[str, Any],
        *,
        capability_summary: Optional[dict[str, dict[str, Any]]] = None,
    ) -> OpenClawAgentSummary:
        # 將 API 回應內容轉換為 agent 摘要
        bindings = payload.get("bindings")
        channel_count = len(bindings) if isinstance(bindings, list) else int(payload.get("channel_count", 0))
        # 擷取 metadata
        metadata = {
            key: value
            for key, value in payload.items()
            if key not in {"id", "agent_id", "name", "display_name", "status", "bindings", "channel_count"}
        }
        metadata["capabilities"] = capability_summary or {}
        return OpenClawAgentSummary(
            id=str(payload.get("id") or payload.get("agent_id") or ""),
            name=str(payload.get("name") or payload.get("display_name") or "Unnamed Agent"),
            status=str(payload.get("status") or "unknown"),
            channel_count=channel_count,
            metadata=metadata,
        )

    def _to_device_summary(self, payload: dict[str, Any]) -> OpenClawDeviceSummary:
        # 將設備 API 回傳轉成 device summary
        device_name = payload.get("name") or payload.get("label") or payload.get("clientId") or payload.get("deviceId")
        return OpenClawDeviceSummary(
            id=str(payload.get("id") or payload.get("device_id") or payload.get("deviceId") or ""),
            name=str(device_name or "Unknown Device"),
            status=str(payload.get("status") or "unknown"),
            platform=payload.get("platform"),
            pending_action=payload.get("pending_action"),
            metadata={
                key: value
                for key, value in payload.items()
                if key not in {"id", "device_id", "deviceId", "name", "label", "status", "platform", "pending_action"}
            },
        )

    def _to_log_entry(self, payload: dict[str, Any]) -> OpenClawLogEntry:
        # 將原始 log dict 轉為 LogEntry schema
        return OpenClawLogEntry(
            timestamp=payload.get("timestamp"),
            level=payload.get("level"),
            message=str(payload.get("message") or payload.get("raw") or ""),
            raw=payload.get("raw"),
        )


def _elapsed_ms(started_at: float) -> int:
    # 回傳自 started_at 到現在的經過毫秒數
    return int((time.perf_counter() - started_at) * 1000)


def _coerce_messages(payload: dict[str, Any]) -> list[str]:
    # 將 messages 欄位統一為 List[str]
    messages = payload.get("messages")
    if isinstance(messages, list):
        return [str(message) for message in messages]
    if "message" in payload:
        return [str(payload["message"])]
    return []


def _build_capability_summary_map(records: list[Any]) -> dict[str, dict[str, dict[str, Any]]]:
    # 將 agent capability 列表整理成可供查詢的 map
    summary: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        config = record.config if isinstance(record.config, dict) else {}
        native = config.get("_native_plugin") if isinstance(config.get("_native_plugin"), dict) else {}
        summary.setdefault(record.agent_id, {})[record.capability_key] = {
            "enabled": record.is_enabled,
            "config": {key: value for key, value in config.items() if key != "_native_plugin"},
            "plugin_id": native.get("plugin_id"),
            "plugin_ready": bool(native.get("plugin_ready")),
            "plugin_enabled": bool(native.get("plugin_enabled")),
            "bridge_ready": bool(native.get("bridge_ready")),
            "last_sync_status": native.get("last_sync_status"),
            "last_sync_message": native.get("last_sync_message"),
            "synced_at": native.get("synced_at"),
            "updated_at": record.updated_at.isoformat(),
        }
    return summary
