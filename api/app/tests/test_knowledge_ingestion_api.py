from __future__ import annotations

from fastapi.testclient import TestClient

from app.routers import knowledge, sources
from app.services.knowledge_ingestion_service import ExtractedWebDocument


def test_knowledge_ingest_persists_metadata_and_versions_endpoint(
    client: TestClient,
) -> None:
    def fake_fetch(url: str) -> ExtractedWebDocument:
        return ExtractedWebDocument(
            url=url,
            canonical_url=url,
            title="OpenClaw Security Update",
            text="OpenClaw security update improves workflow safety and support operations." * 8,
            preview="OpenClaw security update improves workflow safety.",
            mime_type="text/html",
            extension="html",
            file_size=2048,
            published_at="2026-04-05T10:00:00+00:00",
            language="en",
        )

    knowledge.knowledge_ingestion_service.fetcher.fetch = fake_fetch
    sources.indexing_service.knowledge_ingestion_service.fetcher.fetch = fake_fetch

    response = client.post(
        "/api/v1/knowledge/ingest",
        json={
            "topic": "OpenClaw 安全更新",
            "query": "OpenClaw security update",
            "source_name": "OpenClaw Security Feed",
            "source_type": "web_page",
            "urls": ["https://docs.openclaw.ai/security/update-1"],
            "keywords": ["security", "workflow"],
            "business_type": "security",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["accepted_count"] == 1
    assert payload["updated_count"] == 0
    assert payload["items"][0]["status"] == "inserted"

    document_id = payload["items"][0]["document_id"]
    search_response = client.post("/api/v1/search", json={"query": "workflow safety"})
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1
    item = search_response.json()["items"][0]
    assert item["source_url"] == "https://docs.openclaw.ai/security/update-1"
    assert item["canonical_url"] == "https://docs.openclaw.ai/security/update-1"
    assert item["business_type"] == "security"
    assert "OpenClaw 安全更新" in item["topic_tags"]
    assert item["credibility_tier"] == "high"

    versions_response = client.get(f"/api/v1/knowledge/documents/{document_id}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1


def test_knowledge_ingest_creates_new_version_when_content_changes(client: TestClient) -> None:
    responses = [
        ExtractedWebDocument(
            url="https://example.com/ops-guide",
            canonical_url="https://example.com/ops-guide",
            title="Ops Guide v1",
            text="Support operations guide with response playbook." * 8,
            preview="Support operations guide.",
            mime_type="text/html",
            extension="html",
            file_size=1024,
            published_at="2026-04-05T09:00:00+00:00",
            language="en",
        ),
        ExtractedWebDocument(
            url="https://example.com/ops-guide",
            canonical_url="https://example.com/ops-guide",
            title="Ops Guide v2",
            text="Support operations guide with updated escalation playbook and audit checklist." * 8,
            preview="Support operations guide updated.",
            mime_type="text/html",
            extension="html",
            file_size=2048,
            published_at="2026-04-05T12:00:00+00:00",
            language="en",
        ),
    ]

    def fake_fetch(_: str) -> ExtractedWebDocument:
        return responses.pop(0)

    knowledge.knowledge_ingestion_service.fetcher.fetch = fake_fetch

    first = client.post(
        "/api/v1/knowledge/ingest",
        json={
            "topic": "Support Guide",
            "query": "support guide",
            "source_name": "Support KB",
            "source_type": "web_page",
            "urls": ["https://example.com/ops-guide"],
            "business_type": "operations",
        },
    )
    assert first.status_code == 201
    source_id = first.json()["source_id"]
    original_document_id = first.json()["items"][0]["document_id"]

    second = client.post(
        "/api/v1/knowledge/ingest",
        json={
            "topic": "Support Guide",
            "query": "support guide",
            "source_id": source_id,
            "source_type": "web_page",
            "urls": ["https://example.com/ops-guide"],
            "business_type": "operations",
        },
    )
    assert second.status_code == 201
    assert second.json()["updated_count"] == 1
    updated_document_id = second.json()["items"][0]["document_id"]
    assert updated_document_id != original_document_id

    versions_response = client.get(f"/api/v1/knowledge/documents/{updated_document_id}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[0]["supersedes_document_id"] == original_document_id
    assert versions[1]["status"] == "superseded"


def test_external_source_scan_refreshes_via_knowledge_ingestion(client: TestClient) -> None:
    def fake_fetch(url: str) -> ExtractedWebDocument:
        return ExtractedWebDocument(
            url=url,
            canonical_url=url,
            title="Workflow Checklist",
            text="Workflow checklist for support team knowledge updates and routing rules." * 8,
            preview="Workflow checklist for support team.",
            mime_type="text/html",
            extension="html",
            file_size=1536,
            published_at="2026-04-05T08:00:00+00:00",
            language="en",
        )

    knowledge.knowledge_ingestion_service.fetcher.fetch = fake_fetch
    sources.indexing_service.knowledge_ingestion_service.fetcher.fetch = fake_fetch

    source_response = client.post(
        "/api/v1/sources",
        json={
            "name": "Support URL List",
            "type": "url_list",
            "config": {
                "urls": ["https://example.com/workflow-checklist"],
                "extra": {"business_type": "operations"},
            },
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    scan_response = client.post(f"/api/v1/sources/{source_id}/scan")
    assert scan_response.status_code == 200
    assert scan_response.json()["scanned_count"] == 1
    assert scan_response.json()["skipped_count"] == 0

    runs_response = client.get("/api/v1/knowledge/ingestion-runs", params={"source_id": source_id})
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) == 1
    assert runs[0]["source_id"] == source_id
    assert runs[0]["accepted_count"] == 1
