from __future__ import annotations

from datetime import datetime

from app.repositories.database import get_connection
from app.schemas.openclaw_workflow_config import OpenClawWorkflowConfigResponse
from app.utils import utc_now_iso


class OpenClawWorkflowConfigRepository:
    # workflow config repository 專門負責每個 instance 的三階段 agent mapping。
    def upsert(
        self,
        *,
        instance_id: str,
        search_agent_id: str,
        analysis_agent_id: str,
        report_agent_id: str,
    ) -> OpenClawWorkflowConfigResponse:
        now = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_workflow_configs (
                    instance_id, search_agent_id, analysis_agent_id, report_agent_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id)
                DO UPDATE SET
                    search_agent_id = excluded.search_agent_id,
                    analysis_agent_id = excluded.analysis_agent_id,
                    report_agent_id = excluded.report_agent_id,
                    updated_at = excluded.updated_at
                """,
                (instance_id, search_agent_id, analysis_agent_id, report_agent_id, now, now),
            )

        return self.get(instance_id)

    def get(self, instance_id: str) -> OpenClawWorkflowConfigResponse:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT instance_id, search_agent_id, analysis_agent_id, report_agent_id, created_at, updated_at
                FROM openclaw_workflow_configs
                WHERE instance_id = ?
                """,
                (instance_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"找不到 workflow config：{instance_id}")

        return OpenClawWorkflowConfigResponse(
            instance_id=row["instance_id"],
            search_agent_id=row["search_agent_id"],
            analysis_agent_id=row["analysis_agent_id"],
            report_agent_id=row["report_agent_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
