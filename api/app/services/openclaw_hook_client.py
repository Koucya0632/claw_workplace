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
    history_preview_max_length = 4000

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
            detail="請改用 `openclaw agent` 或在 OpenClaw Control Center 使用 Agent Hook。Wake Hook 已暫時停用。",
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
        started_at = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env=os.environ.copy(),
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
            self._recover_missing_text_from_session_history(
                instance=instance,
                token=token,
                session_key=session_key,
                message=message,
                timeout_seconds=timeout_seconds,
                result=result,
            )
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

    def _recover_missing_text_from_session_history(
        self,
        *,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        session_key: str,
        message: str,
        timeout_seconds: int,
        result: dict[str, Any],
    ) -> None:
        if self._extract_result_text(result):
            return

        session_id = self._extract_session_id(result)
        recovered = self._read_session_history_fallback(
            instance=instance,
            token=token,
            session_key=session_key,
            session_id=session_id,
            prompt_message=message,
            timeout_seconds=timeout_seconds,
        )
        if not recovered:
            return

        result_payload = result.get("result")
        if not isinstance(result_payload, dict):
            result_payload = {}
            result["result"] = result_payload

        payloads = result_payload.get("payloads")
        if not isinstance(payloads, list):
            payloads = []
            result_payload["payloads"] = payloads

        payloads.append({"text": recovered})

    def _extract_result_text(self, payload: dict[str, Any]) -> str:
        result = payload.get("result")
        if isinstance(result, dict):
            payloads = result.get("payloads")
            if isinstance(payloads, list):
                for item in payloads:
                    if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                        return item["text"].strip()
            for key in ["text", "output_text", "content"]:
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            message = result.get("message")
            if isinstance(message, dict):
                for key in ["text", "content", "output_text"]:
                    value = message.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            if isinstance(message, str) and message.strip():
                return message.strip()

        for key in ["text", "output_text", "content"]:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        message = payload.get("message")
        if isinstance(message, dict):
            for key in ["text", "content", "output_text"]:
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(message, str) and message.strip():
            return message.strip()
        return ""

    def _extract_session_id(self, payload: dict[str, Any]) -> str:
        result = payload.get("result")
        if not isinstance(result, dict):
            return ""
        meta = result.get("meta")
        if not isinstance(meta, dict):
            return ""
        agent_meta = meta.get("agentMeta")
        if not isinstance(agent_meta, dict):
            return ""
        session_id = agent_meta.get("sessionId")
        return session_id.strip() if isinstance(session_id, str) else ""

    def _read_session_history_fallback(
        self,
        *,
        instance: OpenClawInstanceResponse,
        token: Optional[str],
        session_key: str,
        session_id: str,
        prompt_message: str,
        timeout_seconds: int,
    ) -> str:
        identifiers: list[str] = []
        for candidate in [session_key, session_id]:
            normalized = candidate.strip()
            if normalized and normalized not in identifiers:
                identifiers.append(normalized)

        if not identifiers:
            return ""

        for identifier in identifiers:
            for args in [
                ["sessions", "history", identifier, "--json", "--limit", "24"],
                ["sessions", "history", identifier, "--limit", "24", "--json"],
                ["sessions", "history", identifier, "--json"],
            ]:
                stdout = self._run_optional_command(
                    [self.binary, *args],
                    env=os.environ.copy(),
                    timeout_seconds=min(timeout_seconds, self.timeout_seconds),
                )
                if not stdout:
                    continue
                text = self._extract_prompt_aligned_assistant_text(stdout, prompt_message)
                if text:
                    return text

        return ""

    def _run_optional_command(
        self,
        command: list[str],
        *,
        env: dict[str, str],
        timeout_seconds: int,
    ) -> str:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(5, timeout_seconds),
                check=False,
                env=env,
            )
        except Exception:  # noqa: BLE001
            return ""

        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()

    def _extract_latest_assistant_text(self, raw: str) -> str:
        parsed_entries = self._parse_history_entries(raw)
        for entry in reversed(parsed_entries):
            role = self._extract_history_entry_role(entry)
            content = self._extract_history_entry_text(entry)
            if not content:
                continue
            if role in {"assistant", "agent"} or role == "":
                return truncate_text(content, self.history_preview_max_length)
        return ""

    def _extract_prompt_aligned_assistant_text(self, raw: str, prompt_message: str) -> str:
        parsed_entries = self._parse_history_entries(raw)
        if not parsed_entries:
            return ""

        normalized_prompt = self._normalize_history_text(prompt_message)
        if not normalized_prompt:
            return self._extract_latest_assistant_text(raw)

        latest_aligned_reply = ""
        assistant_candidates: list[str] = []

        for index, entry in enumerate(parsed_entries):
            role = self._extract_history_entry_role(entry)
            content = self._extract_history_entry_text(entry)
            if not content:
                continue

            if role in {"assistant", "agent"} or role == "":
                assistant_candidates.append(content)
                continue

            if role not in {"user", "human"}:
                continue

            if not self._history_text_matches_prompt(content, normalized_prompt):
                continue

            for follower in parsed_entries[index + 1 :]:
                follower_role = self._extract_history_entry_role(follower)
                follower_text = self._extract_history_entry_text(follower)
                if not follower_text:
                    continue
                if follower_role in {"user", "human"}:
                    break
                if follower_role in {"assistant", "agent"} or follower_role == "":
                    latest_aligned_reply = follower_text
                    break

        if latest_aligned_reply:
            return truncate_text(latest_aligned_reply, self.history_preview_max_length)

        if len(assistant_candidates) == 1:
            return truncate_text(assistant_candidates[0], self.history_preview_max_length)

        return ""

    def _parse_history_entries(self, raw: str) -> list[dict[str, Any]]:
        parsed = self._safe_json_load(raw)
        if parsed is not None:
            return self._extract_history_array(parsed)

        entries: list[dict[str, Any]] = []
        for line in raw.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            parsed_line = self._safe_json_load(normalized)
            if isinstance(parsed_line, dict):
                entries.append(parsed_line)
        return entries

    def _safe_json_load(self, raw: str) -> Any:
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return None

    def _extract_history_array(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        for key in ["history", "messages", "items", "entries", "events", "conversation"]:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

        for key in ["data", "result", "payload"]:
            nested = payload.get(key)
            extracted = self._extract_history_array(nested)
            if extracted:
                return extracted

        return []

    def _extract_history_entry_role(self, entry: dict[str, Any]) -> str:
        role = entry.get("role") or entry.get("speaker") or entry.get("source") or entry.get("type")
        return role.strip().lower() if isinstance(role, str) else ""

    def _normalize_history_text(self, value: str) -> str:
        return "".join(value.lower().split())

    def _history_text_matches_prompt(self, content: str, normalized_prompt: str) -> bool:
        candidate = self._normalize_history_text(content)
        if not candidate:
            return False

        if (
            candidate == normalized_prompt
            or candidate in normalized_prompt
            or normalized_prompt in candidate
        ):
            return True

        fragments: list[str] = []
        prompt_length = len(normalized_prompt)
        if prompt_length >= 16:
            fragments.append(normalized_prompt[: min(80, prompt_length)])
        if prompt_length >= 32:
            window = min(48, prompt_length)
            starts = {
                0,
                max(0, (prompt_length // 2) - (window // 2)),
                max(0, prompt_length - window),
            }
            if prompt_length >= 96:
                starts.add(max(0, (prompt_length // 3) - (window // 2)))
                starts.add(max(0, ((prompt_length * 2) // 3) - (window // 2)))
            for start in sorted(starts):
                fragment = normalized_prompt[start : start + window]
                if fragment:
                    fragments.append(fragment)

        return any(fragment and fragment in candidate for fragment in fragments)

    def _extract_history_entry_text(self, entry: dict[str, Any]) -> str:
        for key in ["content", "text", "output_text"]:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        message = entry.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        if isinstance(message, dict):
            for key in ["content", "text"]:
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        result = entry.get("result")
        if isinstance(result, dict):
            payloads = result.get("payloads")
            if isinstance(payloads, list):
                for item in payloads:
                    if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                        return item["text"].strip()
            for key in ["content", "text", "output_text"]:
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            message = result.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            if isinstance(message, dict):
                for key in ["content", "text", "output_text"]:
                    value = message.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

        return ""
