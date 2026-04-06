from __future__ import annotations

import sqlite3
from collections import OrderedDict
from datetime import datetime
from typing import Any

from app.repositories.database import adapt_json, get_connection
from app.schemas.search import DocumentSummary, DocumentVersionSummary, SearchRequest, SearchResponse, SearchResultItem
from app.utils import json_loads, new_id, utc_now_iso


class DocumentRepository:
    # DocumentRepository 管理文件、chunk 與 FTS 索引。
    def replace_for_source(self, source_id: str, documents: list[dict[str, Any]]) -> None:
        with get_connection() as connection:
            existing_rows = connection.execute(
                "SELECT id FROM documents WHERE source_id = ?",
                (source_id,),
            ).fetchall()
            existing_ids = [row["id"] for row in existing_rows]

            # 先刪除舊的 FTS 與 chunk，再刪文件主表，確保重掃結果不會殘留舊內容。
            if existing_ids:
                placeholders = ",".join("?" for _ in existing_ids)
                connection.execute(
                    f"DELETE FROM document_chunks_fts WHERE document_id IN ({placeholders})",
                    existing_ids,
                )
                connection.execute(
                    f"DELETE FROM document_chunks WHERE document_id IN ({placeholders})",
                    existing_ids,
                )
                connection.execute(
                    "DELETE FROM documents WHERE source_id = ?",
                    (source_id,),
                )

            # 逐筆寫入 document 與 chunk，Phase 1 的資料量可接受這種清楚直接的流程。
            for document in documents:
                connection.execute(
                    """
                    INSERT INTO documents (
                        id, source_id, relative_path, filename, extension, mime_type, file_size,
                        checksum, modified_at, indexed_at, content_preview, extracted_text,
                        document_kind, source_url, canonical_url, published_at, language, status,
                        trust_score, relevance_score, duplicate_group_id, business_type, metadata_json,
                        version_group_id, version_number, supersedes_document_id, first_seen_at, last_seen_at,
                        last_checked_at, created_by, updated_by, role_hint
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document["id"],
                        source_id,
                        document["relative_path"],
                        document["filename"],
                        document["extension"],
                        document["mime_type"],
                        document["file_size"],
                        document["checksum"],
                        document["modified_at"],
                        document["indexed_at"],
                        document["content_preview"],
                        document["extracted_text"],
                        document.get("document_kind", "local_file"),
                        document.get("source_url"),
                        document.get("canonical_url"),
                        document.get("published_at"),
                        document.get("language"),
                        document.get("status", "active"),
                        document.get("trust_score"),
                        document.get("relevance_score"),
                        document.get("duplicate_group_id"),
                        document.get("business_type"),
                        adapt_json(document.get("metadata", {})),
                        document.get("version_group_id"),
                        document.get("version_number", 1),
                        document.get("supersedes_document_id"),
                        document.get("first_seen_at"),
                        document.get("last_seen_at"),
                        document.get("last_checked_at"),
                        "system",
                        "system",
                        "member",
                    ),
                )

                for chunk in document["chunks"]:
                    connection.execute(
                        """
                        INSERT INTO document_chunks (id, document_id, chunk_index, content, token_count, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk["id"],
                            document["id"],
                            chunk["chunk_index"],
                            chunk["content"],
                            chunk["token_count"],
                            utc_now_iso(),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO document_chunks_fts (chunk_id, document_id, filename, content)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            chunk["id"],
                            document["id"],
                            document["filename"],
                            chunk["content"],
                        ),
                    )

                self._replace_tags(connection, document["id"], document.get("tags", []))

    def get_document(self, document_id: str) -> DocumentSummary:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()

        if row is None:
            raise KeyError(f"找不到文件：{document_id}")

        return DocumentSummary(
            id=row["id"],
            source_id=row["source_id"],
            filename=row["filename"],
            relative_path=row["relative_path"],
            extension=row["extension"],
            modified_at=datetime.fromisoformat(row["modified_at"]),
            content_preview=row["content_preview"],
            extracted_text=row["extracted_text"],
            source_url=row["source_url"],
            canonical_url=row["canonical_url"],
            published_at=_parse_datetime(row["published_at"]),
            language=row["language"],
            status=row["status"],
            business_type=row["business_type"],
            topic_tags=self._get_tags(document_id, "topic"),
            credibility_tier=_metadata_value(row["metadata_json"], "credibility_tier"),
            metadata=json_loads(row["metadata_json"], {}),
        )

    def search(self, payload: SearchRequest) -> SearchResponse:
        start_time = datetime.now()
        filename_hits = self._search_filename(payload)
        content_hits = self._search_content(payload)

        # 用 OrderedDict 去重，保留第一個命中的描述方式與片段。
        merged: "OrderedDict[str, SearchResultItem]" = OrderedDict()
        for item in filename_hits + content_hits:
            if item.document_id not in merged:
                merged[item.document_id] = item

        elapsed = int((datetime.now() - start_time).total_seconds() * 1000)

        return SearchResponse(
            items=list(merged.values()),
            total=len(merged),
            query_time_ms=elapsed,
            semantic_search_ready=False,
        )

    def upsert_knowledge_document(self, source_id: str, document: dict[str, Any]) -> tuple[str, str]:
        canonical_url = document.get("canonical_url")
        checksum = document["checksum"]
        now = utc_now_iso()

        with get_connection() as connection:
            existing = self._find_existing_document(connection, canonical_url=canonical_url, checksum=checksum)
            if existing is not None:
                connection.execute(
                    """
                    UPDATE documents
                    SET last_seen_at = ?, last_checked_at = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (now, now, adapt_json(document.get("metadata", {})), existing["id"]),
                )
                self._replace_tags(connection, existing["id"], document.get("tags", []))
                return existing["id"], "duplicate"

            previous = self._find_existing_document(connection, canonical_url=canonical_url, checksum=None)
            previous_id = previous["id"] if previous else None
            version_group_id = previous["version_group_id"] if previous and previous["version_group_id"] else new_id("ver")
            version_number = int(previous["version_number"] or 1) + 1 if previous else 1

            if previous_id is not None:
                connection.execute(
                    "UPDATE documents SET status = ?, last_checked_at = ? WHERE id = ?",
                    ("superseded", now, previous_id),
                )

            self._insert_document(connection, source_id, document, version_group_id, version_number, previous_id)
            self._replace_tags(connection, document["id"], document.get("tags", []))
            return document["id"], "updated" if previous_id else "inserted"

    def list_versions(self, document_id: str) -> list[DocumentVersionSummary]:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT version_group_id FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"找不到文件：{document_id}")
            version_group_id = row["version_group_id"]
            if not version_group_id:
                version_row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
                return [self._row_to_version_summary(version_row)] if version_row else []

            rows = connection.execute(
                """
                SELECT * FROM documents
                WHERE version_group_id = ?
                ORDER BY version_number DESC, indexed_at DESC
                """,
                (version_group_id,),
            ).fetchall()
        return [self._row_to_version_summary(item) for item in rows]

    def find_existing_document(
        self,
        *,
        canonical_url: str | None,
        checksum: str | None,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = self._find_existing_document(
                connection,
                canonical_url=canonical_url,
                checksum=checksum,
            )
        return dict(row) if row is not None else None

    def _search_filename(self, payload: SearchRequest) -> list[SearchResultItem]:
        clauses = ["d.filename LIKE ?", "(d.status IS NULL OR d.status != 'superseded')"]
        params: list[Any] = [f"%{payload.query}%"]
        self._append_filters(payload, clauses, params)

        sql = f"""
            SELECT d.id, d.source_id, s.name AS source_name, d.filename, d.relative_path, d.modified_at,
                   d.source_url, d.canonical_url, d.published_at, d.business_type, d.metadata_json
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.modified_at DESC
        """

        with get_connection() as connection:
            rows = connection.execute(sql, params).fetchall()

        return [
            SearchResultItem(
                document_id=row["id"],
                source_id=row["source_id"],
                source_name=row["source_name"],
                filename=row["filename"],
                relative_path=row["relative_path"],
                snippet=f"檔名命中：{row['filename']}",
                matched_on="filename",
                modified_at=datetime.fromisoformat(row["modified_at"]),
                source_url=row["source_url"],
                canonical_url=row["canonical_url"],
                published_at=_parse_datetime(row["published_at"]),
                business_type=row["business_type"],
                topic_tags=self._get_tags(row["id"], "topic"),
                credibility_tier=_metadata_value(row["metadata_json"], "credibility_tier"),
            )
            for row in rows
        ]

    def _search_content(self, payload: SearchRequest) -> list[SearchResultItem]:
        like_rows = self._search_content_like(payload)
        match_query = " AND ".join(token for token in payload.query.split() if token.strip())
        clauses = ["document_chunks_fts MATCH ?", "(d.status IS NULL OR d.status != 'superseded')"]
        params: list[Any] = [match_query or payload.query]
        self._append_filters(payload, clauses, params, prefix="d")

        sql = f"""
            SELECT d.id, d.source_id, s.name AS source_name, d.filename, d.relative_path, d.modified_at, c.content,
                   d.source_url, d.canonical_url, d.published_at, d.business_type, d.metadata_json
            FROM document_chunks_fts fts
            JOIN document_chunks c ON c.id = fts.chunk_id
            JOIN documents d ON d.id = fts.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.modified_at DESC
            LIMIT 30
        """

        try:
            with get_connection() as connection:
                fts_rows = connection.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # 如果 FTS 因特殊語法失敗，仍然保留 LIKE 結果，避免整個全文搜索不可用。
            fts_rows = []

        merged_rows = list(fts_rows) + like_rows
        deduped: "OrderedDict[str, sqlite3.Row]" = OrderedDict()
        for row in merged_rows:
            if row["id"] not in deduped:
                deduped[row["id"]] = row

        return [
            SearchResultItem(
                document_id=row["id"],
                source_id=row["source_id"],
                source_name=row["source_name"],
                filename=row["filename"],
                relative_path=row["relative_path"],
                snippet=row["content"][:180],
                matched_on="content",
                modified_at=datetime.fromisoformat(row["modified_at"]),
                source_url=row["source_url"],
                canonical_url=row["canonical_url"],
                published_at=_parse_datetime(row["published_at"]),
                business_type=row["business_type"],
                topic_tags=self._get_tags(row["id"], "topic"),
                credibility_tier=_metadata_value(row["metadata_json"], "credibility_tier"),
            )
            for row in deduped.values()
        ]

    def _search_content_like(self, payload: SearchRequest) -> list[sqlite3.Row]:
        # LIKE 搜索在中文與特殊字元場景更穩定，因此會與 FTS 結果合併。
        like_clauses = ["c.content LIKE ?", "(d.status IS NULL OR d.status != 'superseded')"]
        like_params: list[Any] = [f"%{payload.query}%"]
        self._append_filters(payload, like_clauses, like_params, prefix="d")
        fallback_sql = f"""
            SELECT d.id, d.source_id, s.name AS source_name, d.filename, d.relative_path, d.modified_at, c.content,
                   d.source_url, d.canonical_url, d.published_at, d.business_type, d.metadata_json
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE {' AND '.join(like_clauses)}
            ORDER BY d.modified_at DESC
            LIMIT 30
        """
        with get_connection() as connection:
            return connection.execute(fallback_sql, like_params).fetchall()

    def _append_filters(
        self,
        payload: SearchRequest,
        clauses: list[str],
        params: list[Any],
        prefix: str = "d",
    ) -> None:
        # 把共用篩選條件抽成一個方法，避免 filename 與 content 搜索各寫一遍。
        if payload.source_id:
            clauses.append(f"{prefix}.source_id = ?")
            params.append(payload.source_id)

        if payload.start_date:
            clauses.append(f"{prefix}.modified_at >= ?")
            params.append(payload.start_date.isoformat())

        if payload.end_date:
            clauses.append(f"{prefix}.modified_at <= ?")
            params.append(payload.end_date.isoformat())

    def _find_existing_document(
        self,
        connection: sqlite3.Connection,
        *,
        canonical_url: str | None,
        checksum: str | None,
    ) -> sqlite3.Row | None:
        if canonical_url:
            row = connection.execute(
                """
                SELECT * FROM documents
                WHERE canonical_url = ?
                ORDER BY version_number DESC, indexed_at DESC
                LIMIT 1
                """,
                (canonical_url,),
            ).fetchone()
            if row is not None:
                if checksum is None or row["checksum"] == checksum:
                    return row

        if checksum:
            return connection.execute(
                """
                SELECT * FROM documents
                WHERE checksum = ?
                ORDER BY indexed_at DESC
                LIMIT 1
                """,
                (checksum,),
            ).fetchone()
        return None

    def _insert_document(
        self,
        connection: sqlite3.Connection,
        source_id: str,
        document: dict[str, Any],
        version_group_id: str,
        version_number: int,
        supersedes_document_id: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO documents (
                id, source_id, relative_path, filename, extension, mime_type, file_size,
                checksum, modified_at, indexed_at, content_preview, extracted_text,
                document_kind, source_url, canonical_url, published_at, language, status,
                trust_score, relevance_score, duplicate_group_id, business_type, metadata_json,
                version_group_id, version_number, supersedes_document_id, first_seen_at, last_seen_at,
                last_checked_at, created_by, updated_by, role_hint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["id"],
                source_id,
                document["relative_path"],
                document["filename"],
                document["extension"],
                document["mime_type"],
                document["file_size"],
                document["checksum"],
                document["modified_at"],
                document["indexed_at"],
                document["content_preview"],
                document["extracted_text"],
                document.get("document_kind", "external_web"),
                document.get("source_url"),
                document.get("canonical_url"),
                document.get("published_at"),
                document.get("language"),
                document.get("status", "active"),
                document.get("trust_score"),
                document.get("relevance_score"),
                document.get("duplicate_group_id"),
                document.get("business_type"),
                adapt_json(document.get("metadata", {})),
                version_group_id,
                version_number,
                supersedes_document_id,
                document.get("first_seen_at"),
                document.get("last_seen_at"),
                document.get("last_checked_at"),
                "system",
                "system",
                "member",
            ),
        )
        for chunk in document["chunks"]:
            connection.execute(
                """
                INSERT INTO document_chunks (id, document_id, chunk_index, content, token_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk["id"],
                    document["id"],
                    chunk["chunk_index"],
                    chunk["content"],
                    chunk["token_count"],
                    utc_now_iso(),
                ),
            )
            connection.execute(
                """
                INSERT INTO document_chunks_fts (chunk_id, document_id, filename, content)
                VALUES (?, ?, ?, ?)
                """,
                (
                    chunk["id"],
                    document["id"],
                    document["filename"],
                    chunk["content"],
                ),
            )

    def _replace_tags(self, connection: sqlite3.Connection, document_id: str, tags: list[dict[str, str]]) -> None:
        connection.execute("DELETE FROM document_tags WHERE document_id = ?", (document_id,))
        for tag in tags:
            connection.execute(
                """
                INSERT INTO document_tags (id, document_id, tag_type, tag_value, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (new_id("tag"), document_id, tag["tag_type"], tag["tag_value"], utc_now_iso()),
            )

    def _get_tags(self, document_id: str, tag_type: str) -> list[str]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT tag_value FROM document_tags
                WHERE document_id = ? AND tag_type = ?
                ORDER BY tag_value ASC
                """,
                (document_id, tag_type),
            ).fetchall()
        return [row["tag_value"] for row in rows]

    def _row_to_version_summary(self, row: sqlite3.Row) -> DocumentVersionSummary:
        return DocumentVersionSummary(
            id=row["id"],
            filename=row["filename"],
            source_url=row["source_url"],
            canonical_url=row["canonical_url"],
            checksum=row["checksum"],
            version_group_id=row["version_group_id"],
            version_number=int(row["version_number"] or 1),
            supersedes_document_id=row["supersedes_document_id"],
            status=row["status"],
            indexed_at=datetime.fromisoformat(row["indexed_at"]),
            published_at=_parse_datetime(row["published_at"]),
        )


def make_document_record(
    *,
    source_id: str,
    relative_path: str,
    filename: str,
    extension: str,
    mime_type: str,
    file_size: int,
    checksum: str,
    modified_at: str,
    content_preview: str,
    extracted_text: str,
    chunks: list[dict[str, Any]],
    document_kind: str = "local_file",
    source_url: str | None = None,
    canonical_url: str | None = None,
    published_at: str | None = None,
    language: str | None = None,
    status: str = "active",
    trust_score: float | None = None,
    relevance_score: float | None = None,
    duplicate_group_id: str | None = None,
    business_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    version_group_id: str | None = None,
    version_number: int = 1,
    supersedes_document_id: str | None = None,
    first_seen_at: str | None = None,
    last_seen_at: str | None = None,
    last_checked_at: str | None = None,
    tags: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    # 這個工廠函式讓 IndexingService 在組裝資料時更容易測試與重用。
    return {
        "id": new_id("doc"),
        "source_id": source_id,
        "relative_path": relative_path,
        "filename": filename,
        "extension": extension,
        "mime_type": mime_type,
        "file_size": file_size,
        "checksum": checksum,
        "modified_at": modified_at,
        "indexed_at": utc_now_iso(),
        "content_preview": content_preview,
        "extracted_text": extracted_text,
        "chunks": chunks,
        "document_kind": document_kind,
        "source_url": source_url,
        "canonical_url": canonical_url,
        "published_at": published_at,
        "language": language,
        "status": status,
        "trust_score": trust_score,
        "relevance_score": relevance_score,
        "duplicate_group_id": duplicate_group_id,
        "business_type": business_type,
        "metadata": metadata or {},
        "version_group_id": version_group_id or new_id("ver"),
        "version_number": version_number,
        "supersedes_document_id": supersedes_document_id,
        "first_seen_at": first_seen_at,
        "last_seen_at": last_seen_at,
        "last_checked_at": last_checked_at,
        "tags": tags or [],
    }


def make_chunk_records(text: str, chunk_size: int = 900) -> list[dict[str, Any]]:
    # Phase 1 用固定字元長度切 chunk，先滿足全文搜索與後續摘要引用需求。
    chunks: list[dict[str, Any]] = []
    start = 0
    index = 0

    while start < len(text):
        content = text[start : start + chunk_size]
        chunks.append(
            {
                "id": new_id("chk"),
                "chunk_index": index,
                "content": content,
                "token_count": len(content.split()),
            }
        )
        start += chunk_size
        index += 1

    return chunks


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _metadata_value(raw_metadata: str | None, key: str) -> str | None:
    metadata = json_loads(raw_metadata, {})
    value = metadata.get(key)
    return str(value) if value is not None else None
