from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional, Union

from app.repositories.database import adapt_json, get_connection
from app.schemas.openclaw_instance import (
    OpenClawInstanceCreateRequest,
    OpenClawInstanceResponse,
    OpenClawInstanceSnapshotSummary,
    OpenClawInstanceUpdateRequest,
)
from app.utils import json_loads, new_id, utc_now_iso


class OpenClawInstanceRepository:
    # 這個 repository 統一管理 instance、secret 與快照，避免 service 分散碰 sqlite 細節。
    def create(self, payload: OpenClawInstanceCreateRequest) -> OpenClawInstanceResponse:
        instance_id = new_id("oc")
        now = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_instances (
                    id, name, gateway_url, is_active, last_health_status, last_health_checked_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (instance_id, payload.name, payload.gateway_url, int(payload.is_active), None, None, now, now),
            )

        return self.get(instance_id)

    def list_all(self) -> list[OpenClawInstanceResponse]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM openclaw_instances ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_model(connection, row) for row in rows]

    def get(self, instance_id: str) -> OpenClawInstanceResponse:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM openclaw_instances WHERE id = ?",
                (instance_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"找不到 OpenClaw Instance：{instance_id}")
            return self._row_to_model(connection, row)

    def update(self, instance_id: str, payload: OpenClawInstanceUpdateRequest) -> OpenClawInstanceResponse:
        current = self.get(instance_id)

        next_name = payload.name if payload.name is not None else current.name
        next_gateway_url = payload.gateway_url if payload.gateway_url is not None else current.gateway_url
        next_is_active = payload.is_active if payload.is_active is not None else current.is_active

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE openclaw_instances
                SET name = ?, gateway_url = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_name, next_gateway_url, int(next_is_active), utc_now_iso(), instance_id),
            )

        return self.get(instance_id)

    def update_health_status(self, instance_id: str, status: str) -> OpenClawInstanceResponse:
        checked_at = utc_now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE openclaw_instances
                SET last_health_status = ?, last_health_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, checked_at, checked_at, instance_id),
            )
        return self.get(instance_id)

    def save_secret(self, instance_id: str, encrypted_token: str) -> None:
        # token 一律走 replace，避免額外分支判斷 create 與 update。
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_instance_secrets (instance_id, encrypted_token, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(instance_id)
                DO UPDATE SET encrypted_token = excluded.encrypted_token, updated_at = excluded.updated_at
                """,
                (instance_id, encrypted_token, utc_now_iso()),
            )

    def clear_secret(self, instance_id: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "DELETE FROM openclaw_instance_secrets WHERE instance_id = ?",
                (instance_id,),
            )

    def get_secret(self, instance_id: str) -> Optional[str]:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT encrypted_token FROM openclaw_instance_secrets WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
        return row["encrypted_token"] if row is not None else None

    def upsert_snapshot(self, instance_id: str, snapshot_type: str, payload: Any) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_cached_snapshots (instance_id, snapshot_type, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(instance_id, snapshot_type)
                DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
                """,
                (instance_id, snapshot_type, adapt_json(payload), utc_now_iso()),
            )

    def get_snapshot(
        self,
        instance_id: str,
        snapshot_type: str,
    ) -> Optional[Union[dict[str, Any], list[Any]]]:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM openclaw_cached_snapshots
                WHERE instance_id = ? AND snapshot_type = ?
                """,
                (instance_id, snapshot_type),
            ).fetchone()

        if row is None:
            return None
        return json_loads(row["payload_json"], {})

    def _row_to_model(self, connection: sqlite3.Connection, row: sqlite3.Row) -> OpenClawInstanceResponse:
        return OpenClawInstanceResponse(
            id=row["id"],
            name=row["name"],
            gateway_url=row["gateway_url"],
            is_active=bool(row["is_active"]),
            has_token=self._has_secret(connection, row["id"]),
            last_health_status=row["last_health_status"],
            last_health_checked_at=_parse_datetime(row["last_health_checked_at"]),
            snapshot_summary=self._build_snapshot_summary(connection, row["id"], row["last_health_status"]),
            created_at=_parse_datetime_required(row["created_at"]),
            updated_at=_parse_datetime_required(row["updated_at"]),
        )

    def _has_secret(self, connection: sqlite3.Connection, instance_id: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM openclaw_instance_secrets WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        return row is not None

    def _build_snapshot_summary(
        self,
        connection: sqlite3.Connection,
        instance_id: str,
        last_health_status: Optional[str],
    ) -> OpenClawInstanceSnapshotSummary:
        rows = connection.execute(
            """
            SELECT snapshot_type, payload_json, updated_at
            FROM openclaw_cached_snapshots
            WHERE instance_id = ?
            """,
            (instance_id,),
        ).fetchall()

        agent_count = 0
        device_count = 0
        config_updated_at: Optional[datetime] = None

        for row in rows:
            payload = json_loads(row["payload_json"], {})
            if row["snapshot_type"] == "agents":
                agent_count = _count_snapshot_items(payload)
            elif row["snapshot_type"] == "devices":
                device_count = _count_snapshot_items(payload)
            elif row["snapshot_type"] == "config_summary":
                config_updated_at = _parse_datetime(row["updated_at"])

        return OpenClawInstanceSnapshotSummary(
            health_status=last_health_status,
            agent_count=agent_count,
            device_count=device_count,
            config_updated_at=config_updated_at,
        )


def _count_snapshot_items(payload: Any) -> int:
    # CLI 與 mock adapter 可能回傳 list 或 {"items": [...]}，這裡統一計數。
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return len(payload["items"])
    return 0


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _parse_datetime_required(value: str) -> datetime:
    return datetime.fromisoformat(value)
