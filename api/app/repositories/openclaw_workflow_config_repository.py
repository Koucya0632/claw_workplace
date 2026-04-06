from __future__ import annotations

from datetime import datetime

from app.repositories.database import adapt_json, get_connection
from app.schemas.openclaw_workflow_config import (
    OpenClawWorkflowConfigResponse,
    OpenClawWorkflowHandoffPolicy,
    OpenClawWorkflowRoutingRule,
    OpenClawWorkflowSpecialistAgents,
)
from app.utils import json_loads
from app.utils import utc_now_iso


class OpenClawWorkflowConfigRepository:
    # workflow config repository 專門負責主控秘書、核心三槽與專職池的持久化。
    def upsert(
        self,
        *,
        instance_id: str,
        controller_agent_id: str,
        search_agent_id: str,
        analysis_agent_id: str,
        report_agent_id: str,
        specialist_agents: OpenClawWorkflowSpecialistAgents,
        routing_rules: list[OpenClawWorkflowRoutingRule],
        handoff_policy: OpenClawWorkflowHandoffPolicy,
    ) -> OpenClawWorkflowConfigResponse:
        now = utc_now_iso()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_workflow_configs (
                    instance_id, controller_agent_id, search_agent_id, analysis_agent_id, report_agent_id,
                    specialist_agents_json, routing_rules_json, handoff_policy_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id)
                DO UPDATE SET
                    controller_agent_id = excluded.controller_agent_id,
                    search_agent_id = excluded.search_agent_id,
                    analysis_agent_id = excluded.analysis_agent_id,
                    report_agent_id = excluded.report_agent_id,
                    specialist_agents_json = excluded.specialist_agents_json,
                    routing_rules_json = excluded.routing_rules_json,
                    handoff_policy_json = excluded.handoff_policy_json,
                    updated_at = excluded.updated_at
                """,
                (
                    instance_id,
                    controller_agent_id,
                    search_agent_id,
                    analysis_agent_id,
                    report_agent_id,
                    adapt_json(specialist_agents.model_dump()),
                    adapt_json([rule.model_dump() for rule in routing_rules]),
                    adapt_json(handoff_policy.model_dump()),
                    now,
                    now,
                ),
            )

        return self.get(instance_id)

    def get(self, instance_id: str) -> OpenClawWorkflowConfigResponse:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT instance_id, controller_agent_id, search_agent_id, analysis_agent_id, report_agent_id,
                       specialist_agents_json, routing_rules_json, handoff_policy_json, created_at, updated_at
                FROM openclaw_workflow_configs
                WHERE instance_id = ?
                """,
                (instance_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"找不到 workflow config：{instance_id}")

        specialist_agents_payload = json_loads(row["specialist_agents_json"], {})
        routing_rules_payload = json_loads(row["routing_rules_json"], [])
        handoff_policy_payload = json_loads(row["handoff_policy_json"], {})

        return OpenClawWorkflowConfigResponse(
            instance_id=row["instance_id"],
            controller_agent_id=row["controller_agent_id"] or row["search_agent_id"],
            search_agent_id=row["search_agent_id"],
            analysis_agent_id=row["analysis_agent_id"],
            report_agent_id=row["report_agent_id"],
            specialist_agents=OpenClawWorkflowSpecialistAgents(**specialist_agents_payload),
            routing_rules=[OpenClawWorkflowRoutingRule(**item) for item in routing_rules_payload],
            handoff_policy=OpenClawWorkflowHandoffPolicy(**handoff_policy_payload),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
