from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def write_source_file(source_root: Path, relative_path: str, content: str) -> None:
    target = source_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_source_management_summary_detail_and_activity(client: TestClient, app_env: dict[str, Path]) -> None:
    source_root = app_env["source_root"]
    write_source_file(source_root, "ops/weekly.md", "# 週會\nOpenClaw source dashboard 上線。")

    create_response = client.post(
        "/api/v1/sources/local",
        json={
            "name": "管理頁測試來源",
            "type": "local",
            "config": {"path": str(source_root)},
        },
    )
    assert create_response.status_code == 201
    source_id = create_response.json()["id"]

    summary_before_scan = client.get("/api/v1/sources/summary")
    assert summary_before_scan.status_code == 200
    assert summary_before_scan.json()["total_sources"] == 1

    scan_response = client.post(f"/api/v1/sources/{source_id}/scan")
    assert scan_response.status_code == 200
    assert scan_response.json()["scanned_count"] == 1

    detail_response = client.get(f"/api/v1/sources/{source_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["document_count"] == 1
    assert detail_payload["last_sync_status"] == "healthy"
    assert len(detail_payload["recent_activity"]) >= 2

    activity_response = client.get(f"/api/v1/sources/{source_id}/activity")
    assert activity_response.status_code == 200
    activity_payload = activity_response.json()
    assert activity_payload[0]["status"] in {"healthy", "warning"}


def test_source_list_filters_and_disable_delete_flow(client: TestClient, app_env: dict[str, Path]) -> None:
    source_root = app_env["source_root"]
    write_source_file(source_root, "engineering/notes.md", "support-agent 已可管理資料源。")

    source_response = client.post(
        "/api/v1/sources/local",
        json={
            "name": "Support Agent Local",
            "type": "local",
            "config": {"path": str(source_root)},
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    client.post(f"/api/v1/sources/{source_id}/scan")

    filtered_response = client.get("/api/v1/sources?q=support&status=healthy&sort=name&order=asc")
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert len(filtered_payload) == 1
    assert filtered_payload[0]["name"] == "Support Agent Local"

    disable_response = client.post(f"/api/v1/sources/{source_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["is_enabled"] is False

    disabled_only_response = client.get("/api/v1/sources?status=disabled")
    assert disabled_only_response.status_code == 200
    assert len(disabled_only_response.json()) == 1

    delete_response = client.delete(f"/api/v1/sources/{source_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/sources")
    assert list_response.status_code == 200
    assert list_response.json() == []
