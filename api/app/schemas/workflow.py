from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.knowledge import BusinessType


WORKFLOW_STAGE_KEYS = ("search", "analysis", "report")
WORKFLOW_TYPE_SEARCH_REPORT = "search_report"
WORKFLOW_TYPE_WEB_SEARCH = "web_search"
WORKFLOW_TYPE_NEWS_BRIEF = "news_brief"
WORKFLOW_TYPE_SYSTEM_INSPECTION = "system_inspection"
WEB_SEARCH_OUTPUT_FORMATS = ("summary", "bullets", "table", "comparison")


class WorkflowSearchReportCreateRequest(BaseModel):
    # 一體化流程的入口只需要 query 與執行 instance，其餘條件都是附加篩選。
    instance_id: str
    query: str
    source_id: Optional[str] = None


class WorkflowWebSearchCreateRequest(BaseModel):
    # Web Search 入口會把搜尋主題、條件與輸出格式一次交給 workflow，由 agent 逐階段消化。
    instance_id: str
    topic: str
    target_urls: list[str] = Field(default_factory=list)
    target_sites: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_exclude: list[str] = Field(default_factory=list)
    focus_points: list[str] = Field(default_factory=list)
    output_format: Literal["summary", "bullets", "table", "comparison"] = "summary"
    include_project_sources: bool = False
    source_id: Optional[str] = None
    result_limit: int = Field(default=5, ge=1, le=10)
    business_type: Optional[BusinessType] = None
    auto_publish: bool = True
    source_merge_hint: Optional[str] = None
    ingest_mode: Literal["auto_store"] = "auto_store"


class WorkflowNewsBriefCreateRequest(BaseModel):
    instance_id: str


class WorkflowSystemInspectionCreateRequest(BaseModel):
    instance_id: str


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


class WorkflowWebSearchSourceItem(BaseModel):
    # Web Search 來源可能來自外網或專案索引，因此欄位同時容納 URL 與 document metadata。
    title: str
    source_type: str
    snippet: str
    reason: str
    matched_keywords: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    domain: Optional[str] = None
    source_name: Optional[str] = None
    document_id: Optional[str] = None
    relative_path: Optional[str] = None


class WorkflowWebSearchUnderstandOutput(BaseModel):
    # Understand 階段先把使用者意圖與搜尋條件正規化，後續 search/filter/format 才能穩定接棒。
    goal_summary: str
    normalized_topic: str
    search_plan: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    target_urls: list[str] = Field(default_factory=list)
    target_sites: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_exclude: list[str] = Field(default_factory=list)
    focus_points: list[str] = Field(default_factory=list)
    output_format: str
    include_project_sources: bool = False


class WorkflowWebSearchSearchOutput(BaseModel):
    # Search 階段只負責廣搜與蒐集候選來源，先不做太重的整理與格式化。
    summary: str
    search_queries: list[str] = Field(default_factory=list)
    sources: list[WorkflowWebSearchSourceItem] = Field(default_factory=list)


class WorkflowWebSearchFilterOutput(BaseModel):
    # Filter 階段會把噪音來源排掉，留下真正要交給 format 階段的核心內容。
    summary: str
    kept_sources: list[WorkflowWebSearchSourceItem] = Field(default_factory=list)
    rejected_sources: list[WorkflowWebSearchSourceItem] = Field(default_factory=list)
    discarded_count: int = 0
    extracted_points: list[str] = Field(default_factory=list)
    focus_answers: list[str] = Field(default_factory=list)
    ingest_reason: str = ""
    suggested_business_type: Optional[BusinessType] = None
    suggested_topic_tags: list[str] = Field(default_factory=list)


class WorkflowWebSearchIngestOutput(BaseModel):
    source_resolution: Literal["explicit_source", "merged", "created"]
    created_source_id: Optional[str] = None
    merged_source_id: Optional[str] = None
    ingestion_run_id: Optional[str] = None
    stored_documents: list[str] = Field(default_factory=list)
    updated_documents: list[str] = Field(default_factory=list)
    rejected_documents: list[str] = Field(default_factory=list)
    ingest_summary: str
    source_name: Optional[str] = None


class WorkflowWebSearchResult(BaseModel):
    # 最終 Web Search 結果要同時適合頁面閱讀、後續接續 workflow、與歷史回看。
    title: str
    requested_format: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    focus_answers: list[str] = Field(default_factory=list)
    included_sources: list[WorkflowWebSearchSourceItem] = Field(default_factory=list)
    applied_filters: list[str] = Field(default_factory=list)
    ingestion_run_id: Optional[str] = None
    ingest_result: Optional[WorkflowWebSearchIngestOutput] = None
    structured_output: str
    markdown: str


class WorkflowNewsSourceItem(BaseModel):
    title: str
    snippet: str
    source_name: str
    reason: str
    published_at: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None


class WorkflowNewsMonitorOutput(BaseModel):
    goal_summary: str
    tracking_scope: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    watch_focus: list[str] = Field(default_factory=list)


class WorkflowNewsSearchOutput(BaseModel):
    summary: str
    raw_sources: list[WorkflowNewsSourceItem] = Field(default_factory=list)


class WorkflowNewsStory(BaseModel):
    title: str
    summary: str
    importance_reason: str
    possible_impact: str = ""
    sources: list[WorkflowNewsSourceItem] = Field(default_factory=list)
    published_at: Optional[str] = None
    background: str = ""
    watch_points: list[str] = Field(default_factory=list)
    event_key: str = ""


class WorkflowNewsDedupeOutput(BaseModel):
    summary: str
    unique_stories: list[WorkflowNewsStory] = Field(default_factory=list)
    removed_duplicates: int = 0
    dedupe_notes: list[str] = Field(default_factory=list)


class WorkflowNewsRankOutput(BaseModel):
    summary: str
    top_stories: list[WorkflowNewsStory] = Field(default_factory=list)
    other_stories: list[WorkflowNewsStory] = Field(default_factory=list)
    trend_summary: str = ""
    watch_items: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class WorkflowNewsBriefPayload(BaseModel):
    title: str
    top_stories: list[WorkflowNewsStory] = Field(default_factory=list)
    other_stories: list[WorkflowNewsStory] = Field(default_factory=list)
    trend_summary: str
    watch_items: list[str] = Field(default_factory=list)
    dedupe_notes: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    raw_sources: list[WorkflowNewsSourceItem] = Field(default_factory=list)
    markdown: str
    delivery_status: str = "pending"
    delivery_target: Optional[str] = None
    delivery_error: Optional[str] = None


class WorkflowSystemInspectionSnapshotOutput(BaseModel):
    current_version: str = ""
    latest_touched_version: Optional[str] = None
    instance_count: int = 0
    workflow_mapping: dict[str, Any] = Field(default_factory=dict)
    capability_summary: list[dict[str, Any]] = Field(default_factory=list)
    plugin_summary: dict[str, Any] = Field(default_factory=dict)
    recent_workflow_failures: list[dict[str, Any]] = Field(default_factory=list)
    recent_operation_logs: list[dict[str, Any]] = Field(default_factory=list)
    gateway_log_excerpt: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowSystemInspectionVersionOutput(BaseModel):
    current_version: str
    latest_version: Optional[str] = None
    latest_version_status: str = "unknown"
    version_gap: str = ""
    release_summary: list[str] = Field(default_factory=list)
    breaking_changes: list[str] = Field(default_factory=list)
    deprecations: list[str] = Field(default_factory=list)
    compatibility_risks: list[str] = Field(default_factory=list)
    affected_areas: dict[str, list[str]] = Field(default_factory=dict)
    upgrade_recommendation: Literal["upgrade_now", "test_before_upgrade", "do_not_upgrade_yet"] = "test_before_upgrade"
    regression_test_checklist: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)


class WorkflowSystemInspectionLogIssue(BaseModel):
    issue_key: str
    category: Literal["error", "warning", "timeout", "retry", "crash", "performance", "security", "config_drift"]
    description: str
    frequency: int
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    possible_root_causes: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    impact_scope: str = ""
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    fix_actions: list[str] = Field(default_factory=list)
    optimization_actions: list[str] = Field(default_factory=list)
    priority: Literal["p0", "p1", "p2", "p3"] = "p2"
    assumptions: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)


class WorkflowSystemInspectionLogReviewOutput(BaseModel):
    summary: str
    issues: list[WorkflowSystemInspectionLogIssue] = Field(default_factory=list)
    log_window_hours: int = 24
    inspected_log_count: int = 0


class WorkflowSystemInspectionRiskOutput(BaseModel):
    summary: str
    upgrade_recommendation: Literal["upgrade_now", "test_before_upgrade", "do_not_upgrade_yet"] = "test_before_upgrade"
    high_priority_risks: list[WorkflowSystemInspectionLogIssue] = Field(default_factory=list)
    immediate_actions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)


class WorkflowSystemInspectionReportPayload(BaseModel):
    title: str
    inspection_summary: list[str] = Field(default_factory=list)
    version_update_check: WorkflowSystemInspectionVersionOutput
    log_review: WorkflowSystemInspectionLogReviewOutput
    high_priority_risks: list[WorkflowSystemInspectionLogIssue] = Field(default_factory=list)
    fix_and_optimization_actions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recommended_execution_order: list[str] = Field(default_factory=list)
    telegram_summary: str = ""
    markdown: str
    delivery_status: str = "pending"
    delivery_target: Optional[str] = None
    delivery_error: Optional[str] = None


class WorkflowSystemInspectionReportDraft(BaseModel):
    title: str = "系統巡檢與風險評估報告"
    inspection_summary: list[str] = Field(default_factory=list)
    fix_and_optimization_actions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recommended_execution_order: list[str] = Field(default_factory=list)
    telegram_summary: str = ""
    markdown: str = ""


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
    final_web_result: Optional[WorkflowWebSearchResult] = None
    final_ingestion_run_id: Optional[str] = None
    final_ingest_result: Optional[WorkflowWebSearchIngestOutput] = None
    final_news_brief: Optional[WorkflowNewsBriefPayload] = None
    final_system_inspection: Optional[WorkflowSystemInspectionReportPayload] = None
    error_message: Optional[str] = None
    stages: list[WorkflowStageRun] = Field(default_factory=list)
    events: list[WorkflowEvent] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
