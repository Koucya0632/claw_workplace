from __future__ import annotations

import sqlite3
from datetime import datetime

from app.repositories.database import get_connection
from app.schemas.openclaw_development import OpenClawDevelopmentConfigRequest, OpenClawDevelopmentConfigResponse
from app.utils import utc_now_iso


class OpenClawDevelopmentConfigRepository:
    def get(self, instance_id: str) -> OpenClawDevelopmentConfigResponse:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM openclaw_development_configs
                WHERE instance_id = ?
                """,
                (instance_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"找不到 development 設定：{instance_id}")

        return self._row_to_model(row)

    def upsert(self, payload: OpenClawDevelopmentConfigRequest) -> OpenClawDevelopmentConfigResponse:
        now = utc_now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_development_configs (
                    instance_id, enabled, delivery_channel, discord_channel_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    delivery_channel = excluded.delivery_channel,
                    discord_channel_id = excluded.discord_channel_id,
                    updated_at = excluded.updated_at
                """,
                (
                    payload.instance_id,
                    1 if payload.enabled else 0,
                    payload.delivery_channel,
                    payload.discord_channel_id,
                    now,
                    now,
                ),
            )
        return self.get(payload.instance_id)

    def mark_delivery(
        self,
        *,
        instance_id: str,
        run_id: str,
        delivery_status: str | None = None,
        delivery_error: str | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE openclaw_development_configs
                SET last_run_id = ?,
                    last_delivery_status = COALESCE(?, last_delivery_status),
                    last_delivery_error = ?,
                    updated_at = ?
                WHERE instance_id = ?
                """,
                (run_id, delivery_status, delivery_error, utc_now_iso(), instance_id),
            )

    def _row_to_model(self, row: sqlite3.Row) -> OpenClawDevelopmentConfigResponse:
        return OpenClawDevelopmentConfigResponse(
            instance_id=row["instance_id"],
            enabled=bool(row["enabled"]),
            delivery_channel=row["delivery_channel"],
            discord_channel_id=row["discord_channel_id"],
            last_run_id=row["last_run_id"],
            last_delivery_status=row["last_delivery_status"],
            last_delivery_error=row["last_delivery_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
