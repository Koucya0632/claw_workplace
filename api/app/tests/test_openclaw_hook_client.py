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


def test_dispatch_agent_uses_env_gateway_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
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
    assert captured["env"]["OPENCLAW_GATEWAY_URL"] == "http://127.0.0.1:18789"
    assert captured["env"]["OPENCLAW_GATEWAY_TOKEN"] == "gateway-token"


def test_dispatch_agent_uses_dedicated_dispatch_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
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
