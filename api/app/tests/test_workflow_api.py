from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.repositories.openclaw_workflow_config_repository import OpenClawWorkflowConfigRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.routers import openclaw_instances, openclaw_workflow_config, workflows
from app.schemas.openclaw_instance import OpenClawInstanceSnapshotSummary, OpenClawInstanceResponse
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.services.openclaw_service import OpenClawInstanceService
from app.services.workflow_service import OpenClawWorkflowConfigService, SearchReportWorkflowService


class MockWorkflowCliAdapter:
    source_mode = "cli"

    def list_agents(self, instance, token: str | None) -> list[dict[str, Any]]:
        return [
            {"id": "search-agent", "name": "Search Agent", "status": "ready"},
            {"id": "analysis-agent", "name": "Analysis Agent", "status": "ready"},
            {"id": "report-agent", "name": "Report Agent", "status": "ready"},
        ]


class MockWorkflowHookClient:
    source_mode = "cli"

    def dispatch_agent(self, instance, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        stage_key = payload["metadata"]["stage_key"]

        if stage_key == "search":
            text = json.dumps(
                {
                    "summary": "已找到客服相關文件。",
                    "candidates": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "relative_path": "support/support-package.md",
                            "source_id": "src_1",
                            "source_name": "Support Docs",
                            "snippet": "這是一份關於包的客服說明",
                            "reason": "直接命中查詢關鍵字",
                        }
                    ],
                    "selected_documents": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "relative_path": "support/support-package.md",
                            "source_id": "src_1",
                            "source_name": "Support Docs",
                            "snippet": "這是一份關於包的客服說明",
                            "reason": "內容最完整",
                        }
                    ],
                    "source_overview": ["Support Docs 提供最完整的客服上下文。"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "analysis":
            text = json.dumps(
                {
                    "summary": "分析顯示使用者想找的是與『包』相關的客服說明與處理方式。",
                    "highlights": ["文件已說明處理步驟。"],
                    "risks": ["若只看單一文件可能漏掉限制條件。"],
                    "todos": ["確認是否需要補充最新政策。"],
                    "evidence": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "quote": "這是一份關於包的客服說明",
                            "reason": "直接支持主要結論",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        else:
            text = json.dumps(
                {
                    "title": "『包』相關客服工作報告",
                    "executive_summary": "已完成搜索、分析與報告整理。",
                    "highlights": ["已找到最相關來源。"],
                    "recommendations": ["優先引用 support-package.md。"],
                    "evidence": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "quote": "這是一份關於包的客服說明",
                            "reason": "主要證據來源",
                        }
                    ],
                    "sections": [
                        {
                            "title": "搜索結果",
                            "summary": "已定位到主要客服文件。",
                            "bullets": ["搜尋到 1 份核心文件"],
                            "body": "文件內容足以支撐第一版報告。",
                        }
                    ],
                    "appendix": ["workflow 由三個 OpenClaw agents 串行完成。"],
                    "markdown": "# 『包』相關客服工作報告\n\n已完成搜索、分析與報告整理。\n",
                },
                ensure_ascii=False,
            )

        return {
            "runId": f"run-{stage_key}",
            "status": "ok",
            "summary": "completed",
            "result": {
                "payloads": [
                    {
                        "text": text,
                    }
                ]
            },
        }


def install_workflow_services() -> None:
    repository = OpenClawInstanceRepository()
    workflow_repository = WorkflowRepository()
    workflow_config_repository = OpenClawWorkflowConfigRepository()
    operation_log_repository = OpenClawOperationLogRepository()
    secret_cipher = OpenClawSecretCipher("test-openclaw-secret")
    cli_adapter = MockWorkflowCliAdapter()
    hook_client = MockWorkflowHookClient()

    openclaw_instances.instance_service = OpenClawInstanceService(
        repository=repository,
        operation_log_repository=operation_log_repository,
        secret_cipher=secret_cipher,
    )
    openclaw_workflow_config.workflow_config_service = OpenClawWorkflowConfigService(
        repository=repository,
        workflow_config_repository=workflow_config_repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
    )
    workflows.workflow_service = SearchReportWorkflowService(
        repository=repository,
        workflow_repository=workflow_repository,
        workflow_config_repository=workflow_config_repository,
        operation_log_repository=operation_log_repository,
        hook_client=hook_client,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
        run_inline=True,
    )


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


def test_workflow_run_happy_path(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    config_response = client.post(
        "/api/v1/openclaw/workflow-config",
        json={
            "instance_id": instance_id,
            "search_agent_id": "search-agent",
            "analysis_agent_id": "analysis-agent",
            "report_agent_id": "report-agent",
        },
    )
    assert config_response.status_code == 200

    create_response = client.post(
        "/api/v1/workflows/search-report",
        json={"instance_id": instance_id, "query": "包"},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["status"] == "completed"
    assert payload["overall_progress_percent"] == 100
    assert payload["final_report"]["title"] == "『包』相關客服工作報告"
    assert [stage["stage_key"] for stage in payload["stages"]] == ["search", "analysis", "report"]
    assert all(stage["status"] == "completed" for stage in payload["stages"])
    assert any(event["message"] == "搜索資料中..." for event in payload["events"])
    assert any(event["message"] == "正在分析重點..." for event in payload["events"])
    assert any(event["message"] == "完整報告已生成，可回看全鏈路與匯出 Markdown。" for event in payload["events"])

    get_response = client.get(f"/api/v1/workflows/{payload['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == payload["id"]

    list_response = client.get("/api/v1/workflows", params={"instanceId": instance_id})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_workflow_run_requires_config(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    response = client.post(
        "/api/v1/workflows/search-report",
        json={"instance_id": instance_id, "query": "包"},
    )
    assert response.status_code == 400
    assert "尚未設定搜索、分析、報告三階段 agent" in response.json()["detail"]
