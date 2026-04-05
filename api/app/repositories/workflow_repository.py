from __future__ import annotations

from datetime import datetime
from typing import Any

from app.repositories.database import adapt_json, get_connection
from app.schemas.workflow import (
    WORKFLOW_TYPE_NEWS_BRIEF,
    WORKFLOW_TYPE_SYSTEM_INSPECTION,
    WORKFLOW_TYPE_WEB_SEARCH,
    WorkflowEvent,
    WorkflowNewsBriefPayload,
    WorkflowReportPayload,
    WorkflowRunResponse,
    WorkflowStageRun,
    WorkflowSystemInspectionReportPayload,
    WorkflowWebSearchResult,
)
from app.utils import json_loads, new_id, utc_now_iso


class WorkflowRepository:
    # WorkflowRepository 把整條搜索-分析-報告 run 的主表、階段表與事件表集中管理。
    def create_run(
        self,
        *,
        instance_id: str,
        workflow_type: str,
        input_payload: dict[str, Any],
        stage_configs: list[dict[str, str]],
    ) -> WorkflowRunResponse:
        run_id = new_id("wfr")
        now = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO workflow_runs (
                    id, instance_id, workflow_type, status, current_stage, active_agent_id, overall_progress_percent,
                    input_payload, final_report_json, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    instance_id,
                    workflow_type,
                    "pending",
                    None,
                    None,
                    0,
                    adapt_json(input_payload),
                    None,
                    None,
                    now,
                    now,
                ),
            )

            for stage in stage_configs:
                connection.execute(
                    """
                    INSERT INTO workflow_stage_runs (
                        id, run_id, stage_key, agent_id, status, progress_percent, input_payload, output_payload,
                        started_at, completed_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("wfs"),
                        run_id,
                        stage["stage_key"],
                        stage["agent_id"],
                        "pending",
                        0,
                        adapt_json({}),
                        None,
                        None,
                        None,
                        now,
                        now,
                    ),
                )

        return self.get_run(run_id)

    def list_runs(
        self,
        *,
        instance_id: str | None = None,
        workflow_type: str | None = None,
        limit: int = 20,
    ) -> list[WorkflowRunResponse]:
        # 列表頁只需要最近 runs，因此這裡一次抓主表後再逐筆拼細節。
        query = """
            SELECT id
            FROM workflow_runs
        """
        params: list[Any] = []
        conditions: list[str] = []
        if instance_id:
            conditions.append("instance_id = ?")
            params.append(instance_id)
        if workflow_type:
            conditions.append("workflow_type = ?")
            params.append(workflow_type)
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self.get_run(row["id"]) for row in rows]

    def get_run(self, run_id: str) -> WorkflowRunResponse:
        with get_connection() as connection:
            run_row = connection.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
            stage_rows = connection.execute(
                """
                SELECT * FROM workflow_stage_runs
                WHERE run_id = ?
                ORDER BY CASE stage_key
                    WHEN 'understand' THEN 1
                    WHEN 'monitor' THEN 2
                    WHEN 'search' THEN 3
                    WHEN 'snapshot' THEN 4
                    WHEN 'version_check' THEN 5
                    WHEN 'log_review' THEN 6
                    WHEN 'risk_assessment' THEN 7
                    WHEN 'dedupe' THEN 8
                    WHEN 'filter' THEN 9
                    WHEN 'rank' THEN 10
                    WHEN 'analysis' THEN 11
                    WHEN 'format' THEN 12
                    WHEN 'brief' THEN 13
                    WHEN 'report' THEN 14
                    ELSE 99
                END ASC, created_at ASC
                """,
                (run_id,),
            ).fetchall()
            event_rows = connection.execute(
                "SELECT * FROM workflow_events WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()

        if run_row is None:
            raise KeyError(f"找不到 workflow run：{run_id}")

        final_payload = json_loads(run_row["final_report_json"], None)
        final_report = None
        final_web_result = None
        final_news_brief = None
        final_system_inspection = None
        if isinstance(final_payload, dict):
            if run_row["workflow_type"] == WORKFLOW_TYPE_WEB_SEARCH:
                final_web_result = WorkflowWebSearchResult(**final_payload)
            elif run_row["workflow_type"] == WORKFLOW_TYPE_NEWS_BRIEF:
                final_news_brief = WorkflowNewsBriefPayload(**final_payload)
            elif run_row["workflow_type"] == WORKFLOW_TYPE_SYSTEM_INSPECTION:
                final_system_inspection = WorkflowSystemInspectionReportPayload(**final_payload)
            else:
                final_report = WorkflowReportPayload(**final_payload)

        return WorkflowRunResponse(
            id=run_row["id"],
            instance_id=run_row["instance_id"],
            workflow_type=run_row["workflow_type"],
            status=run_row["status"],
            current_stage=run_row["current_stage"],
            active_agent_id=run_row["active_agent_id"],
            overall_progress_percent=run_row["overall_progress_percent"],
            input_payload=json_loads(run_row["input_payload"], {}),
            final_report=final_report,
            final_web_result=final_web_result,
            final_news_brief=final_news_brief,
            final_system_inspection=final_system_inspection,
            error_message=run_row["error_message"],
            stages=[self._to_stage(row) for row in stage_rows],
            events=[self._to_event(row) for row in event_rows],
            created_at=datetime.fromisoformat(run_row["created_at"]),
            updated_at=datetime.fromisoformat(run_row["updated_at"]),
        )

    def update_run_status(
        self,
        *,
        run_id: str,
        status: str,
        current_stage: str | None,
        active_agent_id: str | None,
        overall_progress_percent: int,
        final_payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE workflow_runs
                SET status = ?, current_stage = ?, active_agent_id = ?, overall_progress_percent = ?,
                    final_report_json = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    current_stage,
                    active_agent_id,
                    overall_progress_percent,
                    adapt_json(final_payload) if final_payload is not None else None,
                    error_message,
                    utc_now_iso(),
                    run_id,
                ),
            )

    def update_stage(
        self,
        *,
        run_id: str,
        stage_key: str,
        status: str,
        progress_percent: int,
        input_payload: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> None:
        # stage update 採 partial merge，讓 orchestrator 每推進一步都能只改需要的欄位。
        with get_connection() as connection:
            current = connection.execute(
                "SELECT * FROM workflow_stage_runs WHERE run_id = ? AND stage_key = ?",
                (run_id, stage_key),
            ).fetchone()

            if current is None:
                raise KeyError(f"找不到 workflow stage：{run_id}:{stage_key}")

            next_input_payload = input_payload if input_payload is not None else json_loads(current["input_payload"], {})
            next_output_payload = output_payload if output_payload is not None else json_loads(current["output_payload"], None)
            next_started_at = started_at if started_at is not None else current["started_at"]
            next_completed_at = completed_at if completed_at is not None else current["completed_at"]

            connection.execute(
                """
                UPDATE workflow_stage_runs
                SET status = ?, progress_percent = ?, input_payload = ?, output_payload = ?,
                    started_at = ?, completed_at = ?, updated_at = ?
                WHERE run_id = ? AND stage_key = ?
                """,
                (
                    status,
                    progress_percent,
                    adapt_json(next_input_payload),
                    adapt_json(next_output_payload) if next_output_payload is not None else None,
                    next_started_at,
                    next_completed_at,
                    utc_now_iso(),
                    run_id,
                    stage_key,
                ),
            )

    def add_event(
        self,
        *,
        run_id: str,
        stage_key: str | None,
        agent_id: str | None,
        status: str,
        progress_percent: int,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        event_id = new_id("wfe")
        created_at = utc_now_iso()
        payload = payload or {}

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO workflow_events (
                    id, run_id, stage_key, agent_id, status, progress_percent, message, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, run_id, stage_key, agent_id, status, progress_percent, message, adapt_json(payload), created_at),
            )

        return WorkflowEvent(
            id=event_id,
            run_id=run_id,
            stage_key=stage_key,
            agent_id=agent_id,
            status=status,
            progress_percent=progress_percent,
            message=message,
            payload=payload,
            created_at=datetime.fromisoformat(created_at),
        )

    def _to_stage(self, row) -> WorkflowStageRun:
        return WorkflowStageRun(
            id=row["id"],
            stage_key=row["stage_key"],
            agent_id=row["agent_id"],
            status=row["status"],
            progress_percent=row["progress_percent"],
            input_payload=json_loads(row["input_payload"], {}),
            output_payload=json_loads(row["output_payload"], None),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _to_event(self, row) -> WorkflowEvent:
        return WorkflowEvent(
            id=row["id"],
            run_id=row["run_id"],
            stage_key=row["stage_key"],
            agent_id=row["agent_id"],
            status=row["status"],
            progress_percent=row["progress_percent"],
            message=row["message"],
            payload=json_loads(row["payload_json"], {}),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
