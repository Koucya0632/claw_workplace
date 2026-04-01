from __future__ import annotations

import sqlite3
from collections import OrderedDict
from datetime import datetime
from typing import Any

from app.repositories.database import get_connection
from app.schemas.search import DocumentSummary, SearchRequest, SearchResponse, SearchResultItem
from app.utils import new_id, utc_now_iso


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
                        created_by, updated_by, role_hint
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def _search_filename(self, payload: SearchRequest) -> list[SearchResultItem]:
        clauses = ["d.filename LIKE ?"]
        params: list[Any] = [f"%{payload.query}%"]
        self._append_filters(payload, clauses, params)

        sql = f"""
            SELECT d.id, d.source_id, s.name AS source_name, d.filename, d.relative_path, d.modified_at
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
            )
            for row in rows
        ]

    def _search_content(self, payload: SearchRequest) -> list[SearchResultItem]:
        like_rows = self._search_content_like(payload)
        match_query = " AND ".join(token for token in payload.query.split() if token.strip())
        clauses = ["document_chunks_fts MATCH ?"]
        params: list[Any] = [match_query or payload.query]
        self._append_filters(payload, clauses, params, prefix="d")

        sql = f"""
            SELECT d.id, d.source_id, s.name AS source_name, d.filename, d.relative_path, d.modified_at, c.content
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
            )
            for row in deduped.values()
        ]

    def _search_content_like(self, payload: SearchRequest) -> list[sqlite3.Row]:
        # LIKE 搜索在中文與特殊字元場景更穩定，因此會與 FTS 結果合併。
        like_clauses = ["c.content LIKE ?"]
        like_params: list[Any] = [f"%{payload.query}%"]
        self._append_filters(payload, like_clauses, like_params, prefix="d")
        fallback_sql = f"""
            SELECT d.id, d.source_id, s.name AS source_name, d.filename, d.relative_path, d.modified_at, c.content
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
