from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from app.repositories.database import adapt_json, get_connection
from app.schemas.common import RoleStatusEvent
from app.schemas.task import SummaryTaskResult, TaskStatusResponse
from app.utils import json_loads, new_id, utc_now_iso


class TaskRepository:
    # TaskRepository 統一管理任務主表與角色事件表。
    def create_task(self, task_type: str, input_payload: dict[str, Any]) -> TaskStatusResponse:
        task_id = new_id("tsk")
        now = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO tasks (id, task_type, status, input_payload, result_payload, error_message, created_by, updated_by, role_hint, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task_type,
                    "pending",
                    adapt_json(input_payload),
                    None,
                    None,
                    "system",
                    "system",
                    "member",
                    now,
                    now,
                ),
            )

        return self.get_task(task_id)

    def update_status(
        self,
        task_id: str,
        status: str,
        result_payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, result_payload = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    adapt_json(result_payload) if result_payload is not None else None,
                    error_message,
                    utc_now_iso(),
                    task_id,
                ),
            )

    def add_event(
        self,
        task_id: str,
        role_name: str,
        role_status: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> RoleStatusEvent:
        event_id = new_id("evt")
        created_at = utc_now_iso()
        metadata = metadata or {}

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO task_events (id, task_id, role_name, role_status, message, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, task_id, role_name, role_status, message, adapt_json(metadata), created_at),
            )

        return RoleStatusEvent(
            id=event_id,
            role_name=role_name,
            role_status=role_status,
            message=message,
            metadata=metadata,
            created_at=datetime.fromisoformat(created_at),
        )

    def get_task(self, task_id: str) -> TaskStatusResponse:
        with get_connection() as connection:
            task_row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            event_rows = connection.execute(
                "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()

        if task_row is None:
            raise KeyError(f"找不到任務：{task_id}")

        result_payload = json_loads(task_row["result_payload"], None)
        task_result = SummaryTaskResult(**result_payload) if result_payload else None

        return TaskStatusResponse(
            id=task_row["id"],
            task_type=task_row["task_type"],
            status=task_row["status"],
            input_payload=json_loads(task_row["input_payload"], {}),
            result_payload=task_result,
            error_message=task_row["error_message"],
            events=[
                RoleStatusEvent(
                    id=row["id"],
                    role_name=row["role_name"],
                    role_status=row["role_status"],
                    message=row["message"],
                    metadata=json_loads(row["metadata"], {}),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in event_rows
            ],
            created_at=datetime.fromisoformat(task_row["created_at"]),
            updated_at=datetime.fromisoformat(task_row["updated_at"]),
        )

