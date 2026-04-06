from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from app.repositories.database import adapt_json, get_connection
from app.schemas.source import (
    SourceConfig,
    SourceCreateRequest,
    SourceDetailResponse,
    SourceMetricsResponse,
    SourceResponse,
    SourceSummaryResponse,
    SourceSyncEventResponse,
    SourceSyncResult,
    SourceUpdateRequest,
)
from app.utils import json_loads, new_id, truncate_text, utc_now, utc_now_iso


SourceSortKey = Literal["updated_at", "last_sync", "name", "document_count", "status"]
SourceSortOrder = Literal["asc", "desc"]


class SourceRepository:
    # SourceRepository 負責資料源 CRUD、同步狀態與管理頁聚合資料。
    def create(self, payload: SourceCreateRequest) -> SourceResponse:
        source_id = new_id("src")
        now = utc_now_iso()
        status = "active"
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sources (
                    id, name, type, config_json, status, is_enabled, last_sync_status,
                    last_sync_error, last_sync_result_json, created_by, updated_by, role_hint,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    payload.name,
                    payload.type,
                    adapt_json(payload.config.model_dump()),
                    status,
                    1,
                    "never_scanned",
                    None,
                    adapt_json(SourceSyncResult().model_dump()),
                    "system",
                    "system",
                    payload.role_hint or "member",
                    now,
                    now,
                ),
            )
        return self.get(source_id)

    def list_all(
        self,
        *,
        q: str | None = None,
        status: str | None = None,
        type: str | None = None,
        sort: SourceSortKey = "updated_at",
        order: SourceSortOrder = "desc",
    ) -> list[SourceSummaryResponse]:
        clauses = ["1 = 1"]
        params: list[Any] = []

        if q:
            clauses.append("(LOWER(s.name) LIKE ? OR LOWER(s.type) LIKE ? OR LOWER(s.config_json) LIKE ?)")
            keyword = f"%{q.lower()}%"
            params.extend([keyword, keyword, keyword])

        if type:
            clauses.append("s.type = ?")
            params.append(type)

        if status:
            status_clause, status_params = self._status_clause(status)
            clauses.append(status_clause)
            params.extend(status_params)

        order_column = {
            "updated_at": "s.updated_at",
            "last_sync": "COALESCE(s.last_scan_at, s.updated_at)",
            "name": "LOWER(s.name)",
            "document_count": "document_count",
            "status": "CASE WHEN s.is_enabled = 0 THEN 'disabled' ELSE s.last_sync_status END",
        }.get(sort, "s.updated_at")
        order_direction = "ASC" if order == "asc" else "DESC"

        sql = f"""
            SELECT
                s.*,
                COALESCE(documents.document_count, 0) AS document_count
            FROM sources s
            LEFT JOIN (
                SELECT source_id, COUNT(*) AS document_count
                FROM documents
                GROUP BY source_id
            ) AS documents ON documents.source_id = s.id
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_column} {order_direction}, LOWER(s.name) ASC
        """

        with get_connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_summary(row) for row in rows]

    def get(self, source_id: str) -> SourceResponse:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    s.*,
                    COALESCE(documents.document_count, 0) AS document_count
                FROM sources s
                LEFT JOIN (
                    SELECT source_id, COUNT(*) AS document_count
                    FROM documents
                    GROUP BY source_id
                ) AS documents ON documents.source_id = s.id
                WHERE s.id = ?
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"找不到資料源：{source_id}")
        return SourceResponse(**self._row_to_summary(row).model_dump())

    def find_by_merge_key(self, merge_key: str) -> SourceResponse | None:
        for source in self.list_all():
            extra = source.config.extra or {}
            if str(extra.get("merge_key") or "").strip() == merge_key:
                return self.get(source.id)
        return None

    def get_detail(self, source_id: str) -> SourceDetailResponse:
        source = self.get(source_id)
        with get_connection() as connection:
            version_count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM documents WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        return SourceDetailResponse(
            **source.model_dump(),
            version_count=int(version_count_row["count"] if version_count_row else 0),
            recent_activity=self.list_activity(source_id, limit=10),
        )

    def get_metrics(self) -> SourceMetricsResponse:
        recent_threshold = (utc_now() - timedelta(days=7)).isoformat()
        with get_connection() as connection:
            counts = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_sources,
                    SUM(CASE WHEN is_enabled = 0 THEN 1 ELSE 0 END) AS disabled_sources,
                    SUM(CASE WHEN is_enabled = 1 AND last_sync_status = 'healthy' THEN 1 ELSE 0 END) AS healthy_sources,
                    SUM(CASE WHEN is_enabled = 1 AND last_sync_status = 'warning' THEN 1 ELSE 0 END) AS warning_sources,
                    SUM(CASE WHEN is_enabled = 1 AND last_sync_status = 'failed' THEN 1 ELSE 0 END) AS failed_sources,
                    SUM(CASE WHEN is_enabled = 1 AND last_sync_status = 'syncing' THEN 1 ELSE 0 END) AS syncing_sources,
                    SUM(
                        CASE
                            WHEN COALESCE(last_scan_at, updated_at) >= ? THEN 1
                            ELSE 0
                        END
                    ) AS recently_updated_sources
                FROM sources
                """,
                (recent_threshold,),
            ).fetchone()
            recent_sync_failures_row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM source_sync_events
                WHERE status = 'failed' AND created_at >= ?
                """,
                (recent_threshold,),
            ).fetchone()

        return SourceMetricsResponse(
            total_sources=int(counts["total_sources"] or 0),
            healthy_sources=int(counts["healthy_sources"] or 0),
            warning_sources=int(counts["warning_sources"] or 0),
            failed_sources=int(counts["failed_sources"] or 0),
            syncing_sources=int(counts["syncing_sources"] or 0),
            disabled_sources=int(counts["disabled_sources"] or 0),
            recently_updated_sources=int(counts["recently_updated_sources"] or 0),
            recent_sync_failures=int(recent_sync_failures_row["count"] or 0),
        )

    def update(self, source_id: str, payload: SourceUpdateRequest) -> SourceResponse:
        current = self.get(source_id)
        name = payload.name or current.name
        config = payload.config or current.config
        is_enabled = current.is_enabled if payload.is_enabled is None else payload.is_enabled
        status = "disabled" if not is_enabled else ("active" if current.status == "disabled" else current.status)
        now = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE sources
                SET name = ?, config_json = ?, is_enabled = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    adapt_json(config.model_dump()),
                    1 if is_enabled else 0,
                    status,
                    now,
                    source_id,
                ),
            )
        return self.get(source_id)

    def merge_extra_config(
        self,
        source_id: str,
        *,
        source_name: str | None = None,
        url: str | None = None,
        urls: list[str] | None = None,
        extra_updates: dict[str, Any] | None = None,
    ) -> SourceResponse:
        current = self.get(source_id)
        existing_extra = dict(current.config.extra or {})
        incoming_extra = dict(extra_updates or {})

        for key, value in incoming_extra.items():
            if isinstance(value, list):
                merged_values = []
                for item in [*existing_extra.get(key, []), *value]:
                    normalized = str(item).strip()
                    if normalized and normalized not in merged_values:
                        merged_values.append(normalized)
                existing_extra[key] = merged_values
            elif value is not None:
                existing_extra[key] = value

        next_urls = list(current.config.urls or [])
        for candidate in urls or []:
            normalized = str(candidate).strip()
            if normalized and normalized not in next_urls:
                next_urls.append(normalized)

        next_url = url or current.config.url
        if next_url and next_url not in next_urls:
            next_urls.insert(0, next_url)

        return self.update(
            source_id,
            SourceUpdateRequest(
                name=source_name or current.name,
                config=SourceConfig(
                    path=current.config.path,
                    url=next_url,
                    urls=next_urls,
                    root_page_id=current.config.root_page_id,
                    database_id=current.config.database_id,
                    workspace_name=current.config.workspace_name,
                    extra=existing_extra,
                ),
                is_enabled=current.is_enabled,
            ),
        )

    def set_enabled(self, source_id: str, enabled: bool) -> SourceResponse:
        current = self.get(source_id)
        if current.is_enabled == enabled:
            return current
        now = utc_now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE sources
                SET is_enabled = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (1 if enabled else 0, "active" if enabled else "disabled", now, source_id),
            )
        return self.get(source_id)

    def delete(self, source_id: str) -> None:
        with get_connection() as connection:
            row = connection.execute("SELECT id FROM sources WHERE id = ?", (source_id,)).fetchone()
            if row is None:
                raise KeyError(f"找不到資料源：{source_id}")

            document_rows = connection.execute(
                "SELECT id FROM documents WHERE source_id = ?",
                (source_id,),
            ).fetchall()
            document_ids = [row["id"] for row in document_rows]
            if document_ids:
                placeholders = ",".join("?" for _ in document_ids)
                connection.execute(
                    f"DELETE FROM document_chunks_fts WHERE document_id IN ({placeholders})",
                    document_ids,
                )
                connection.execute(
                    f"DELETE FROM document_chunks WHERE document_id IN ({placeholders})",
                    document_ids,
                )
                connection.execute(
                    f"DELETE FROM document_tags WHERE document_id IN ({placeholders})",
                    document_ids,
                )
                connection.execute(
                    f"DELETE FROM ingestion_items WHERE document_id IN ({placeholders})",
                    document_ids,
                )
                connection.execute("DELETE FROM documents WHERE source_id = ?", (source_id,))

            run_rows = connection.execute(
                "SELECT id FROM ingestion_runs WHERE source_id = ?",
                (source_id,),
            ).fetchall()
            run_ids = [row["id"] for row in run_rows]
            if run_ids:
                placeholders = ",".join("?" for _ in run_ids)
                connection.execute(
                    f"DELETE FROM ingestion_items WHERE run_id IN ({placeholders})",
                    run_ids,
                )
                connection.execute("DELETE FROM ingestion_runs WHERE source_id = ?", (source_id,))

            connection.execute("DELETE FROM source_sync_events WHERE source_id = ?", (source_id,))
            connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))

    def list_activity(self, source_id: str, *, limit: int = 10) -> list[SourceSyncEventResponse]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM source_sync_events
                WHERE source_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (source_id, limit),
            ).fetchall()
        return [self._row_to_activity(row) for row in rows]

    def touch_scan(self, source_id: str, status: str) -> SourceResponse:
        now = utc_now_iso()
        mapped_status = "syncing" if status == "scanning" else ("healthy" if status == "ready" else status)
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE sources
                SET status = ?, last_scan_at = ?, updated_at = ?, last_sync_status = ?
                WHERE id = ?
                """,
                (status, now, now, mapped_status, source_id),
            )
        return self.get(source_id)

    def mark_sync_started(self, source_id: str, *, message: str = "開始同步資料源。") -> None:
        now = utc_now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE sources
                SET status = ?, last_sync_status = ?, last_sync_error = NULL, last_scan_at = ?, updated_at = ?
                WHERE id = ?
                """,
                ("scanning", "syncing", now, now, source_id),
            )
        self.record_sync_event(source_id, status="syncing", message=message)

    def mark_sync_finished(
        self,
        source_id: str,
        *,
        status: str,
        scanned_count: int,
        skipped_count: int,
        error_count: int,
        message: str,
        error_message: str | None = None,
    ) -> None:
        now = utc_now_iso()
        status_value = "disabled" if not self.get(source_id).is_enabled else "active"
        success_at = now if status in {"healthy", "warning"} else None
        failed_at = now if status == "failed" else None
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE sources
                SET
                    status = ?,
                    last_sync_status = ?,
                    last_sync_error = ?,
                    last_sync_result_json = ?,
                    last_scan_at = ?,
                    last_successful_sync_at = COALESCE(?, last_successful_sync_at),
                    last_failed_sync_at = COALESCE(?, last_failed_sync_at),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status_value,
                    status,
                    error_message,
                    adapt_json(
                        {
                            "scanned_count": scanned_count,
                            "skipped_count": skipped_count,
                            "error_count": error_count,
                        }
                    ),
                    now,
                    success_at,
                    failed_at,
                    now,
                    source_id,
                ),
            )
        self.record_sync_event(
            source_id,
            status=status,
            message=message,
            scanned_count=scanned_count,
            skipped_count=skipped_count,
            error_count=error_count,
        )

    def record_sync_event(
        self,
        source_id: str,
        *,
        status: str,
        message: str,
        scanned_count: int = 0,
        skipped_count: int = 0,
        error_count: int = 0,
    ) -> SourceSyncEventResponse:
        event_id = new_id("ssev")
        created_at = utc_now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO source_sync_events (
                    id, source_id, status, message, scanned_count, skipped_count, error_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    source_id,
                    status,
                    truncate_text(message, max_length=480),
                    scanned_count,
                    skipped_count,
                    error_count,
                    created_at,
                ),
            )
        return SourceSyncEventResponse(
            id=event_id,
            source_id=source_id,
            status=status,
            message=truncate_text(message, max_length=480),
            scanned_count=scanned_count,
            skipped_count=skipped_count,
            error_count=error_count,
            created_at=datetime.fromisoformat(created_at),
        )

    def _status_clause(self, status: str) -> tuple[str, list[Any]]:
        normalized = status.lower()
        if normalized in {"all", ""}:
            return "1 = 1", []
        if normalized in {"disabled", "inactive"}:
            return "s.is_enabled = 0", []
        if normalized in {"healthy", "normal"}:
            return "s.is_enabled = 1 AND s.last_sync_status = 'healthy'", []
        if normalized in {"warning", "abnormal"}:
            return "s.is_enabled = 1 AND s.last_sync_status IN ('warning', 'failed')", []
        if normalized == "failed":
            return "s.is_enabled = 1 AND s.last_sync_status = 'failed'", []
        if normalized == "syncing":
            return "s.is_enabled = 1 AND s.last_sync_status = 'syncing'", []
        if normalized == "never_scanned":
            return "s.is_enabled = 1 AND s.last_sync_status = 'never_scanned'", []
        if normalized == "active":
            return "s.is_enabled = 1", []
        return "LOWER(s.last_sync_status) = ?", [normalized]

    def _row_to_summary(self, row: sqlite3.Row) -> SourceSummaryResponse:
        sync_result = json_loads(row["last_sync_result_json"], {}) or {}
        return SourceSummaryResponse(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            status=row["status"],
            is_enabled=bool(row["is_enabled"]),
            config=SourceConfig(**json_loads(row["config_json"], {})),
            document_count=int(row["document_count"] or 0),
            last_sync_status=row["last_sync_status"] or "never_scanned",
            last_sync_error=row["last_sync_error"],
            last_successful_sync_at=_parse_datetime(row["last_successful_sync_at"]),
            last_failed_sync_at=_parse_datetime(row["last_failed_sync_at"]),
            last_sync_result=SourceSyncResult(
                scanned_count=int(sync_result.get("scanned_count", 0) or 0),
                skipped_count=int(sync_result.get("skipped_count", 0) or 0),
                error_count=int(sync_result.get("error_count", 0) or 0),
            ),
            last_scan_at=_parse_datetime(row["last_scan_at"]),
            created_at=_required_datetime(row["created_at"]),
            updated_at=_required_datetime(row["updated_at"]),
        )

    def _row_to_activity(self, row: sqlite3.Row) -> SourceSyncEventResponse:
        return SourceSyncEventResponse(
            id=row["id"],
            source_id=row["source_id"],
            status=row["status"],
            message=row["message"],
            scanned_count=int(row["scanned_count"] or 0),
            skipped_count=int(row["skipped_count"] or 0),
            error_count=int(row["error_count"] or 0),
            created_at=_required_datetime(row["created_at"]),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _required_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)
