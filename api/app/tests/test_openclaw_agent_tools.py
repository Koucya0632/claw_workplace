from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import get_settings
from app.repositories.document_repository import DocumentRepository, make_chunk_records, make_document_record
from app.repositories.openclaw_agent_capability_repository import OpenClawAgentCapabilityRepository
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.repositories.source_repository import SourceRepository
from app.routers import openclaw_agent_tools, openclaw_agents, openclaw_instances
from app.schemas.openclaw_instance import OpenClawInstanceSnapshotSummary, OpenClawInstanceResponse
from app.schemas.source import SourceConfig, SourceCreateRequest
from app.services.openclaw_agent_capability_service import OpenClawAgentCapabilityService
from app.services.openclaw_agent_tool_service import OpenClawAgentToolService
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.services.openclaw_service import OpenClawInstanceService, OpenClawManagementService


class MockCliAdapterWithNativePlugin:
    source_mode = "cli"

    def __init__(self) -> None:
        self.created_agents: list[dict[str, Any]] = []
        self.plugin_installed = False
        self.plugin_enabled = False
        self.global_config: dict[str, Any] = {
            "plugins": {
                "entries": {
                    "acpx": {
                        "enabled": True,
                        "config": {
                            "pluginToolsMcpBridge": False,
                        },
                    }
                }
            }
        }

    def get_health(self, instance, token: str | None) -> dict[str, Any]:
        return {"status": "healthy", "gateway_url": instance.gateway_url, "has_token": bool(token)}

    def list_agents(self, instance, token: str | None) -> list[dict[str, Any]]:
        # 測試替身需要模擬真實 CLI 的 workspace 欄位，Provisioner 才能真的落檔。
        support_agent = {
            "id": "support-agent",
            "name": "Support Agent",
            "status": "ready",
            "bindings": [],
            "workspace": str(self._workspace_for(instance.id, "support-agent")),
        }
        self._workspace_for(instance.id, "support-agent").mkdir(parents=True, exist_ok=True)

        dynamic_agents = []
        for agent in self.created_agents:
            if agent["instance_id"] != instance.id:
                continue
            workspace = self._workspace_for(instance.id, agent["id"])
            workspace.mkdir(parents=True, exist_ok=True)
            dynamic_agents.append(
                {
                    "id": agent["id"],
                    "name": agent["name"],
                    "status": "ready",
                    "bindings": [],
                    "workspace": str(workspace),
                }
            )

        return [support_agent, *dynamic_agents]

    def create_agent(self, instance, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["name"].strip().lower().replace(" ", "-")
        self.created_agents.append({"instance_id": instance.id, "id": agent_id, "name": payload["name"]})
        workspace = self._workspace_for(instance.id, agent_id)
        workspace.mkdir(parents=True, exist_ok=True)
        return {
            "id": agent_id,
            "name": payload["name"],
            "status": "ready",
            "bindings": [],
            "workspace": str(workspace),
        }

    def inspect_plugin(self, plugin_id: str) -> dict[str, Any]:
        if plugin_id != "project-search" or not self.plugin_installed:
            raise OpenClawServiceError("plugin not found", detail=f"unknown plugin: {plugin_id}", source_mode=self.source_mode)

        return {
            "plugin": {
                "id": plugin_id,
                "enabled": self.plugin_enabled,
                "status": "loaded" if self.plugin_enabled else "disabled",
            }
        }

    def install_plugin_link(self, plugin_path: Path) -> dict[str, Any]:
        self.plugin_installed = True
        self.global_config.setdefault("plugins", {}).setdefault("entries", {}).setdefault(
            "project-search",
            {"enabled": False, "config": {}},
        )
        return {"message": f"linked plugin {plugin_path.name}"}

    def enable_plugin(self, plugin_id: str) -> dict[str, Any]:
        self.plugin_installed = True
        self.plugin_enabled = True
        entry = self.global_config.setdefault("plugins", {}).setdefault("entries", {}).setdefault(
            plugin_id,
            {"enabled": False, "config": {}},
        )
        entry["enabled"] = True
        return {"message": f"enabled {plugin_id}"}

    def get_global_config(self, path: str) -> dict[str, Any]:
        try:
            return self._read_config_path(path)
        except KeyError as error:
            raise OpenClawServiceError(
                "OpenClaw CLI 執行失敗。",
                detail=f"Config path not found: {path}",
                source_mode=self.source_mode,
            ) from error

    def set_global_config(self, path: str, value: Any) -> dict[str, Any]:
        self._write_config_path(path, value)
        if path == "plugins.entries.project-search":
            self.plugin_enabled = bool(isinstance(value, dict) and value.get("enabled"))
        return {"message": f"updated {path}", "value": value}

    def _workspace_for(self, instance_id: str, agent_id: str) -> Path:
        settings = get_settings()
        return settings.database_file.parent / "openclaw_agents" / instance_id / agent_id

    def _read_config_path(self, path: str) -> dict[str, Any]:
        current: Any = self.global_config
        for segment in path.split("."):
            if not isinstance(current, dict) or segment not in current:
                raise KeyError(path)
            current = current[segment]
        if not isinstance(current, dict):
            raise KeyError(path)
        return current

    def _write_config_path(self, path: str, value: Any) -> None:
        current: Any = self.global_config
        segments = path.split(".")
        for segment in segments[:-1]:
            current = current.setdefault(segment, {})
        current[segments[-1]] = value


def install_openclaw_agent_tool_services() -> MockCliAdapterWithNativePlugin:
    repository = OpenClawInstanceRepository()
    capability_repository = OpenClawAgentCapabilityRepository()
    operation_log_repository = OpenClawOperationLogRepository()
    secret_cipher = OpenClawSecretCipher("test-openclaw-secret")
    cli_adapter = MockCliAdapterWithNativePlugin()

    openclaw_instances.instance_service = OpenClawInstanceService(
        repository=repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
    )
    openclaw_agents.management_service = OpenClawManagementService(
        repository=repository,
        capability_repository=capability_repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
    )
    openclaw_agents.capability_service = OpenClawAgentCapabilityService(
        repository=repository,
        capability_repository=capability_repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
    )
    openclaw_agent_tools.agent_tool_service = OpenClawAgentToolService(
        repository=repository,
        operation_log_repository=operation_log_repository,
        capability_service=openclaw_agents.capability_service,
    )

    return cli_adapter


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
    return response.json()["data"]["id"]


def create_searchable_document() -> str:
    source = SourceRepository().create(
        SourceCreateRequest(
            name="Support Docs",
            type="local",
            config=SourceConfig(path="./samples/local_source"),
        )
    )
    record = make_document_record(
        source_id=source.id,
        relative_path="support/invoice-notes.md",
        filename="invoice-notes.md",
        extension="md",
        mime_type="text/markdown",
        file_size=128,
        checksum="checksum-demo",
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_preview="Invoice dispute notes",
        extracted_text="Invoice dispute notes for customer Alpha. Refund approved after checking invoice 2026-Q2.",
        chunks=make_chunk_records("Invoice dispute notes for customer Alpha. Refund approved after checking invoice 2026-Q2."),
    )
    DocumentRepository().replace_for_source(source.id, [record])
    return record["id"]


def test_enable_and_disable_search_capability_syncs_native_plugin_and_cleans_legacy_files(client: TestClient) -> None:
    cli_adapter = install_openclaw_agent_tool_services()
    instance_id = create_instance(client)
    workspace = cli_adapter._workspace_for(instance_id, "support-agent")
    support_dir = workspace / ".openclaw-smart-office"
    support_dir.mkdir(parents=True, exist_ok=True)
    (support_dir / "project_search.py").write_text("# legacy bridge\n", encoding="utf-8")
    (support_dir / "search-config.json").write_text("{}", encoding="utf-8")
    (workspace / "SEARCH_API.md").write_text("legacy docs\n", encoding="utf-8")
    (workspace / "TOOLS.md").write_text(
        "# TOOLS.md - Local Notes\n\nmy custom note\n\n"
        "<!-- OPENCLAW-SMART-OFFICE:SEARCH_API:START -->\nlegacy block\n<!-- OPENCLAW-SMART-OFFICE:SEARCH_API:END -->\n",
        encoding="utf-8",
    )

    enable_response = client.post(
        "/api/v1/openclaw/agents/support-agent/capabilities/search",
        json={"instance_id": instance_id, "enabled": True},
    )
    assert enable_response.status_code == 200
    payload = enable_response.json()["data"]
    assert payload["is_enabled"] is True
    assert payload["native_plugin_id"] == "project-search"
    assert payload["native_plugin_ready"] is True
    assert payload["native_plugin_enabled"] is True
    assert payload["bridge_ready"] is True
    assert "原生搜索工具已就緒" in payload["message"]

    capability_list_response = client.get(
        f"/api/v1/openclaw/agents/support-agent/capabilities",
        params={"instanceId": instance_id},
    )
    assert capability_list_response.status_code == 200
    assert capability_list_response.json()["data"][0]["capability_key"] == "search_api"

    tools_text = (workspace / "TOOLS.md").read_text(encoding="utf-8")
    assert "my custom note" in tools_text
    assert "legacy block" not in tools_text
    assert not (workspace / "SEARCH_API.md").exists()
    assert not (workspace / ".openclaw-smart-office" / "project_search.py").exists()
    assert not (workspace / ".openclaw-smart-office" / "search-config.json").exists()

    assert cli_adapter.plugin_installed is True
    assert cli_adapter.plugin_enabled is True
    project_plugin = cli_adapter.global_config["plugins"]["entries"]["project-search"]
    assert project_plugin["enabled"] is True
    assert project_plugin["config"]["enabledAgents"] == ["support-agent"]
    assert project_plugin["config"]["apiBaseUrl"] == get_settings().openclaw_agent_tool_api_base_url_resolved
    assert cli_adapter.global_config["plugins"]["entries"]["acpx"]["config"]["pluginToolsMcpBridge"] is True

    agents_response = client.get("/api/v1/openclaw/agents", params={"instanceId": instance_id})
    support_agent = agents_response.json()["data"][0]
    assert support_agent["metadata"]["capabilities"]["search_api"]["enabled"] is True
    assert support_agent["metadata"]["capabilities"]["search_api"]["plugin_ready"] is True
    assert support_agent["metadata"]["capabilities"]["search_api"]["bridge_ready"] is True

    disable_response = client.post(
        "/api/v1/openclaw/agents/support-agent/capabilities/search",
        json={"instance_id": instance_id, "enabled": False},
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["data"]["is_enabled"] is False
    assert cli_adapter.global_config["plugins"]["entries"]["project-search"]["config"]["enabledAgents"] == []


def test_agent_tool_bridge_requires_enabled_capability(client: TestClient) -> None:
    install_openclaw_agent_tool_services()
    create_instance(client)

    response = client.post(
        "/api/v1/openclaw/agent-tools/search",
        json={
            "agent_id": "support-agent",
            "session_id": "ticket-1001",
            "query": "invoice",
        },
    )
    assert response.status_code == 403
    assert "尚未開啟搜索能力" in response.json()["error"]["message"]


def test_agent_tool_bridge_searches_documents_and_truncates_content(client: TestClient) -> None:
    install_openclaw_agent_tool_services()
    instance_id = create_instance(client)
    document_id = create_searchable_document()

    capability_response = client.post(
        "/api/v1/openclaw/agents/support-agent/capabilities/search",
        json={"instance_id": instance_id, "enabled": True, "config": {"limit": 1, "max_chars": 20}},
    )
    assert capability_response.status_code == 200

    search_response = client.post(
        "/api/v1/openclaw/agent-tools/search",
        json={
            "agent_id": "support-agent",
            "session_id": "ticket-1001",
            "query": "Invoice",
        },
    )
    assert search_response.status_code == 200
    search_payload = search_response.json()["data"]
    assert search_payload["query"] == "Invoice"
    assert search_payload["total"] == 1
    assert search_payload["items"][0]["document_id"] == document_id

    document_response = client.post(
        "/api/v1/openclaw/agent-tools/document",
        json={
            "agent_id": "support-agent",
            "session_id": "ticket-1001",
            "document_id": document_id,
        },
    )
    assert document_response.status_code == 200
    document_payload = document_response.json()["data"]
    assert document_payload["document"]["id"] == document_id
    assert document_payload["truncated"] is True
    assert document_payload["returned_chars"] == 20

    operations_response = client.get("/api/v1/openclaw/operations", params={"instanceId": instance_id, "limit": 20})
    operation_types = {item["operation_type"] for item in operations_response.json()["data"]}
    assert "agent_search" in operation_types
    assert "agent_get_document" in operation_types


def test_search_capability_rejects_cross_instance_duplicate_agent_id(client: TestClient) -> None:
    install_openclaw_agent_tool_services()
    first_instance_id = create_instance(client)
    second_instance_response = client.post(
        "/api/v1/openclaw/instances",
        json={
            "name": "Secondary Gateway",
            "gateway_url": "http://gateway.backup",
            "token": "secondary-secret-token",
            "is_active": True,
        },
    )
    assert second_instance_response.status_code == 201
    second_instance_id = second_instance_response.json()["data"]["id"]

    first_enable = client.post(
        "/api/v1/openclaw/agents/support-agent/capabilities/search",
        json={"instance_id": first_instance_id, "enabled": True},
    )
    assert first_enable.status_code == 200

    conflicting_enable = client.post(
        "/api/v1/openclaw/agents/support-agent/capabilities/search",
        json={"instance_id": second_instance_id, "enabled": True},
    )
    assert conflicting_enable.status_code == 409
    assert "不同 Instance" in conflicting_enable.json()["error"]["message"]
