from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.routers import (
    openclaw_agents,
    openclaw_config,
    openclaw_devices,
    openclaw_hooks,
    openclaw_instances,
    openclaw_logs,
)
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_hook_service import OpenClawHookService
from app.services.openclaw_hook_client import OpenClawHookClient
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.services.openclaw_service import OpenClawInstanceService, OpenClawManagementService


class MockOpenClawCliAdapter:
    # mock adapter 讓測試聚焦在本專案的封裝與審計，不依賴本機安裝真實 CLI。
    source_mode = "cli"

    def __init__(self) -> None:
        self.fail_health = False
        self.fail_device_action: str | None = None
        self.last_created_agent_payload: dict[str, Any] | None = None
        self.agents = [
            {"id": "agent_support", "name": "Support Agent", "status": "ready", "bindings": ["web", "email"]}
        ]
        self.devices = [
            {"deviceId": "device_pending", "status": "pending", "platform": "ios", "clientId": "cli", "clientMode": "cli"},
            {
                "deviceId": "device_paired",
                "status": "paired",
                "platform": "darwin",
                "clientId": "openclaw-control-ui",
                "clientMode": "webchat",
            },
        ]

    def get_health(self, instance, token: str | None) -> dict[str, Any]:
        if self.fail_health:
            raise OpenClawServiceError("OpenClaw CLI 執行失敗。", detail="gateway offline", source_mode=self.source_mode)
        return {"status": "healthy", "gateway_url": instance.gateway_url, "has_token": bool(token)}

    def list_agents(self, instance, token: str | None) -> list[dict[str, Any]]:
        return self.agents

    def create_agent(self, instance, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_created_agent_payload = payload
        return {"id": "agent_new", "name": payload["name"], "status": "ready", "bindings": []}

    def list_devices(self, instance, token: str | None) -> list[dict[str, Any]]:
        return self.devices

    def approve_device(self, instance, token: str | None, device_id: str) -> dict[str, Any]:
        return self._device_action("approve", device_id)

    def reject_device(self, instance, token: str | None, device_id: str) -> dict[str, Any]:
        return self._device_action("reject", device_id)

    def revoke_device(self, instance, token: str | None, device_id: str) -> dict[str, Any]:
        return self._device_action("revoke", device_id)

    def get_config(self, instance, token: str | None, path: str) -> dict[str, Any]:
        return {"value": {"path": path, "enabled": True}}

    def set_config(self, instance, token: str | None, path: str, value: Any) -> dict[str, Any]:
        return {"value": value}

    def validate_config(self, instance, token: str | None, path: str, value: Any) -> dict[str, Any]:
        return {"valid": True, "messages": [f"{path} is valid"]}

    def get_logs(self, instance, token: str | None, limit: int) -> list[dict[str, Any]]:
        return [{"timestamp": "2026-04-02T00:00:00+00:00", "level": "info", "message": f"log limit={limit}"}]

    def _device_action(self, action: str, device_id: str) -> dict[str, Any]:
        if self.fail_device_action == action:
            raise OpenClawServiceError(
                "OpenClaw CLI 執行失敗。",
                detail=f"{action} failed for {device_id}",
                source_mode=self.source_mode,
            )
        return {"status": "ok", "action": action, "device_id": device_id}


class MockOpenClawHookClient(OpenClawHookClient):
    source_mode = "cli"

    def __init__(self) -> None:
        self.last_agent_payload: dict[str, Any] | None = None
        self.last_wake_payload: dict[str, Any] | None = None

    def dispatch_agent(self, instance, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_agent_payload = payload
        return {"status": "accepted", "task_id": "agent_turn_1", "accepted": True, "session_id": payload["session_key"]}

    def dispatch_wake(self, instance, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_wake_payload = payload
        raise OpenClawServiceError(
            "目前這個 OpenClaw 版本未提供可用的 wake 派發入口。",
            detail="請改用 `openclaw agent` 或在管理台使用 Agent Hook。Wake Hook 已暫時停用。",
            status_code=501,
            source_mode=self.source_mode,
        )


def install_mock_openclaw_services() -> tuple[MockOpenClawCliAdapter, MockOpenClawHookClient]:
    repository = OpenClawInstanceRepository()
    operation_log_repository = OpenClawOperationLogRepository()
    secret_cipher = OpenClawSecretCipher("test-openclaw-secret")
    cli_adapter = MockOpenClawCliAdapter()
    hook_client = MockOpenClawHookClient()

    openclaw_instances.instance_service = OpenClawInstanceService(
        repository=repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
    )
    management_service = OpenClawManagementService(
        repository=repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
    )
    openclaw_agents.management_service = management_service
    openclaw_devices.management_service = management_service
    openclaw_config.management_service = management_service
    openclaw_logs.management_service = management_service
    openclaw_hooks.hook_service = OpenClawHookService(
        repository=repository,
        operation_log_repository=operation_log_repository,
        hook_client=hook_client,
        secret_cipher=secret_cipher,
    )

    return cli_adapter, hook_client


def create_instance(client: TestClient) -> str:
    response = client.post(
        "/api/v1/openclaw/instances",
        json={
            "name": "Primary Gateway",
            "gateway_url": "http://gateway.internal",
            "token": "super-secret-token",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert "token" not in payload["data"]
    assert payload["data"]["has_token"] is True
    return payload["data"]["id"]


def test_openclaw_instance_health_and_snapshots(client: TestClient) -> None:
    cli_adapter, _ = install_mock_openclaw_services()
    instance_id = create_instance(client)

    list_response = client.get("/api/v1/openclaw/instances")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["success"] is True
    assert "super-secret-token" not in str(list_payload)

    health_response = client.get(f"/api/v1/openclaw/instances/{instance_id}/health")
    assert health_response.status_code == 200
    assert health_response.json()["data"]["status"] == "healthy"

    agents_response = client.get("/api/v1/openclaw/agents", params={"instanceId": instance_id})
    assert agents_response.status_code == 200
    devices_response = client.get("/api/v1/openclaw/devices", params={"instanceId": instance_id})
    assert devices_response.status_code == 200
    assert {item["status"] for item in devices_response.json()["data"]} == {"pending", "paired"}
    assert {item["id"] for item in devices_response.json()["data"]} == {"device_pending", "device_paired"}

    refreshed_instances = client.get("/api/v1/openclaw/instances").json()["data"]
    assert refreshed_instances[0]["snapshot_summary"]["agent_count"] == len(cli_adapter.agents)
    assert refreshed_instances[0]["snapshot_summary"]["device_count"] == 2

    operations_response = client.get("/api/v1/openclaw/operations", params={"limit": 10})
    assert operations_response.status_code == 200
    assert any(item["operation_type"] == "health_check" for item in operations_response.json()["data"])
    assert "super-secret-token" not in str(operations_response.json())


def test_openclaw_health_failure_records_failed_operation(client: TestClient) -> None:
    cli_adapter, _ = install_mock_openclaw_services()
    cli_adapter.fail_health = True
    instance_id = create_instance(client)

    response = client.get(f"/api/v1/openclaw/instances/{instance_id}/health")
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["detail"] == "gateway offline"

    operations_response = client.get("/api/v1/openclaw/operations", params={"instanceId": instance_id, "limit": 10})
    failed_operations = operations_response.json()["data"]
    assert any(item["status"] == "failed" and item["operation_type"] == "health_check" for item in failed_operations)


def test_openclaw_management_routes_and_hooks(client: TestClient) -> None:
    cli_adapter, hook_client = install_mock_openclaw_services()
    instance_id = create_instance(client)

    agents_response = client.get("/api/v1/openclaw/agents", params={"instanceId": instance_id})
    assert agents_response.status_code == 200
    assert agents_response.json()["data"][0]["name"] == "Support Agent"

    create_agent_response = client.post(
        "/api/v1/openclaw/agents",
        json={"instance_id": instance_id, "name": "Escalation Agent", "role_hint": "operator"},
    )
    assert create_agent_response.status_code == 201
    assert cli_adapter.last_created_agent_payload is not None
    assert cli_adapter.last_created_agent_payload["name"] == "Escalation Agent"

    config_response = client.get("/api/v1/openclaw/config", params={"instanceId": instance_id, "path": "agents.default"})
    assert config_response.status_code == 200
    assert config_response.json()["data"]["path"] == "agents.default"

    validate_response = client.post(
        "/api/v1/openclaw/config/validate",
        json={"instance_id": instance_id, "path": "agents.default", "value": {"enabled": True}},
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["data"]["valid"] is True

    set_response = client.post(
        "/api/v1/openclaw/config/set",
        json={"instance_id": instance_id, "path": "agents.default", "value": {"enabled": False}},
    )
    assert set_response.status_code == 200
    assert set_response.json()["data"]["value"]["enabled"] is False

    logs_response = client.get("/api/v1/openclaw/logs", params={"instanceId": instance_id, "limit": 25})
    assert logs_response.status_code == 200
    assert "limit=25" in logs_response.json()["data"][0]["message"]

    agent_hook_response = client.post(
        "/api/v1/openclaw/hooks/agent",
        json={
            "instance_id": instance_id,
            "agent_id": "agent_support",
            "session_key": "ticket:1001",
            "message": "請整理內容",
            "metadata": {"priority": "high"},
        },
    )
    assert agent_hook_response.status_code == 200
    assert hook_client.last_agent_payload == {
        "agent_id": "agent_support",
        "session_key": "ticket:1001",
        "message": "請整理內容",
        "deliver": True,
        "channel": None,
        "to": None,
        "metadata": {"priority": "high"},
    }

    wake_hook_response = client.post(
        "/api/v1/openclaw/hooks/wake",
        json={
            "instance_id": instance_id,
            "agent_id": "agent_support",
            "session_key": "ticket:1001",
            "metadata": {"source": "manual"},
        },
    )
    assert wake_hook_response.status_code == 501
    assert "wake 派發入口" in wake_hook_response.json()["error"]["message"]


def test_openclaw_device_error_surfaces_cli_detail(client: TestClient) -> None:
    cli_adapter, _ = install_mock_openclaw_services()
    cli_adapter.fail_device_action = "approve"
    instance_id = create_instance(client)

    response = client.post(
        "/api/v1/openclaw/devices/device_pending/approve",
        json={"instance_id": instance_id},
    )
    assert response.status_code == 400
    assert response.json()["error"]["detail"] == "approve failed for device_pending"


def test_openclaw_unknown_instance_returns_not_found(client: TestClient) -> None:
    install_mock_openclaw_services()

    response = client.get("/api/v1/openclaw/agents", params={"instanceId": "oc_missing"})
    assert response.status_code == 404
    assert response.json()["success"] is False
