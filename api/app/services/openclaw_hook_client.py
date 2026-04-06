from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any, Optional

from app.schemas.openclaw_instance import OpenClawInstanceResponse
from app.services.openclaw_errors import OpenClawServiceError
from app.utils import truncate_text


class OpenClawHookClient:
    # OpenClaw 2026.4.1 對應的手動派發入口更接近 CLI agent turn，而不是公開 /hooks HTTP 路徑。
    source_mode = "cli"
    preview_max_length = 500

    def __init__(self) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.timeout_seconds = settings.openclaw_agent_dispatch_timeout_seconds
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

    def _classify_cli_failure(self, *, stdout: str, stderr: str) -> str:
        haystack = f"{stderr}\n{stdout}".lower()
        if "timed out" in haystack or "timeout" in haystack:
            if "failover" in haystack or "embedded" in haystack or "minimax" in haystack:
                return "embedded_model_timeout"
            return "dispatch_timeout"
        if "failover" in haystack or "embedded_run_failover_decision" in haystack or "surface_error" in haystack:
            return "embedded_model_timeout"
        return "cli_nonzero_exit"

    def _run_agent_command(
        self,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or "").strip()
        session_key = str(payload.get("session_key") or "").strip()
        message = str(payload.get("message") or "").strip()
        timeout_seconds = int(payload.get("timeout_seconds") or self.timeout_seconds)

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

        started_at = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env={**os.environ, **env},
            )
        except subprocess.TimeoutExpired as error:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            raise OpenClawServiceError(
                "OpenClaw agent 派發逾時。",
                detail=f"command={' '.join(command)} timeout={timeout_seconds}s",
                source_mode=self.source_mode,
                metadata={
                    "failure_kind": "dispatch_timeout",
                    "returncode": None,
                    "duration_ms": duration_ms,
                    "stdout_preview": "",
                    "stderr_preview": "",
                    "timeout_seconds": timeout_seconds,
                },
            ) from error
        except OSError as error:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            raise OpenClawServiceError(
                "無法執行 OpenClaw agent 命令。",
                detail=str(error),
                source_mode=self.source_mode,
                metadata={
                    "failure_kind": "cli_nonzero_exit",
                    "returncode": None,
                    "duration_ms": duration_ms,
                    "stdout_preview": "",
                    "stderr_preview": truncate_text(str(error), self.preview_max_length),
                    "timeout_seconds": timeout_seconds,
                },
            ) from error

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()

        if completed.returncode != 0:
            raise OpenClawServiceError(
                "OpenClaw agent 派發失敗。",
                detail=truncate_text(stderr or stdout),
                source_mode=self.source_mode,
                metadata={
                    "failure_kind": self._classify_cli_failure(stdout=stdout, stderr=stderr),
                    "returncode": completed.returncode,
                    "duration_ms": duration_ms,
                    "stdout_preview": truncate_text(stdout, self.preview_max_length),
                    "stderr_preview": truncate_text(stderr, self.preview_max_length),
                    "timeout_seconds": timeout_seconds,
                },
            )

        stdout = completed.stdout.strip()
        try:
            result = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError as error:
            raise OpenClawServiceError(
                "OpenClaw agent 輸出不是合法 JSON。",
                detail=truncate_text(stdout),
                source_mode=self.source_mode,
                metadata={
                    "failure_kind": "invalid_json_output",
                    "returncode": completed.returncode,
                    "duration_ms": duration_ms,
                    "stdout_preview": truncate_text(stdout, self.preview_max_length),
                    "stderr_preview": truncate_text(stderr, self.preview_max_length),
                    "timeout_seconds": timeout_seconds,
                },
            ) from error

        if isinstance(result, dict):
            result.setdefault("_dispatch_meta", {})
            result["_dispatch_meta"].update(
                {
                    "returncode": completed.returncode,
                    "duration_ms": duration_ms,
                    "stdout_preview": truncate_text(stdout, self.preview_max_length),
                    "stderr_preview": truncate_text(stderr, self.preview_max_length),
                    "timeout_seconds": timeout_seconds,
                }
            )
            return result

        return {
            "result": result,
            "_dispatch_meta": {
                "returncode": completed.returncode,
                "duration_ms": duration_ms,
                "stdout_preview": truncate_text(stdout, self.preview_max_length),
                "stderr_preview": truncate_text(stderr, self.preview_max_length),
                "timeout_seconds": timeout_seconds,
            },
        }
