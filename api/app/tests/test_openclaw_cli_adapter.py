from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas.openclaw_instance import OpenClawInstanceResponse, OpenClawInstanceSnapshotSummary
from app.services.openclaw_cli_adapter import OpenClawCliAdapter


@pytest.fixture
def cli_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> OpenClawCliAdapter:
    # 把資料庫路徑導向暫存目錄，方便驗證 create_agent 會建立固定 workspace 路徑。
    monkeypatch.setenv("OPENCLAW_DATABASE_PATH", str(tmp_path / "openclaw.sqlite3"))
    monkeypatch.setenv("OPENCLAW_CLI_BIN", "openclaw")
    monkeypatch.setenv("OPENCLAW_CLI_TIMEOUT_SECONDS", "20")

    from app.config import get_settings

    get_settings.cache_clear()
    adapter = OpenClawCliAdapter()
    yield adapter
    get_settings.cache_clear()


def test_build_create_agent_args_for_openclaw_2026_4_1(cli_adapter: OpenClawCliAdapter, tmp_path: Path) -> None:
    # 建立 agent 應改走 `agents add --json --non-interactive --workspace ...`。
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    args = cli_adapter._build_create_agent_args(  # noqa: SLF001
        instance,
        {
            "name": "Escalation Agent",
            "metadata": {
                "model": "gpt-5.4-mini",
                "bindings": ["web", "slack:ops"],
            },
        },
    )

    assert args[:6] == [
        "agents",
        "add",
        "Escalation Agent",
        "--json",
        "--non-interactive",
        "--workspace",
    ]
    assert "--model" in args
    assert "gpt-5.4-mini" in args
    assert args.count("--bind") == 2
    workspace_index = args.index("--workspace") + 1
    workspace_path = Path(args[workspace_index])
    assert workspace_path == tmp_path / "openclaw_agents" / "oc_test" / "escalation-agent"
    assert workspace_path.exists()


def test_list_devices_flattens_pending_and_paired_groups(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # devices list 應把 2026.4.1 的 {pending, paired} 結構攤平成單一清單。
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    monkeypatch.setattr(
        cli_adapter,
        "_run_json_command",
        lambda instance, token, args: {  # noqa: ARG005
            "pending": [{"deviceId": "device_pending", "platform": "ios"}],
            "paired": [{"deviceId": "device_paired", "platform": "darwin"}],
        },
    )

    devices = cli_adapter.list_devices(instance, token="test-token")

    assert len(devices) == 2
    assert devices[0]["status"] == "pending"
    assert devices[0]["pending_action"] == "approve"
    assert devices[1]["status"] == "paired"


def test_set_config_uses_positional_value_and_strict_json(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # OpenClaw 2026.4.1 的 config set 走位置參數，不接受 --value。
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    captured_args: list[str] = []

    def fake_run_text_command(instance, token, args):  # noqa: ARG001
        captured_args[:] = args
        return "Updated agents. Restart the gateway to apply."

    monkeypatch.setattr(cli_adapter, "_run_text_command", fake_run_text_command)

    result = cli_adapter.set_config(instance, token="test-token", path="agents.default", value={"enabled": True})

    assert captured_args == [
        "config",
        "set",
        "agents.default",
        '{"enabled": true}',
        "--strict-json",
    ]
    assert result["value"] == {"enabled": True}
    assert "Restart the gateway" in result["message"]


def test_run_text_command_uses_explicit_gateway_args(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789/",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr("subprocess.run", fake_run)

    result = cli_adapter._run_text_command(instance, "gateway-token", ["cron", "list", "--json"])  # noqa: SLF001

    assert result == "ok"
    assert captured["command"] == [
        cli_adapter.binary,
        "cron",
        "list",
        "--json",
        "--url",
        "ws://127.0.0.1:18789",
        "--token",
        "gateway-token",
    ]


def test_add_cron_job_uses_single_payload_and_agent_owner(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    captured_args: list[str] = []

    def fake_run_json_command(instance, token, args):  # noqa: ARG001
        captured_args[:] = args
        return {"jobId": "job-1"}

    monkeypatch.setattr(cli_adapter, "_run_json_command", fake_run_json_command)

    result = cli_adapter.add_cron_job(
        instance,
        token="gateway-token",
        name="daily-news:oc_test",
        cron_expression="0 9 * * *",
        timezone="Asia/Tokyo",
        agent_id="daily-news-brief-agent",
        message="收集并整理每日新闻简报。",
        announce=True,
        channel="discord",
        to="1490256212229488742",
    )

    assert result == {"jobId": "job-1"}
    assert captured_args == [
        "cron",
        "add",
        "--json",
        "--name",
        "daily-news:oc_test",
        "--cron",
        "0 9 * * *",
        "--tz",
        "Asia/Tokyo",
        "--agent",
        "daily-news-brief-agent",
        "--message",
        "收集并整理每日新闻简报。",
        "--announce",
        "--channel",
        "discord",
        "--to",
        "1490256212229488742",
    ]


def test_edit_cron_job_drops_json_flag_for_current_cli(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    captured_args: list[str] = []

    def fake_run_text_command(instance, token, args):  # noqa: ARG001
        captured_args[:] = args
        return "updated"

    monkeypatch.setattr(cli_adapter, "_run_text_command", fake_run_text_command)

    result = cli_adapter.edit_cron_job(
        instance,
        token="gateway-token",
        job_id="job-1",
        name="daily-news:oc_test",
        cron_expression="0 9 * * *",
        timezone="Asia/Tokyo",
        agent_id="daily-news-brief-agent",
        message="收集并整理每日新闻简报。",
        announce=True,
        channel="discord",
        to="1490256212229488742",
    )

    assert result == {"message": "updated"}
    assert captured_args == [
        "cron",
        "edit",
        "job-1",
        "--name",
        "daily-news:oc_test",
        "--cron",
        "0 9 * * *",
        "--tz",
        "Asia/Tokyo",
        "--agent",
        "daily-news-brief-agent",
        "--message",
        "收集并整理每日新闻简报。",
        "--announce",
        "--channel",
        "discord",
        "--to",
        "1490256212229488742",
    ]


def test_list_cron_runs_reads_entries_without_json_flag(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    captured_args: list[str] = []

    def fake_run_json_command(instance, token, args):  # noqa: ARG001
        captured_args[:] = args
        return {"entries": [{"runId": "cron-run-1"}]}

    monkeypatch.setattr(cli_adapter, "_run_json_command", fake_run_json_command)

    result = cli_adapter.list_cron_runs(instance, token="gateway-token", job_id="job-1", limit=8)

    assert result == [{"runId": "cron-run-1"}]
    assert captured_args == [
        "cron",
        "runs",
        "--limit",
        "8",
        "--id",
        "job-1",
    ]


def test_validate_config_uses_dry_run_set_flow(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # validate 需改用 config set --dry-run，才能驗這次變更而不真正寫入。
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    captured_args: list[str] = []

    def fake_run_text_command(instance, token, args):  # noqa: ARG001
        captured_args[:] = args
        return "Dry run successful: 1 update(s) validated against ~/.openclaw/openclaw.json."

    monkeypatch.setattr(cli_adapter, "_run_text_command", fake_run_text_command)

    result = cli_adapter.validate_config(instance, token="test-token", path="agents.default", value={"enabled": False})

    assert captured_args == [
        "config",
        "set",
        "agents.default",
        '{"enabled": false}',
        "--strict-json",
        "--dry-run",
    ]
    assert result["valid"] is True
    assert result["messages"] == ["Dry run successful: 1 update(s) validated against ~/.openclaw/openclaw.json."]


def test_get_logs_parses_json_lines_output(
    cli_adapter: OpenClawCliAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # logs --json 應支援 NDJSON 風格輸出，而不是只接受單一 JSON。
    instance = OpenClawInstanceResponse(
        id="oc_test",
        name="Primary Gateway",
        gateway_url="http://127.0.0.1:18789",
        is_active=True,
        has_token=True,
        last_health_status=None,
        last_health_checked_at=None,
        snapshot_summary=OpenClawInstanceSnapshotSummary(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    monkeypatch.setattr(
        cli_adapter,
        "_run_text_command",
        lambda instance, token, args: "\n".join(  # noqa: ARG005
            [
                '{"type":"meta","file":"/tmp/openclaw.log","cursor":10}',
                '{"type":"log","time":"2026-04-02T17:26:55.845+09:00","level":"warn","message":"gateway already running"}',
            ]
        ),
    )

    logs = cli_adapter.get_logs(instance, token="test-token", limit=2)

    assert len(logs) == 2
    assert logs[0]["level"] == "meta"
    assert "cursor=10" in logs[0]["message"]
    assert logs[1]["level"] == "warn"
    assert logs[1]["message"] == "gateway already running"
