from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.providers.mock import MockLLMProvider
from app.routers import tasks
from app.services.summary_service import SummaryService


class FailingProvider(MockLLMProvider):
    # 失敗版 provider 用來驗證任務錯誤狀態與重試入口是否有資料可依據。
    async def summarize_document(self, document_title: str, document_text: str) -> dict:
        raise RuntimeError("MiniMax timeout")


def seed_scanned_document(client: TestClient, source_root: Path) -> str:
    # 先建立一個已掃描文件，讓摘要與報告測試可以重複使用。
    target = source_root / "meeting.txt"
    target.write_text("待辦：整理報告\n結論：先完成本地 MVP。", encoding="utf-8")

    source_response = client.post(
        "/api/v1/sources/local",
        json={
            "name": "會議來源",
            "type": "local",
            "config": {"path": str(source_root)},
        },
    )
    source_id = source_response.json()["id"]
    client.post(f"/api/v1/sources/{source_id}/scan")

    search_response = client.post("/api/v1/search", json={"query": "待辦"})
    return search_response.json()["items"][0]["document_id"]


def test_summary_task_and_markdown_export(client: TestClient, app_env: dict[str, Path]) -> None:
    # 成功路徑要涵蓋任務事件、摘要結果與 Markdown 匯出。
    tasks.task_orchestrator.summary_service = SummaryService(MockLLMProvider())
    document_id = seed_scanned_document(client, app_env["source_root"])

    task_response = client.post("/api/v1/tasks/summary", json={"document_id": document_id})
    assert task_response.status_code == 201
    task_payload = task_response.json()
    assert task_payload["status"] == "completed"
    assert len(task_payload["events"]) >= 3

    report_response = client.post("/api/v1/reports/markdown", json={"task_id": task_payload["id"]})
    assert report_response.status_code == 200
    assert report_response.json()["filename"].endswith(".md")


def test_summary_task_returns_failed_status_when_provider_breaks(
    client: TestClient,
    app_env: dict[str, Path],
) -> None:
    # 失敗時仍應保存 task 與 failed 狀態，前端才能顯示可重試入口。
    tasks.task_orchestrator.summary_service = SummaryService(FailingProvider())
    document_id = seed_scanned_document(client, app_env["source_root"])

    task_response = client.post("/api/v1/tasks/summary", json={"document_id": document_id})
    assert task_response.status_code == 201
    assert task_response.json()["status"] == "failed"
    assert "MiniMax timeout" in task_response.json()["error_message"]

