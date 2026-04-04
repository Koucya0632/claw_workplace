from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from app.repositories.database import adapt_json, get_connection
from app.schemas.openclaw_agent_capability import OpenClawAgentCapabilityRecord
from app.utils import json_loads, new_id, utc_now_iso


class OpenClawAgentCapabilityRepository:
    # Agent capability 屬於本專案自己的管理資料，因此獨立存放在本地 SQLite。
    def upsert(
        self,
        *,
        instance_id: str,
        agent_id: str,
        capability_key: str,
        is_enabled: bool,
        config: dict[str, Any],
    ) -> OpenClawAgentCapabilityRecord:
        current = self.get(instance_id=instance_id, agent_id=agent_id, capability_key=capability_key)
        record_id = current.id if current else new_id("occap")
        created_at = current.created_at.isoformat() if current else utc_now_iso()
        updated_at = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_agent_capabilities (
                    id, instance_id, agent_id, capability_key, is_enabled, config_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id, agent_id, capability_key)
                DO UPDATE SET
                    is_enabled = excluded.is_enabled,
                    config_json = excluded.config_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record_id,
                    instance_id,
                    agent_id,
                    capability_key,
                    int(is_enabled),
                    adapt_json(config),
                    created_at,
                    updated_at,
                ),
            )

        updated = self.get(instance_id=instance_id, agent_id=agent_id, capability_key=capability_key)
        if updated is None:
            raise RuntimeError("Agent capability upsert 後無法重新讀取資料。")
        return updated

    def get(
        self,
        *,
        instance_id: str,
        agent_id: str,
        capability_key: str,
    ) -> OpenClawAgentCapabilityRecord | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM openclaw_agent_capabilities
                WHERE instance_id = ? AND agent_id = ? AND capability_key = ?
                """,
                (instance_id, agent_id, capability_key),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_model(row)

    def list_for_agent(self, *, instance_id: str, agent_id: str) -> list[OpenClawAgentCapabilityRecord]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM openclaw_agent_capabilities
                WHERE instance_id = ? AND agent_id = ?
                ORDER BY capability_key ASC
                """,
                (instance_id, agent_id),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def list_for_instance(self, *, instance_id: str) -> list[OpenClawAgentCapabilityRecord]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM openclaw_agent_capabilities
                WHERE instance_id = ?
                ORDER BY agent_id ASC, capability_key ASC
                """,
                (instance_id,),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def list_for_capability(self, *, capability_key: str) -> list[OpenClawAgentCapabilityRecord]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM openclaw_agent_capabilities
                WHERE capability_key = ?
                ORDER BY instance_id ASC, agent_id ASC
                """,
                (capability_key,),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def list_enabled_for_capability(self, *, capability_key: str) -> list[OpenClawAgentCapabilityRecord]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM openclaw_agent_capabilities
                WHERE capability_key = ? AND is_enabled = 1
                ORDER BY instance_id ASC, agent_id ASC
                """,
                (capability_key,),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def find_conflicts(
        self,
        *,
        capability_key: str,
        agent_id: str,
        exclude_instance_id: str,
    ) -> list[OpenClawAgentCapabilityRecord]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM openclaw_agent_capabilities
                WHERE capability_key = ? AND agent_id = ? AND instance_id != ?
                ORDER BY updated_at DESC
                """,
                (capability_key, agent_id, exclude_instance_id),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_enabled_by_agent_id(
        self,
        *,
        capability_key: str,
        agent_id: str,
    ) -> OpenClawAgentCapabilityRecord | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM openclaw_agent_capabilities
                WHERE capability_key = ? AND agent_id = ? AND is_enabled = 1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (capability_key, agent_id),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_model(row)

    def _row_to_model(self, row: sqlite3.Row) -> OpenClawAgentCapabilityRecord:
        return OpenClawAgentCapabilityRecord(
            id=row["id"],
            instance_id=row["instance_id"],
            agent_id=row["agent_id"],
            capability_key=row["capability_key"],
            is_enabled=bool(row["is_enabled"]),
            config=json_loads(row["config_json"], {}),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
