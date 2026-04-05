from __future__ import annotations

import sqlite3
from datetime import datetime

from app.repositories.database import get_connection
from app.schemas.openclaw_system_inspection import (
    OpenClawSystemInspectionConfigRequest,
    OpenClawSystemInspectionConfigResponse,
)
from app.utils import utc_now_iso


class OpenClawSystemInspectionConfigRepository:
    def get(self, instance_id: str) -> OpenClawSystemInspectionConfigResponse:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM openclaw_system_inspection_configs
                WHERE instance_id = ?
                """,
                (instance_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"找不到 system inspection 設定：{instance_id}")

        return self._row_to_model(row)

    def upsert(self, payload: OpenClawSystemInspectionConfigRequest) -> OpenClawSystemInspectionConfigResponse:
        now = utc_now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_system_inspection_configs (
                    instance_id, enabled, schedule_timezone, schedule_time, delivery_channel, telegram_target,
                    discord_channel_id, version_check_enabled, log_review_enabled, log_review_window_hours,
                    log_review_limit, official_release_url, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    schedule_timezone = excluded.schedule_timezone,
                    schedule_time = excluded.schedule_time,
                    delivery_channel = excluded.delivery_channel,
                    telegram_target = excluded.telegram_target,
                    discord_channel_id = excluded.discord_channel_id,
                    version_check_enabled = excluded.version_check_enabled,
                    log_review_enabled = excluded.log_review_enabled,
                    log_review_window_hours = excluded.log_review_window_hours,
                    log_review_limit = excluded.log_review_limit,
                    official_release_url = excluded.official_release_url,
                    updated_at = excluded.updated_at
                """,
                (
                    payload.instance_id,
                    1 if payload.enabled else 0,
                    payload.schedule_timezone,
                    payload.schedule_time,
                    payload.delivery_channel,
                    payload.telegram_target,
                    payload.discord_channel_id,
                    1 if payload.version_check_enabled else 0,
                    1 if payload.log_review_enabled else 0,
                    payload.log_review_window_hours,
                    payload.log_review_limit,
                    payload.official_release_url,
                    now,
                    now,
                ),
            )
        return self.get(payload.instance_id)

    def mark_run(
        self,
        *,
        instance_id: str,
        scheduled_date: str,
        run_id: str,
        delivery_status: str | None = None,
        delivery_error: str | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE openclaw_system_inspection_configs
                SET last_scheduled_date = ?,
                    last_run_id = ?,
                    last_delivery_status = COALESCE(?, last_delivery_status),
                    last_delivery_error = ?,
                    updated_at = ?
                WHERE instance_id = ?
                """,
                (scheduled_date, run_id, delivery_status, delivery_error, utc_now_iso(), instance_id),
            )

    def list_enabled(self) -> list[OpenClawSystemInspectionConfigResponse]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM openclaw_system_inspection_configs
                WHERE enabled = 1
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def _row_to_model(self, row: sqlite3.Row) -> OpenClawSystemInspectionConfigResponse:
        return OpenClawSystemInspectionConfigResponse(
            instance_id=row["instance_id"],
            enabled=bool(row["enabled"]),
            schedule_timezone=row["schedule_timezone"],
            schedule_time=row["schedule_time"],
            delivery_channel=row["delivery_channel"],
            telegram_target=row["telegram_target"],
            discord_channel_id=row["discord_channel_id"],
            version_check_enabled=bool(row["version_check_enabled"]),
            log_review_enabled=bool(row["log_review_enabled"]),
            log_review_window_hours=row["log_review_window_hours"],
            log_review_limit=row["log_review_limit"],
            official_release_url=row["official_release_url"],
            last_scheduled_date=row["last_scheduled_date"],
            last_run_id=row["last_run_id"],
            last_delivery_status=row["last_delivery_status"],
            last_delivery_error=row["last_delivery_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
