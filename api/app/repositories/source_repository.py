from __future__ import annotations

import sqlite3
from datetime import datetime

from app.repositories.database import adapt_json, get_connection
from app.schemas.source import SourceConfig, SourceCreateRequest, SourceResponse
from app.utils import json_loads, new_id, utc_now_iso


class SourceRepository:
    # SourceRepository 專門管理資料源設定與掃描狀態。
    def create(self, payload: SourceCreateRequest) -> SourceResponse:
        source_id = new_id("src")
        now = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sources (id, name, type, config_json, status, created_by, updated_by, role_hint, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    payload.name,
                    payload.type,
                    adapt_json(payload.config.model_dump()),
                    "ready",
                    "system",
                    "system",
                    payload.role_hint,
                    now,
                    now,
                ),
            )

        return self.get(source_id)

    def list_all(self) -> list[SourceResponse]:
        with get_connection() as connection:
            rows = connection.execute("SELECT * FROM sources ORDER BY created_at DESC").fetchall()
        return [self._row_to_model(row) for row in rows]

    def get(self, source_id: str) -> SourceResponse:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()

        if row is None:
            raise KeyError(f"找不到資料源：{source_id}")

        return self._row_to_model(row)

    def touch_scan(self, source_id: str, status: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE sources SET status = ?, last_scan_at = ?, updated_at = ? WHERE id = ?",
                (status, utc_now_iso(), utc_now_iso(), source_id),
            )

    def _row_to_model(self, row: sqlite3.Row) -> SourceResponse:
        return SourceResponse(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            status=row["status"],
            config=SourceConfig(**json_loads(row["config_json"], {})),
            last_scan_at=_parse_datetime(row["last_scan_at"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    # repository 從 sqlite 讀出字串後，在這裡統一轉回 datetime。
    return datetime.fromisoformat(value) if value else None

