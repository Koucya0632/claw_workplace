from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional

from app.schemas.openclaw_instance import OpenClawInstanceResponse
from app.services.openclaw_errors import OpenClawServiceError
from app.utils import truncate_text


class OpenClawHookClient:
    # OpenClaw 2026.4.1 對應的手動派發入口更接近 CLI agent turn，而不是公開 /hooks HTTP 路徑。
    source_mode = "cli"

    def __init__(self) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.timeout_seconds = settings.openclaw_cli_timeout_seconds
        self.binary = settings.openclaw_cli_bin

    def dispatch_agent(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._run_agent_command(instance, token, payload)

    def dispatch_wake(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raise OpenClawServiceError(
            "目前這個 OpenClaw 版本未提供可用的 wake 派發入口。",
            detail="請改用 `openclaw agent` 或在管理台使用 Agent Hook。Wake Hook 已暫時停用。",
            status_code=501,
            source_mode=self.source_mode,
        )

    def _run_agent_command(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or "").strip()
        session_key = str(payload.get("session_key") or "").strip()
        message = str(payload.get("message") or "").strip()

        if not agent_id or not session_key or not message:
            raise OpenClawServiceError(
                "Agent 派發缺少必要欄位。",
                detail="agent_id、session_key、message 都必填。",
                source_mode=self.source_mode,
            )

        command = [
            self.binary,
            "agent",
            "--agent",
            agent_id,
            "--session-id",
            session_key,
            "--message",
            message,
            "--json",
        ]

        if payload.get("deliver"):
            command.append("--deliver")
        if isinstance(payload.get("channel"), str) and payload["channel"].strip():
            command.extend(["--channel", payload["channel"].strip()])
        if isinstance(payload.get("to"), str) and payload["to"].strip():
            command.extend(["--reply-to", payload["to"].strip()])

        env = {
            "OPENCLAW_GATEWAY_URL": instance.gateway_url,
        }
        if token:
            env["OPENCLAW_GATEWAY_TOKEN"] = token

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                env={**os.environ, **env},
            )
        except subprocess.TimeoutExpired as error:
            raise OpenClawServiceError(
                "OpenClaw agent 派發逾時。",
                detail=f"command={' '.join(command)} timeout={self.timeout_seconds}s",
                source_mode=self.source_mode,
            ) from error
        except OSError as error:
            raise OpenClawServiceError(
                "無法執行 OpenClaw agent 命令。",
                detail=str(error),
                source_mode=self.source_mode,
            ) from error

        if completed.returncode != 0:
            raise OpenClawServiceError(
                "OpenClaw agent 派發失敗。",
                detail=truncate_text(completed.stderr.strip() or completed.stdout.strip()),
                source_mode=self.source_mode,
            )

        stdout = completed.stdout.strip()
        try:
            result = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError as error:
            raise OpenClawServiceError(
                "OpenClaw agent 輸出不是合法 JSON。",
                detail=truncate_text(stdout),
                source_mode=self.source_mode,
            ) from error

        if isinstance(result, dict):
            return result

        return {"result": result}
