from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


WORKFLOW_STAGE_KEYS = ("search", "analysis", "report")


class WorkflowSearchReportCreateRequest(BaseModel):
    # 一體化流程的入口只需要 query 與執行 instance，其餘條件都是附加篩選。
    instance_id: str
    query: str
    source_id: Optional[str] = None


class WorkflowSearchDocumentItem(BaseModel):
    # 搜索階段至少要交出候選文件，前端才能把證據鏈展示清楚。
    document_id: str
    filename: str
    relative_path: str
    source_id: str
    source_name: str
    snippet: str
    reason: str


class WorkflowEvidenceItem(BaseModel):
    # 分析與報告階段都會重用證據結構，因此先集中在 workflow schema。
    document_id: str
    filename: str
    quote: str
    reason: str


class WorkflowSearchStageOutput(BaseModel):
    # 搜索階段除了候選文件，也要交代搜索代理最後選了哪些證據。
    summary: str
    candidates: list[WorkflowSearchDocumentItem] = Field(default_factory=list)
    selected_documents: list[WorkflowSearchDocumentItem] = Field(default_factory=list)
    source_overview: list[str] = Field(default_factory=list)


class WorkflowAnalysisStageOutput(BaseModel):
    # 分析階段負責把多文件內容收斂成重點、風險、待辦與證據。
    summary: str
    highlights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)
    evidence: list[WorkflowEvidenceItem] = Field(default_factory=list)


class WorkflowReportSection(BaseModel):
    # 報告頁需要結構化章節，避免只能渲染一大片 Markdown 原文。
    title: str
    summary: str = ""
    bullets: list[str] = Field(default_factory=list)
    body: str = ""


class WorkflowReportPayload(BaseModel):
    # 最終報告保留結構化欄位與 markdown，前端展示與匯出都會用到。
    title: str
    executive_summary: str
    highlights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    evidence: list[WorkflowEvidenceItem] = Field(default_factory=list)
    sections: list[WorkflowReportSection] = Field(default_factory=list)
    appendix: list[str] = Field(default_factory=list)
    markdown: str


class WorkflowStageRun(BaseModel):
    # 每個階段卡片都直接綁定這個模型，讓 agent / progress / input / output 一次到位。
    id: str
    stage_key: str
    agent_id: str
    status: str
    progress_percent: int
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: Optional[dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkflowEvent(BaseModel):
    # Timeline 需要知道事件屬於哪個 stage、由哪個 agent 產生，以及當時進度。
    id: str
    run_id: str
    stage_key: Optional[str] = None
    agent_id: Optional[str] = None
    status: str
    progress_percent: int
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class WorkflowRunResponse(BaseModel):
    # 搜索主流程頁會以這個模型做輪詢，因此把總覽與細節都放在同一份回應裡。
    id: str
    instance_id: str
    workflow_type: str
    status: str
    current_stage: Optional[str] = None
    active_agent_id: Optional[str] = None
    overall_progress_percent: int
    input_payload: dict[str, Any] = Field(default_factory=dict)
    final_report: Optional[WorkflowReportPayload] = None
    error_message: Optional[str] = None
    stages: list[WorkflowStageRun] = Field(default_factory=list)
    events: list[WorkflowEvent] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
