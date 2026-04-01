from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def write_source_file(source_root: Path, relative_path: str, content: str) -> None:
    # 測試資料直接寫進臨時來源資料夾，模擬真實掃描情境。
    target = source_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_local_source_scan_and_search_flow(client: TestClient, app_env: dict[str, Path]) -> None:
    # 驗證建立來源、掃描、全文搜索與文件詳情的 happy path。
    source_root = app_env["source_root"]
    write_source_file(source_root, "ops/weekly.md", "# 週會\nOpenClaw 本週完成搜索頁與摘要流程。")

    create_response = client.post(
        "/api/v1/sources/local",
        json={
            "name": "測試來源",
            "type": "local",
            "config": {"path": str(source_root)},
        },
    )
    assert create_response.status_code == 201
    source_id = create_response.json()["id"]

    scan_response = client.post(f"/api/v1/sources/{source_id}/scan")
    assert scan_response.status_code == 200
    assert scan_response.json()["scanned_count"] == 1

    search_response = client.post(
        "/api/v1/search",
        json={"query": "搜索頁", "source_id": source_id},
    )
    assert search_response.status_code == 200
    payload = search_response.json()
    assert payload["total"] == 1

    document_id = payload["items"][0]["document_id"]
    document_response = client.get(f"/api/v1/documents/{document_id}")
    assert document_response.status_code == 200
    assert "OpenClaw" in document_response.json()["extracted_text"]


def test_search_returns_empty_when_no_matches(client: TestClient, app_env: dict[str, Path]) -> None:
    # 無結果也是重要情境，前端需要依賴 total=0 做空狀態提示。
    source_root = app_env["source_root"]
    write_source_file(source_root, "finance.txt", "三月營收增加，但沒有提到法務。")

    source_response = client.post(
        "/api/v1/sources/local",
        json={
            "name": "財務來源",
            "type": "local",
            "config": {"path": str(source_root)},
        },
    )
    source_id = source_response.json()["id"]
    client.post(f"/api/v1/sources/{source_id}/scan")

    search_response = client.post("/api/v1/search", json={"query": "法遵風險"})
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 0

