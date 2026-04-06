from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from app.repositories.database import adapt_json, get_connection
from app.schemas.knowledge import KnowledgeIngestionItemResponse, KnowledgeIngestionRunResponse
from app.utils import json_loads, new_id, utc_now_iso


class KnowledgeRepository:
    def create_run(
        self,
        *,
        source_id: str,
        topic: str,
        query: str,
        agent_id: str,
        metadata: dict[str, Any],
    ) -> str:
        run_id = new_id("ing")
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    id, source_id, topic, query, status, total_candidates, accepted_count, updated_count,
                    rejected_count, agent_id, metadata_json, created_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_id,
                    topic,
                    query,
                    "running",
                    0,
                    0,
                    0,
                    0,
                    agent_id,
                    adapt_json(metadata),
                    utc_now_iso(),
                    None,
                ),
            )
        return run_id

    def add_item(
        self,
        *,
        run_id: str,
        candidate_url: str,
        normalized_url: str | None,
        title: str,
        status: str,
        reject_reason: str | None,
        document_id: str | None,
        trust_score: float | None,
        relevance_score: float | None,
        duplicate_score: float | None,
        checksum: str | None,
        source_domain: str,
        metadata: dict[str, Any],
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_items (
                    id, run_id, candidate_url, normalized_url, title, status, reject_reason,
                    document_id, trust_score, relevance_score, duplicate_score, checksum,
                    source_domain, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("ingi"),
                    run_id,
                    candidate_url,
                    normalized_url,
                    title,
                    status,
                    reject_reason,
                    document_id,
                    trust_score,
                    relevance_score,
                    duplicate_score,
                    checksum,
                    source_domain,
                    adapt_json(metadata),
                    utc_now_iso(),
                ),
            )

    def finish_run(
        self,
        *,
        run_id: str,
        status: str,
        total_candidates: int,
        accepted_count: int,
        updated_count: int,
        rejected_count: int,
        metadata: dict[str, Any],
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE ingestion_runs
                SET status = ?, total_candidates = ?, accepted_count = ?, updated_count = ?,
                    rejected_count = ?, metadata_json = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    total_candidates,
                    accepted_count,
                    updated_count,
                    rejected_count,
                    adapt_json(metadata),
                    utc_now_iso(),
                    run_id,
                ),
            )

    def list_runs(self, *, source_id: str | None = None, limit: int = 20) -> list[KnowledgeIngestionRunResponse]:
        clauses = []
        params: list[Any] = []
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)

        sql = """
            SELECT runs.*, sources.name AS source_name
            FROM ingestion_runs runs
            JOIN sources ON sources.id = runs.source_id
        """
        if clauses:
            sql += f" WHERE {' AND '.join(clauses)}"
        sql += " ORDER BY runs.created_at DESC LIMIT ?"
        params.append(limit)

        with get_connection() as connection:
            runs = connection.execute(sql, params).fetchall()
            items = connection.execute(
                """
                SELECT * FROM ingestion_items
                WHERE run_id IN (
                    SELECT id FROM ingestion_runs
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC
                """,
                (limit,),
            ).fetchall()

        grouped: dict[str, list[KnowledgeIngestionItemResponse]] = {}
        for row in items:
            grouped.setdefault(row["run_id"], []).append(self._row_to_item(row))

        return [self._row_to_run(row, grouped.get(row["id"], [])) for row in runs]

    def _row_to_item(self, row: sqlite3.Row) -> KnowledgeIngestionItemResponse:
        return KnowledgeIngestionItemResponse(
            id=row["id"],
            candidate_url=row["candidate_url"],
            normalized_url=row["normalized_url"],
            title=row["title"],
            status=row["status"],
            reject_reason=row["reject_reason"],
            document_id=row["document_id"],
            trust_score=row["trust_score"],
            relevance_score=row["relevance_score"],
            duplicate_score=row["duplicate_score"],
            source_domain=row["source_domain"],
            created_at=_parse_datetime(row["created_at"]),
            metadata=json_loads(row["metadata_json"], {}),
        )

    def _row_to_run(self, row: sqlite3.Row, items: list[KnowledgeIngestionItemResponse]) -> KnowledgeIngestionRunResponse:
        return KnowledgeIngestionRunResponse(
            id=row["id"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            topic=row["topic"],
            query=row["query"],
            status=row["status"],
            total_candidates=row["total_candidates"],
            accepted_count=row["accepted_count"],
            updated_count=row["updated_count"],
            rejected_count=row["rejected_count"],
            created_at=_parse_datetime(row["created_at"]),
            completed_at=_parse_datetime(row["completed_at"]),
            items=items,
            metadata=json_loads(row["metadata_json"], {}),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None

