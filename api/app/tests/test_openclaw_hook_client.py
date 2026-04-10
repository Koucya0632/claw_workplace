from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import pytest

from app.config import get_settings
from app.schemas.openclaw_instance import OpenClawInstanceResponse
from app.services.openclaw_hook_client import OpenClawHookClient


def build_instance() -> OpenClawInstanceResponse:
    now = datetime.now(timezone.utc)
    return OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        created_at=now,
        updated_at=now,
    )


def test_dispatch_agent_uses_current_cli_agent_args_without_gateway_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        if command[1] == "agent":
            captured["command"] = command
            captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"accepted": True, "task_id": "turn_1"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "support-agent",
            "session_key": "ticket:1001",
            "message": "請整理客服需求",
            "channel": "web",
            "to": "customer:42",
            "deliver": True,
        },
    )

    assert result["accepted"] is True
    assert captured["command"] == [
        client.binary,
        "agent",
        "--agent",
        "support-agent",
        "--session-id",
        "ticket:1001",
        "--message",
        "請整理客服需求",
        "--json",
        "--deliver",
        "--channel",
        "web",
        "--reply-to",
        "customer:42",
    ]
    assert isinstance(captured["env"], dict)


def test_dispatch_agent_uses_dedicated_dispatch_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        if command[1] == "agent":
            captured["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"status": "ok"}),
            stderr="",
        )

    monkeypatch.setenv("OPENCLAW_AGENT_DISPATCH_TIMEOUT_SECONDS", "75")
    monkeypatch.setattr(subprocess, "run", fake_run)
    get_settings.cache_clear()

    client = OpenClawHookClient()
    client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "support-agent",
            "session_key": "ticket-1001",
            "message": "請整理客服需求",
        },
    )

    assert captured["timeout"] == 75
    get_settings.cache_clear()


def test_dispatch_agent_allows_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        if command[1] == "agent":
            captured["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"status": "ok"}),
            stderr="",
        )

    monkeypatch.setenv("OPENCLAW_AGENT_DISPATCH_TIMEOUT_SECONDS", "75")
    monkeypatch.setattr(subprocess, "run", fake_run)
    get_settings.cache_clear()

    client = OpenClawHookClient()
    client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "daily-news-brief-agent",
            "session_key": "news-brief-001",
            "message": "請整理新聞",
            "timeout_seconds": 180,
        },
    )

    assert captured["timeout"] == 180
    get_settings.cache_clear()


def test_dispatch_agent_includes_dispatch_meta_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"status": "ok", "summary": "done"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "support-agent",
            "session_key": "ticket:1002",
            "message": "請整理客服需求",
        },
    )

    assert result["status"] == "ok"
    assert result["_dispatch_meta"]["returncode"] == 0
    assert isinstance(result["_dispatch_meta"]["duration_ms"], int)
    assert result["_dispatch_meta"]["timeout_seconds"] == client.timeout_seconds


def test_dispatch_agent_nonzero_exit_exposes_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="Profile minimax:cn timed out. Trying next account...",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    with pytest.raises(Exception) as exc_info:
        client.dispatch_agent(
            build_instance(),
            "gateway-token",
            {
                "agent_id": "main",
                "session_key": "ticket:1003",
                "message": "請整理客服需求",
            },
        )

    error = exc_info.value
    assert getattr(error, "metadata", {})["failure_kind"] == "embedded_model_timeout"
    assert getattr(error, "metadata", {})["returncode"] == 1
    assert "timed out" in getattr(error, "metadata", {})["stderr_preview"]


def test_dispatch_agent_recovers_missing_text_from_session_history(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1:3] == ["agent", "--agent"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "status": "ok",
                        "summary": "completed",
                        "result": {
                            "payloads": [],
                            "meta": {
                                "agentMeta": {
                                    "sessionId": "session-123",
                                    "provider": "minimax",
                                }
                            },
                        },
                    }
                ),
                stderr="",
            )

        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "history": [
                        {"role": "user", "content": "請產出系統巡檢報告"},
                        {"role": "assistant", "content": "{\"title\":\"系統巡檢與風險評估報告\"}"},
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "system-inspection-agent",
            "session_key": "run-report-session",
            "message": "請整理巡檢報告",
        },
    )

    assert result["result"]["payloads"][0]["text"] == "{\"title\":\"系統巡檢與風險評估報告\"}"
    assert any(command[1:4] == ["sessions", "history", "run-report-session"] for command in calls)


def test_dispatch_agent_recovers_prompt_aligned_text_from_reused_session_history(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        if command[1:3] == ["agent", "--agent"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "status": "ok",
                        "summary": "completed",
                        "result": {
                            "payloads": [],
                            "meta": {
                                "agentMeta": {
                                    "sessionId": "session-123",
                                    "provider": "minimax",
                                }
                            },
                        },
                    }
                ),
                stderr="",
            )

        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "history": [
                        {"role": "user", "content": "你是 System Inspection 的巡檢代理，請輸出 JSON 報告。"},
                        {"role": "assistant", "content": "{\"title\":\"系統巡檢與風險評估報告\"}"},
                        {"role": "user", "content": "你是 Daily News Brief 的簡報代理，請輸出今日新聞摘要。"},
                        {"role": "assistant", "content": "{\"title\":\"今日新聞簡報\",\"summary\":\"市場與 AI 動態整理完成\"}"},
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "daily-news-brief-agent",
            "session_key": "reused-session",
            "message": "你是 Daily News Brief 的簡報代理，請輸出今日新聞摘要。",
        },
    )

    assert result["result"]["payloads"][0]["text"] == "{\"title\":\"今日新聞簡報\",\"summary\":\"市場與 AI 動態整理完成\"}"


def test_dispatch_agent_does_not_recover_unrelated_text_when_prompt_does_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        if command[1:3] == ["agent", "--agent"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "status": "ok",
                        "summary": "completed",
                        "result": {
                            "payloads": [],
                            "meta": {
                                "agentMeta": {
                                    "sessionId": "session-123",
                                    "provider": "minimax",
                                }
                            },
                        },
                    }
                ),
                stderr="",
            )

        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "history": [
                        {"role": "user", "content": "你是 System Inspection 的巡檢代理，請輸出 JSON 報告。"},
                        {"role": "assistant", "content": "{\"title\":\"系統巡檢與風險評估報告\"}"},
                        {"role": "user", "content": "這是一段和目前任務無關的舊 prompt。"},
                        {"role": "assistant", "content": "{\"title\":\"舊的無關回覆\"}"},
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "daily-news-brief-agent",
            "session_key": "reused-session",
            "message": "你是 Daily News Brief 的簡報代理，請輸出今日新聞摘要。",
        },
    )

    assert result["result"]["payloads"] == []


def test_dispatch_agent_skips_session_history_when_text_payload_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "summary": "completed",
                    "result": {
                        "payloads": [{"text": "{\"title\":\"already there\"}"}],
                        "meta": {
                            "agentMeta": {
                                "sessionId": "session-123",
                                "provider": "minimax",
                            }
                        },
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "system-inspection-agent",
            "session_key": "run-report-session",
            "message": "請整理巡檢報告",
        },
    )

    assert result["result"]["payloads"][0]["text"] == "{\"title\":\"already there\"}"
    assert all(command[1] != "sessions" for command in calls)


def test_dispatch_agent_skips_session_history_when_result_output_text_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "summary": "completed",
                    "result": {
                        "payloads": [],
                        "output_text": "{\"title\":\"already there via output_text\"}",
                        "meta": {
                            "agentMeta": {
                                "sessionId": "session-123",
                                "provider": "minimax",
                            }
                        },
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "system-inspection-agent",
            "session_key": "run-report-session",
            "message": "請整理巡檢報告",
        },
    )

    assert result["result"]["output_text"] == "{\"title\":\"already there via output_text\"}"
    assert all(command[1] != "sessions" for command in calls)


def test_dispatch_agent_recovers_from_truncated_prompt_match_in_reused_session(monkeypatch: pytest.MonkeyPatch) -> None:
    long_prompt = (
        "你是 System Inspection 的版本檢查代理。"
        "請根據目前版本、CLI update summary、release context，"
        "輸出包含 current_version、latest_version、latest_version_status、"
        "version_gap、upgrade_recommendation、verification_steps 的 JSON。"
    )
    history_prompt = "請根據目前版本、CLI update summary、release context，輸出包含 current_version、latest_version、latest_version_status 的 JSON。"

    def fake_run(command, **kwargs):
        if command[1:3] == ["agent", "--agent"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "status": "ok",
                        "summary": "completed",
                        "result": {
                            "payloads": [],
                            "meta": {
                                "agentMeta": {
                                    "sessionId": "session-123",
                                    "provider": "minimax",
                                }
                            },
                        },
                    }
                ),
                stderr="",
            )

        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "history": [
                        {"role": "user", "content": "這是一段較舊的 Daily News prompt。"},
                        {"role": "assistant", "content": "{\"title\":\"舊的無關回覆\"}"},
                        {"role": "user", "content": history_prompt},
                        {"role": "assistant", "content": "{\"current_version\":\"OpenClaw 2026.4.2\",\"latest_version\":\"2026.4.5\"}"},
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = OpenClawHookClient()
    result = client.dispatch_agent(
        build_instance(),
        "gateway-token",
        {
            "agent_id": "system-inspection-agent",
            "session_key": "reused-session",
            "message": long_prompt,
        },
    )

    assert result["result"]["payloads"][0]["text"] == "{\"current_version\":\"OpenClaw 2026.4.2\",\"latest_version\":\"2026.4.5\"}"
