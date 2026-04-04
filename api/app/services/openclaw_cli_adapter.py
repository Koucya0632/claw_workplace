from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional, Union

from app.config import get_settings
from app.schemas.openclaw_instance import OpenClawInstanceResponse
from app.services.openclaw_errors import OpenClawServiceError
from app.utils import truncate_text


class OpenClawCliAdapter:
    # CLI adapter 把 subprocess 邏輯集中起來，避免 router 與 service 直接碰指令細節。
    source_mode = "cli"

    def __init__(self) -> None:
        settings = get_settings()
        self.binary = settings.openclaw_cli_bin
        self.timeout_seconds = settings.openclaw_cli_timeout_seconds

    def get_health(self, instance: OpenClawInstanceResponse, token: Optional[str]) -> dict[str, Any]:
        return self._run_json_command(instance, token, ["gateway", "health", "--json"])

    def list_agents(self, instance: OpenClawInstanceResponse, token: Optional[str]) -> list[dict[str, Any]]:
        payload = self._run_json_command(instance, token, ["agents", "list", "--json"])
        return _coerce_items(payload)

    def create_agent(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        # OpenClaw 2026.4.1 起建立 agent 改用 `agents add`，而且非互動模式必須提供 workspace。
        return self._run_json_command(
            instance,
            token,
            self._build_create_agent_args(instance, payload),
        )

    def list_devices(self, instance: OpenClawInstanceResponse, token: Optional[str]) -> list[dict[str, Any]]:
        payload = self._run_json_command(instance, token, ["devices", "list", "--json"])
        return _coerce_devices(payload)

    def approve_device(self, instance: OpenClawInstanceResponse, token: Optional[str], device_id: str) -> dict[str, Any]:
        return self._run_json_command(instance, token, ["devices", "approve", device_id, "--json"])

    def reject_device(self, instance: OpenClawInstanceResponse, token: Optional[str], device_id: str) -> dict[str, Any]:
        return self._run_json_command(instance, token, ["devices", "reject", device_id, "--json"])

    def revoke_device(self, instance: OpenClawInstanceResponse, token: Optional[str], device_id: str) -> dict[str, Any]:
        return self._run_json_command(instance, token, ["devices", "revoke", device_id, "--json"])

    def get_config(self, instance: OpenClawInstanceResponse, token: Optional[str], path: str) -> dict[str, Any]:
        return self._run_json_command(instance, token, ["config", "get", path, "--json"])

    def set_config(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        path: str,
        value: Any,
    ) -> dict[str, Any]:
        serialized_value = json.dumps(value, ensure_ascii=False)
        stdout = self._run_text_command(
            instance,
            token,
            ["config", "set", path, serialized_value, "--strict-json"],
        )
        return {"value": value, "message": stdout or f"{path} updated"}

    def validate_config(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        path: str,
        value: Any,
    ) -> dict[str, Any]:
        serialized_value = json.dumps(value, ensure_ascii=False)
        stdout = self._run_text_command(
            instance,
            token,
            ["config", "set", path, serialized_value, "--strict-json", "--dry-run"],
        )
        return {"valid": True, "messages": [stdout] if stdout else []}

    def get_logs(self, instance: OpenClawInstanceResponse, token: Optional[str], limit: int) -> list[dict[str, Any]]:
        payload = self._run_json_lines_command(instance, token, ["logs", "--json", "--limit", str(limit)])
        return _coerce_logs(payload)

    def inspect_plugin(self, plugin_id: str) -> dict[str, Any]:
        payload = self._run_global_json_command(["plugins", "inspect", plugin_id, "--json"])
        if not isinstance(payload, dict):
            raise OpenClawServiceError(
                "OpenClaw plugin inspect 輸出格式不正確。",
                detail=truncate_text(str(payload)),
                source_mode=self.source_mode,
            )
        return payload

    def install_plugin_link(self, plugin_path: Path) -> dict[str, Any]:
        stdout = self._run_global_text_command(["plugins", "install", "--link", str(plugin_path)])
        return {"message": stdout or f"linked plugin from {plugin_path}"}

    def enable_plugin(self, plugin_id: str) -> dict[str, Any]:
        stdout = self._run_global_text_command(["plugins", "enable", plugin_id])
        return {"message": stdout or f"enabled plugin {plugin_id}"}

    def disable_plugin(self, plugin_id: str) -> dict[str, Any]:
        stdout = self._run_global_text_command(["plugins", "disable", plugin_id])
        return {"message": stdout or f"disabled plugin {plugin_id}"}

    def get_global_config(self, path: str) -> dict[str, Any]:
        payload = self._run_global_json_command(["config", "get", path, "--json"])
        if isinstance(payload, dict):
            return payload
        return {"value": payload}

    def set_global_config(self, path: str, value: Any) -> dict[str, Any]:
        serialized_value = json.dumps(value, ensure_ascii=False)
        stdout = self._run_global_text_command(["config", "set", path, serialized_value, "--strict-json"])
        return {"value": value, "message": stdout or f"{path} updated"}

    def _run_json_command(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        args: list[str],
    ) -> Union[dict[str, Any], list[dict[str, Any]]]:
        stdout = self._run_text_command(instance, token, args)
        if not stdout:
            return {}

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as error:
            raise OpenClawServiceError(
                "OpenClaw CLI 輸出不是合法 JSON。",
                detail=truncate_text(stdout),
                source_mode=self.source_mode,
            ) from error

    def _run_global_json_command(self, args: list[str]) -> Union[dict[str, Any], list[dict[str, Any]]]:
        stdout = self._run_global_text_command(args)
        if not stdout:
            return {}

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as error:
            raise OpenClawServiceError(
                "OpenClaw CLI 全域輸出不是合法 JSON。",
                detail=truncate_text(stdout),
                source_mode=self.source_mode,
            ) from error

    def _run_json_lines_command(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        args: list[str],
    ) -> list[dict[str, Any]]:
        # logs --json 在 2026.4.1 回的是逐行 JSON，而不是單一 JSON 文件。
        stdout = self._run_text_command(instance, token, args)
        if not stdout:
            return []

        parsed_lines: list[dict[str, Any]] = []

        for line in stdout.splitlines():
            normalized = line.strip()
            if not normalized:
                continue

            try:
                payload = json.loads(normalized)
            except json.JSONDecodeError as error:
                raise OpenClawServiceError(
                    "OpenClaw CLI 日誌輸出不是合法 JSON lines。",
                    detail=truncate_text(normalized),
                    source_mode=self.source_mode,
                ) from error

            if isinstance(payload, dict):
                parsed_lines.append(payload)

        return parsed_lines

    def _run_text_command(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        args: list[str],
    ) -> str:
        # config set / dry-run 在 2026.4.1 會回純文字成功訊息，因此抽一層純文字執行器共用。
        env = {
            "OPENCLAW_GATEWAY_URL": instance.gateway_url,
        }

        if token:
            env["OPENCLAW_GATEWAY_TOKEN"] = token

        return self._run_command([self.binary, *args], env)

    def _run_global_text_command(self, args: list[str]) -> str:
        return self._run_command([self.binary, *args], {})

    def _run_command(self, command: list[str], env_overrides: dict[str, str]) -> str:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                env={**os.environ, **env_overrides},
            )
        except subprocess.TimeoutExpired as error:
            raise OpenClawServiceError(
                "OpenClaw CLI 執行逾時。",
                detail=f"command={' '.join(command)} timeout={self.timeout_seconds}s",
                source_mode=self.source_mode,
            ) from error
        except OSError as error:
            raise OpenClawServiceError(
                "無法執行 OpenClaw CLI。",
                detail=str(error),
                source_mode=self.source_mode,
            ) from error

        if completed.returncode != 0:
            raise OpenClawServiceError(
                "OpenClaw CLI 執行失敗。",
                detail=truncate_text(completed.stderr.strip() or completed.stdout.strip()),
                source_mode=self.source_mode,
            )

        return completed.stdout.strip()

    def _build_create_agent_args(self, instance: OpenClawInstanceResponse, payload: dict[str, Any]) -> list[str]:
        # 這裡只映射目前 CLI 真正支援的參數；prompt / role_hint 先保留在 metadata，不強行塞給 CLI。
        agent_name = str(payload.get("name") or "").strip()
        if not agent_name:
            raise OpenClawServiceError("建立 Agent 時缺少 name。", source_mode=self.source_mode)

        workspace_path = self._build_agent_workspace(instance.id, agent_name)
        workspace_path.mkdir(parents=True, exist_ok=True)

        command = [
            "agents",
            "add",
            agent_name,
            "--json",
            "--non-interactive",
            "--workspace",
            str(workspace_path),
        ]

        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            model = metadata.get("model")
            if isinstance(model, str) and model.strip():
                command.extend(["--model", model.strip()])

            bindings = metadata.get("bindings")
            if isinstance(bindings, list):
                for binding in bindings:
                    if isinstance(binding, str) and binding.strip():
                        command.extend(["--bind", binding.strip()])

        return command

    def _build_agent_workspace(self, instance_id: str, agent_name: str) -> Path:
        # 每個 instance / agent 都分配固定 workspace，讓 CLI 可重複執行且不互相覆蓋。
        settings = get_settings()
        slug = _slugify(agent_name)
        return settings.database_file.parent / "openclaw_agents" / instance_id / slug


def _coerce_items(payload: Any) -> list[dict[str, Any]]:
    # 實際 CLI 與測試替身可能有不同包裝層，這裡先容忍 list 或 {items: list} 兩種形狀。
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    return []


def _coerce_devices(payload: Any) -> list[dict[str, Any]]:
    # OpenClaw 2026.4.1 的 devices list 會回 {pending: [...], paired: [...]}，這裡先展平成一致格式。
    if isinstance(payload, dict):
        grouped_devices: list[dict[str, Any]] = []

        for group_name in ("pending", "paired", "revoked"):
            items = payload.get(group_name)
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue

                normalized = dict(item)
                normalized.setdefault("status", group_name)
                if group_name == "pending":
                    normalized.setdefault("pending_action", "approve")
                grouped_devices.append(normalized)

        if grouped_devices:
            return grouped_devices

    return _coerce_items(payload)


def _coerce_logs(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # logs 會混入 meta/error/log 多種 line type，前端只需要可顯示的摘要格式。
    normalized_logs: list[dict[str, Any]] = []

    for item in payload:
        line_type = str(item.get("type") or "")

        if line_type == "meta":
            normalized_logs.append(
                {
                    "timestamp": None,
                    "level": "meta",
                    "message": f"log file: {item.get('file', 'unknown')} cursor={item.get('cursor', '?')}",
                    "raw": json.dumps(item, ensure_ascii=False),
                }
            )
            continue

        if line_type == "error":
            normalized_logs.append(
                {
                    "timestamp": None,
                    "level": "error",
                    "message": str(item.get("message") or item.get("error") or "OpenClaw log error"),
                    "raw": json.dumps(item, ensure_ascii=False),
                }
            )
            continue

        if line_type == "log":
            normalized_logs.append(
                {
                    "timestamp": item.get("time"),
                    "level": item.get("level"),
                    "message": str(item.get("message") or ""),
                    "raw": json.dumps(item, ensure_ascii=False),
                }
            )
            continue

        normalized_logs.append(
            {
                "timestamp": item.get("time"),
                "level": item.get("level"),
                "message": str(item.get("message") or line_type or "unknown log line"),
                "raw": json.dumps(item, ensure_ascii=False),
            }
        )

    return normalized_logs


def _slugify(value: str) -> str:
    # workspace 路徑只保留安全字元，避免 agent 名稱含空白或符號導致路徑混亂。
    sanitized = "".join(character.lower() if character.isalnum() else "-" for character in value)
    collapsed = "-".join(segment for segment in sanitized.split("-") if segment)
    return collapsed or "agent"
