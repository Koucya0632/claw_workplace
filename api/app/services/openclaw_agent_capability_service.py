from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from app.config import REPO_ROOT, Settings, get_settings
from app.repositories.openclaw_agent_capability_repository import OpenClawAgentCapabilityRepository
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.schemas.openclaw_agent_capability import (
    OpenClawAgentCapabilityRecord,
    OpenClawAgentCapabilityResponse,
    OpenClawAgentCapabilityUpsertRequest,
)
from app.services.openclaw_cli_adapter import OpenClawCliAdapter
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.utils import truncate_text, utc_now_iso

SEARCH_API_CAPABILITY_KEY = "search_api"
PROJECT_SEARCH_PLUGIN_ID = "project-search"
PROJECT_SEARCH_PLUGIN_TIMEOUT_MS = 15000
PROJECT_SEARCH_PLUGIN_CONFIG_PATH = f"plugins.entries.{PROJECT_SEARCH_PLUGIN_ID}"
ACPX_PLUGIN_CONFIG_PATH = "plugins.entries.acpx"
NATIVE_PLUGIN_META_KEY = "_native_plugin"

LEGACY_TOOLS_BLOCK_START = "<!-- OPENCLAW-SMART-OFFICE:SEARCH_API:START -->"
LEGACY_TOOLS_BLOCK_END = "<!-- OPENCLAW-SMART-OFFICE:SEARCH_API:END -->"


class OpenClawNativeSearchPluginProvisioner:
    # Native plugin provisioner 負責 repo-local plugin 的 install/link、config 同步與 ACPX bridge readiness。
    source_mode = "plugin"

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()

    def sync_search_plugin(
        self,
        *,
        instance_id: str,
        agent_id: str,
        enabled_agent_ids: list[str],
    ) -> dict[str, Any]:
        plugin_dir = self._resolve_plugin_dir()
        started_at = time.perf_counter()
        request_summary = {
            "plugin_id": PROJECT_SEARCH_PLUGIN_ID,
            "enabled_agents": enabled_agent_ids,
            "api_base_url": self.settings.openclaw_agent_tool_api_base_url_resolved,
        }

        self._validate_plugin_package(plugin_dir)
        inspect_payload = self._ensure_plugin_installed(instance_id=instance_id, agent_id=agent_id, plugin_dir=plugin_dir)
        if not _plugin_enabled(inspect_payload):
            self._run_with_logging(
                instance_id=instance_id,
                agent_id=agent_id,
                operation_type="enable_search_plugin",
                request_summary={"plugin_id": PROJECT_SEARCH_PLUGIN_ID},
                action=lambda: self.cli_adapter.enable_plugin(PROJECT_SEARCH_PLUGIN_ID),
            )
            inspect_payload = self.cli_adapter.inspect_plugin(PROJECT_SEARCH_PLUGIN_ID)

        plugin_entry = self._read_plugin_entry()
        plugin_config = _normalize_plugin_config(plugin_entry.get("config"))
        plugin_config["apiBaseUrl"] = self.settings.openclaw_agent_tool_api_base_url_resolved
        plugin_config["timeoutMs"] = PROJECT_SEARCH_PLUGIN_TIMEOUT_MS
        plugin_config["enabledAgents"] = enabled_agent_ids

        self._run_with_logging(
            instance_id=instance_id,
            agent_id=agent_id,
            operation_type="sync_search_plugin_config",
            request_summary=request_summary,
            action=lambda: self.cli_adapter.set_global_config(
                PROJECT_SEARCH_PLUGIN_CONFIG_PATH,
                {
                    "enabled": True,
                    "config": plugin_config,
                },
            ),
        )

        bridge_ready, bridge_message = self._ensure_acpx_plugin_bridge(instance_id=instance_id, agent_id=agent_id)
        synced_at = utc_now_iso()
        last_sync_message = "原生搜索工具已就緒"
        if enabled_agent_ids:
            last_sync_message = f"原生搜索工具已就緒，已授權 {len(enabled_agent_ids)} 個 agent。"
        if bridge_message:
            last_sync_message = f"{last_sync_message} {bridge_message}".strip()

        return {
            "plugin_id": PROJECT_SEARCH_PLUGIN_ID,
            "plugin_ready": True,
            "plugin_enabled": True,
            "bridge_ready": bridge_ready,
            "api_base_url": self.settings.openclaw_agent_tool_api_base_url_resolved,
            "timeout_ms": PROJECT_SEARCH_PLUGIN_TIMEOUT_MS,
            "enabled_agents": enabled_agent_ids,
            "last_sync_status": "success",
            "last_sync_message": last_sync_message,
            "synced_at": synced_at,
            "duration_ms": _elapsed_ms(started_at),
        }

    def cleanup_legacy_workspace_artifacts(self, payload: dict[str, Any]) -> None:
        workspace_value = payload.get("workspace")
        if not isinstance(workspace_value, str) or not workspace_value.strip():
            return

        workspace_path = Path(workspace_value).expanduser().resolve()
        if not workspace_path.exists() or not workspace_path.is_dir():
            return

        support_dir = workspace_path / ".openclaw-smart-office"
        self._remove_if_exists(support_dir / "project_search.py")
        self._remove_if_exists(support_dir / "search-config.json")
        if support_dir.exists() and not any(support_dir.iterdir()):
            support_dir.rmdir()

        self._remove_if_exists(workspace_path / "SEARCH_API.md")
        self._remove_legacy_tools_block(workspace_path / "TOOLS.md")

    def _ensure_plugin_installed(self, *, instance_id: str, agent_id: str, plugin_dir: Path) -> dict[str, Any]:
        try:
            return self.cli_adapter.inspect_plugin(PROJECT_SEARCH_PLUGIN_ID)
        except OpenClawServiceError as error:
            if not self._is_missing_plugin_error(error):
                raise

        self._run_with_logging(
            instance_id=instance_id,
            agent_id=agent_id,
            operation_type="install_search_plugin",
            request_summary={"plugin_path": str(plugin_dir)},
            action=lambda: self.cli_adapter.install_plugin_link(plugin_dir),
        )
        return self.cli_adapter.inspect_plugin(PROJECT_SEARCH_PLUGIN_ID)

    def _ensure_acpx_plugin_bridge(self, *, instance_id: str, agent_id: str) -> tuple[bool, str]:
        acpx_entry = self._try_read_config(ACPX_PLUGIN_CONFIG_PATH)
        if not acpx_entry or not bool(acpx_entry.get("enabled")):
            return True, "ACPX 未啟用，略過 plugin tool bridge。"

        acpx_config = acpx_entry.get("config")
        if not isinstance(acpx_config, dict):
            acpx_config = {}

        if acpx_config.get("pluginToolsMcpBridge") is True:
            return True, "ACPX plugin-tools bridge 已就緒。"

        next_entry = {
            "enabled": True,
            "config": {
                **acpx_config,
                "pluginToolsMcpBridge": True,
            },
        }
        self._run_with_logging(
            instance_id=instance_id,
            agent_id=agent_id,
            operation_type="ensure_acpx_plugin_bridge",
            request_summary={"pluginToolsMcpBridge": True},
            action=lambda: self.cli_adapter.set_global_config(ACPX_PLUGIN_CONFIG_PATH, next_entry),
        )
        return True, "已啟用 ACPX plugin-tools bridge。"

    def _resolve_plugin_dir(self) -> Path:
        return REPO_ROOT / "openclaw-plugins" / PROJECT_SEARCH_PLUGIN_ID

    def _validate_plugin_package(self, plugin_dir: Path) -> None:
        manifest_path = plugin_dir / "openclaw.plugin.json"
        package_json_path = plugin_dir / "package.json"
        entry_path = plugin_dir / "index.js"

        for required_path in (plugin_dir, manifest_path, package_json_path, entry_path):
            if not required_path.exists():
                raise OpenClawServiceError(
                    "找不到原生搜索 plugin 套件。",
                    detail=str(required_path),
                    source_mode=self.source_mode,
                )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise OpenClawServiceError(
                "原生搜索 plugin manifest 不是合法 JSON。",
                detail=str(manifest_path),
                source_mode=self.source_mode,
            ) from error

        if manifest.get("id") != PROJECT_SEARCH_PLUGIN_ID:
            raise OpenClawServiceError(
                "原生搜索 plugin manifest id 不正確。",
                detail=f"expected={PROJECT_SEARCH_PLUGIN_ID} actual={manifest.get('id')}",
                source_mode=self.source_mode,
            )

    def _read_plugin_entry(self) -> dict[str, Any]:
        entry = self._try_read_config(PROJECT_SEARCH_PLUGIN_CONFIG_PATH)
        if entry is None:
            return {}
        return entry

    def _try_read_config(self, path: str) -> dict[str, Any] | None:
        try:
            payload = self.cli_adapter.get_global_config(path)
        except OpenClawServiceError as error:
            if "Config path not found" in (error.detail or error.message):
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def _is_missing_plugin_error(self, error: OpenClawServiceError) -> bool:
        normalized = f"{error.message} {error.detail or ''}".lower()
        return "not found" in normalized or "unknown plugin" in normalized

    def _run_with_logging(
        self,
        *,
        instance_id: str,
        agent_id: str,
        operation_type: str,
        request_summary: dict[str, Any],
        action,
    ) -> dict[str, Any]:
        try:
            result = action()
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type=operation_type,
                target_type="plugin",
                target_id=PROJECT_SEARCH_PLUGIN_ID,
                status="success",
                error_message=None,
                request_summary={**request_summary, "agent_id": agent_id},
                response_summary=result if isinstance(result, dict) else {"result": str(result)},
                source_mode=self.source_mode,
            )
            return result if isinstance(result, dict) else {"result": result}
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type=operation_type,
                target_type="plugin",
                target_id=PROJECT_SEARCH_PLUGIN_ID,
                status="failed",
                error_message=error.detail or error.message,
                request_summary={**request_summary, "agent_id": agent_id},
                response_summary=None,
                source_mode=error.source_mode or self.source_mode,
            )
            raise

    def _remove_legacy_tools_block(self, tools_path: Path) -> None:
        if not tools_path.exists():
            return
        existing = tools_path.read_text(encoding="utf-8")
        updated = _remove_managed_tools_block(existing)
        tools_path.write_text(updated, encoding="utf-8")

    def _remove_if_exists(self, path: Path) -> None:
        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path)
            return
        path.unlink()


class OpenClawAgentCapabilityService:
    # Capability service 管理 per-agent 功能開關，並在啟用時同步原生 plugin readiness。
    source_mode = "plugin"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        capability_repository: Optional[OpenClawAgentCapabilityRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
        provisioner: Optional[OpenClawNativeSearchPluginProvisioner] = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.capability_repository = capability_repository or OpenClawAgentCapabilityRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)
        self.provisioner = provisioner or OpenClawNativeSearchPluginProvisioner(
            settings=settings,
            cli_adapter=self.cli_adapter,
            operation_log_repository=self.operation_log_repository,
        )

    def list_capabilities(self, instance_id: str, agent_id: str) -> tuple[list[OpenClawAgentCapabilityResponse], int]:
        started_at = time.perf_counter()
        self.repository.get(instance_id)
        records = self.capability_repository.list_for_agent(instance_id=instance_id, agent_id=agent_id)
        return [self._to_response(record) for record in records], _elapsed_ms(started_at)

    def set_search_capability(
        self,
        agent_id: str,
        payload: OpenClawAgentCapabilityUpsertRequest,
    ) -> tuple[OpenClawAgentCapabilityResponse, int]:
        started_at = time.perf_counter()
        instance, token = self._load_context(payload.instance_id)
        normalized_config = _normalize_capability_config(payload.config)
        request_summary = {
            "capability_key": SEARCH_API_CAPABILITY_KEY,
            "enabled": payload.enabled,
            "config": normalized_config,
        }

        try:
            agent_payload: dict[str, Any] | None = None
            if payload.enabled:
                agent_payload = self._get_agent_payload(instance_id=payload.instance_id, instance=instance, token=token, agent_id=agent_id)
                self._assert_no_cross_instance_conflicts(instance_id=payload.instance_id, agent_id=agent_id)
            else:
                agent_payload = self._try_get_agent_payload(instance_id=payload.instance_id, instance=instance, token=token, agent_id=agent_id)

            enabled_agent_ids = self._resolve_enabled_agent_ids(instance_id=payload.instance_id, agent_id=agent_id, enabled=payload.enabled)
            plugin_status = self.provisioner.sync_search_plugin(
                instance_id=payload.instance_id,
                agent_id=agent_id,
                enabled_agent_ids=enabled_agent_ids,
            )
            if agent_payload is not None:
                self.provisioner.cleanup_legacy_workspace_artifacts(agent_payload)

            record = self.capability_repository.upsert(
                instance_id=payload.instance_id,
                agent_id=agent_id,
                capability_key=SEARCH_API_CAPABILITY_KEY,
                is_enabled=payload.enabled,
                config=_merge_capability_config(normalized_config, plugin_status),
            )
            response = self._to_response(
                record,
                message="原生搜索工具已就緒" if payload.enabled else "Agent 原生搜索能力已停用",
            )
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="configure_agent_search_capability",
                target_type="agent",
                target_id=agent_id,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary={
                    "is_enabled": record.is_enabled,
                    "plugin_id": response.native_plugin_id,
                    "plugin_ready": response.native_plugin_ready,
                    "bridge_ready": response.bridge_ready,
                },
                source_mode=self.source_mode,
            )
            return response, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="configure_agent_search_capability",
                target_type="agent",
                target_id=agent_id,
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or self.source_mode,
            )
            raise

    def assert_search_enabled(self, *, agent_id: str, instance_id: Optional[str] = None) -> OpenClawAgentCapabilityRecord:
        enabled_records = [
            record
            for record in self.capability_repository.list_enabled_for_capability(capability_key=SEARCH_API_CAPABILITY_KEY)
            if record.agent_id == agent_id
        ]

        if not enabled_records:
            raise OpenClawServiceError(
                "Agent 尚未開啟搜索能力。",
                detail=f"agent_id={agent_id} capability={SEARCH_API_CAPABILITY_KEY}",
                status_code=403,
                source_mode=self.source_mode,
            )

        if len(enabled_records) > 1:
            raise OpenClawServiceError(
                "同名 Agent 在多個 Instance 上同時啟用了原生搜索能力。",
                detail=f"agent_id={agent_id}",
                status_code=409,
                source_mode=self.source_mode,
            )

        record = enabled_records[0]
        if instance_id and record.instance_id != instance_id:
            raise OpenClawServiceError(
                "Agent 搜索能力與指定 Instance 不一致。",
                detail=f"requested_instance={instance_id} actual_instance={record.instance_id} agent_id={agent_id}",
                status_code=403,
                source_mode=self.source_mode,
            )
        return record

    def build_capability_summary_map(self, instance_id: str) -> dict[str, dict[str, dict[str, Any]]]:
        summary: dict[str, dict[str, dict[str, Any]]] = {}
        for record in self.capability_repository.list_for_instance(instance_id=instance_id):
            native_status = _read_native_plugin_status(record.config)
            summary.setdefault(record.agent_id, {})[record.capability_key] = {
                "enabled": record.is_enabled,
                "config": _strip_internal_capability_config(record.config),
                "updated_at": record.updated_at.isoformat(),
                "plugin_id": native_status["plugin_id"],
                "plugin_ready": native_status["plugin_ready"],
                "plugin_enabled": native_status["plugin_enabled"],
                "bridge_ready": native_status["bridge_ready"],
                "last_sync_status": native_status["last_sync_status"],
                "last_sync_message": native_status["last_sync_message"],
                "synced_at": native_status["synced_at"],
            }
        return summary

    def _assert_no_cross_instance_conflicts(self, *, instance_id: str, agent_id: str) -> None:
        conflicts = self.capability_repository.find_conflicts(
            capability_key=SEARCH_API_CAPABILITY_KEY,
            agent_id=agent_id,
            exclude_instance_id=instance_id,
        )
        if conflicts:
            conflict_instances = ", ".join(sorted({record.instance_id for record in conflicts}))
            raise OpenClawServiceError(
                "不同 Instance 嘗試共用同名 Agent 的原生搜索能力。",
                detail=f"agent_id={agent_id} conflicts={conflict_instances}",
                status_code=409,
                source_mode=self.source_mode,
            )

    def _resolve_enabled_agent_ids(self, *, instance_id: str, agent_id: str, enabled: bool) -> list[str]:
        active_agents = {
            record.agent_id
            for record in self.capability_repository.list_enabled_for_capability(capability_key=SEARCH_API_CAPABILITY_KEY)
            if record.agent_id != agent_id
        }
        if enabled:
            active_agents.add(agent_id)
        return sorted(active_agents)

    def _load_context(self, instance_id: str) -> tuple[Any, Optional[str]]:
        instance = self.repository.get(instance_id)
        encrypted_token = self.repository.get_secret(instance_id)
        token = self.secret_cipher.decrypt(encrypted_token) if encrypted_token else None
        return instance, token

    def _get_agent_payload(self, *, instance_id: str, instance: Any, token: Optional[str], agent_id: str) -> dict[str, Any]:
        for item in self.cli_adapter.list_agents(instance, token):
            candidate_id = str(item.get("id") or item.get("agent_id") or "")
            if candidate_id == agent_id:
                return item
        raise OpenClawServiceError(
            "找不到指定的 OpenClaw Agent。",
            detail=f"instance_id={instance_id} agent_id={agent_id}",
            status_code=404,
            source_mode=self.cli_adapter.source_mode,
        )

    def _try_get_agent_payload(self, *, instance_id: str, instance: Any, token: Optional[str], agent_id: str) -> dict[str, Any] | None:
        try:
            return self._get_agent_payload(instance_id=instance_id, instance=instance, token=token, agent_id=agent_id)
        except OpenClawServiceError as error:
            if error.status_code == 404:
                return None
            raise

    def _to_response(
        self,
        record: OpenClawAgentCapabilityRecord,
        *,
        message: Optional[str] = None,
    ) -> OpenClawAgentCapabilityResponse:
        native_status = _read_native_plugin_status(record.config)
        return OpenClawAgentCapabilityResponse(
            id=record.id,
            instance_id=record.instance_id,
            agent_id=record.agent_id,
            capability_key=record.capability_key,
            is_enabled=record.is_enabled,
            config=_strip_internal_capability_config(record.config),
            native_plugin_id=native_status["plugin_id"],
            native_plugin_ready=native_status["plugin_ready"],
            native_plugin_enabled=native_status["plugin_enabled"],
            bridge_ready=native_status["bridge_ready"],
            last_sync_status=native_status["last_sync_status"],
            last_sync_message=native_status["last_sync_message"],
            workspace_synced=False,
            message=message or native_status["last_sync_message"],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


def _normalize_capability_config(payload: dict[str, Any]) -> dict[str, Any]:
    # 第一期只接受搜索工具真正需要的幾個欄位，避免把任意 UI 狀態原樣落庫。
    normalized: dict[str, Any] = {}

    source_id = payload.get("source_id")
    if isinstance(source_id, str) and source_id.strip():
        normalized["source_id"] = source_id.strip()

    limit = payload.get("limit")
    if isinstance(limit, int) and limit > 0:
        normalized["limit"] = limit

    max_chars = payload.get("max_chars")
    if isinstance(max_chars, int) and max_chars > 0:
        normalized["max_chars"] = max_chars

    return normalized


def _merge_capability_config(user_config: dict[str, Any], plugin_status: dict[str, Any]) -> dict[str, Any]:
    return {
        **user_config,
        NATIVE_PLUGIN_META_KEY: plugin_status,
    }


def _strip_internal_capability_config(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key != NATIVE_PLUGIN_META_KEY
    }


def _read_native_plugin_status(payload: dict[str, Any]) -> dict[str, Any]:
    native = payload.get(NATIVE_PLUGIN_META_KEY)
    if not isinstance(native, dict):
        return {
            "plugin_id": None,
            "plugin_ready": False,
            "plugin_enabled": False,
            "bridge_ready": False,
            "last_sync_status": None,
            "last_sync_message": None,
            "synced_at": None,
        }

    return {
        "plugin_id": native.get("plugin_id"),
        "plugin_ready": bool(native.get("plugin_ready")),
        "plugin_enabled": bool(native.get("plugin_enabled")),
        "bridge_ready": bool(native.get("bridge_ready")),
        "last_sync_status": native.get("last_sync_status"),
        "last_sync_message": native.get("last_sync_message"),
        "synced_at": native.get("synced_at"),
    }


def _normalize_plugin_config(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {
            key: value
            for key, value in payload.items()
            if key in {"apiBaseUrl", "timeoutMs", "enabledAgents"}
        }
    return {}


def _plugin_enabled(payload: dict[str, Any]) -> bool:
    plugin = payload.get("plugin")
    if not isinstance(plugin, dict):
        return False
    return bool(plugin.get("enabled"))


def _remove_managed_tools_block(content: str) -> str:
    start_index = content.find(LEGACY_TOOLS_BLOCK_START)
    end_index = content.find(LEGACY_TOOLS_BLOCK_END)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return content

    before = content[:start_index].rstrip()
    after = content[end_index + len(LEGACY_TOOLS_BLOCK_END) :].lstrip()
    if not before and not after:
        return ""
    return "\n\n".join(part for part in [before, after] if part).rstrip() + "\n"


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)
