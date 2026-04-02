from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional

from app.repositories.database import adapt_json, get_connection
from app.schemas.openclaw_common import OpenClawOperationLogRecord
from app.utils import json_loads, new_id, utc_now_iso


class OpenClawOperationLogRepository:
    # 所有敏感管理操作都要留下審計紀錄，因此獨立成專責 repository。
    def create(
        self,
        *,
        instance_id: Optional[str],
        operation_type: str,
        target_type: str,
        target_id: Optional[str],
        status: str,
        error_message: Optional[str],
        request_summary: dict[str, Any],
        response_summary: Optional[dict[str, Any]],
        source_mode: str,
    ) -> OpenClawOperationLogRecord:
        log_id = new_id("oclog")
        created_at = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_operation_logs (
                    id, instance_id, operation_type, target_type, target_id, status, error_message,
                    request_summary, response_summary, source_mode, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    instance_id,
                    operation_type,
                    target_type,
                    target_id,
                    status,
                    error_message,
                    adapt_json(request_summary),
                    adapt_json(response_summary) if response_summary is not None else None,
                    source_mode,
                    created_at,
                ),
            )

        return self.list_recent(limit=1)[0]

    def list_recent(self, *, limit: int = 20, instance_id: Optional[str] = None) -> list[OpenClawOperationLogRecord]:
        query = "SELECT * FROM openclaw_operation_logs"
        params: tuple[Any, ...]

        if instance_id:
            query += " WHERE instance_id = ?"
            params = (instance_id, limit)
            query += " ORDER BY created_at DESC LIMIT ?"
        else:
            params = (limit,)
            query += " ORDER BY created_at DESC LIMIT ?"

        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._row_to_model(row) for row in rows]

    def _row_to_model(self, row: sqlite3.Row) -> OpenClawOperationLogRecord:
        return OpenClawOperationLogRecord(
            id=row["id"],
            instance_id=row["instance_id"],
            operation_type=row["operation_type"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            status=row["status"],
            error_message=row["error_message"],
            request_summary=json_loads(row["request_summary"], {}),
            response_summary=json_loads(row["response_summary"], None),
            source_mode=row["source_mode"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
