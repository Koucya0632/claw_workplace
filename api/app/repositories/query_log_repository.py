from __future__ import annotations

from app.repositories.database import get_connection
from app.utils import new_id, utc_now_iso


class QueryLogRepository:
    # QueryLogRepository 讓搜索操作可追溯，後續做觀測與優化會很方便。
    def start(self, query_text: str, source_filter: str | None) -> str:
        log_id = new_id("qry")
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO query_logs (
                    id, query_text, source_filter, started_at, finished_at,
                    result_count, status, error_message, created_by, updated_by, role_hint
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    query_text,
                    source_filter,
                    utc_now_iso(),
                    None,
                    0,
                    "running",
                    None,
                    "system",
                    "system",
                    "member",
                ),
            )
        return log_id

    def finish(self, log_id: str, result_count: int, status: str, error_message: str | None = None) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE query_logs
                SET finished_at = ?, result_count = ?, status = ?, error_message = ?
                WHERE id = ?
                """,
                (utc_now_iso(), result_count, status, error_message, log_id),
            )

