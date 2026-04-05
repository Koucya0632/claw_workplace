from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OpenClawWorkflowSpecialistBinding(BaseModel):
    # 專職 agent 可以先映射到同一個實體 agent，因此 binding 需要同時表達 agent_id 與是否啟用。
    agent_id: str = ""
    enabled: bool = False


class OpenClawWorkflowSpecialistAgents(BaseModel):
    # 第一版固定提供 6 個可擴充的專職槽位，核心 search / analysis / report 則維持原有欄位。
    search_web: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)
    organizer: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)
    writer: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)
    test_design: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)
    ui_review: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)
    monitor: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)
    daily_news_brief: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)
    system_inspection: OpenClawWorkflowSpecialistBinding = Field(default_factory=OpenClawWorkflowSpecialistBinding)


class OpenClawWorkflowRoutingRule(BaseModel):
    # routing rule 以高階條件與 route_to 表示，先夠用於智能辦公室 / 搜尋整理場景。
    key: str
    label: str
    enabled: bool = True
    conditions: list[str] = Field(default_factory=list)
    route_to: list[str] = Field(default_factory=list)


class OpenClawWorkflowHandoffPolicy(BaseModel):
    # handoff policy 集中表達重試與人工接管條件，避免散落在各 service 的魔術數字。
    manual_review_required_on_conflict: bool = True
    manual_review_required_on_high_risk: bool = True
    max_search_retry_count: int = 1
    max_report_retry_count: int = 2
    timeout_escalation_seconds: int = 180
    fallback_mode: Literal["controller", "fail_fast"] = "controller"


class OpenClawWorkflowConfigUpdateRequest(BaseModel):
    # workflow config 升級為主控秘書 + 核心三槽 + 專職池，兼容現有三階段流程。
    instance_id: str
    controller_agent_id: str
    search_agent_id: str
    analysis_agent_id: str
    report_agent_id: str
    specialist_agents: OpenClawWorkflowSpecialistAgents = Field(default_factory=OpenClawWorkflowSpecialistAgents)
    routing_rules: list[OpenClawWorkflowRoutingRule] = Field(default_factory=list)
    handoff_policy: OpenClawWorkflowHandoffPolicy = Field(default_factory=OpenClawWorkflowHandoffPolicy)


class OpenClawWorkflowConfigResponse(BaseModel):
    # 回應同時提供 controller、核心 agent 與專職池，方便前端直接畫出協作關係。
    instance_id: str
    controller_agent_id: str
    search_agent_id: str
    analysis_agent_id: str
    report_agent_id: str
    specialist_agents: OpenClawWorkflowSpecialistAgents = Field(default_factory=OpenClawWorkflowSpecialistAgents)
    routing_rules: list[OpenClawWorkflowRoutingRule] = Field(default_factory=list)
    handoff_policy: OpenClawWorkflowHandoffPolicy = Field(default_factory=OpenClawWorkflowHandoffPolicy)
    created_at: datetime
    updated_at: datetime
