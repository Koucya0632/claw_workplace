export type SourceType = "local" | "google_drive" | "notion" | "web_page" | "rss_feed" | "url_list";

export interface SourceConfig {
  path?: string | null;
  url?: string | null;
  urls?: string[];
  root_page_id?: string | null;
  database_id?: string | null;
  workspace_name?: string | null;
  extra?: Record<string, unknown>;
}

export interface SourceResponse {
  id: string;
  name: string;
  type: SourceType;
  status: string;
  is_enabled: boolean;
  config: SourceConfig;
  document_count: number;
  last_sync_status: string;
  last_sync_error?: string | null;
  last_successful_sync_at?: string | null;
  last_failed_sync_at?: string | null;
  last_sync_result: SourceSyncResult;
  last_scan_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceSyncResult {
  scanned_count: number;
  skipped_count: number;
  error_count: number;
}

export interface SourceSyncEventResponse {
  id: string;
  source_id: string;
  status: string;
  message: string;
  scanned_count: number;
  skipped_count: number;
  error_count: number;
  created_at: string;
}

export interface SourceDetailResponse extends SourceResponse {
  version_count: number;
  recent_activity: SourceSyncEventResponse[];
}

export interface SourceMetricsResponse {
  total_sources: number;
  healthy_sources: number;
  warning_sources: number;
  failed_sources: number;
  syncing_sources: number;
  disabled_sources: number;
  recently_updated_sources: number;
  recent_sync_failures: number;
}

export interface SourceUpdateRequest {
  name?: string;
  config?: SourceConfig;
  is_enabled?: boolean;
}

export interface ScanSourceResponse {
  source_id: string;
  scanned_count: number;
  skipped_count: number;
  errors: string[];
  scanned_at: string;
}

export interface SearchRequest {
  query: string;
  source_id?: string;
  start_date?: string;
  end_date?: string;
  mode?: string;
}

export interface SearchResultItem {
  document_id: string;
  source_id: string;
  source_name: string;
  filename: string;
  relative_path: string;
  snippet: string;
  matched_on: string;
  modified_at: string;
  source_url?: string | null;
  canonical_url?: string | null;
  published_at?: string | null;
  business_type?: string | null;
  topic_tags?: string[];
  credibility_tier?: string | null;
}

export interface SearchResponse {
  items: SearchResultItem[];
  total: number;
  query_time_ms: number;
  semantic_search_ready: boolean;
}

export interface DocumentSummary {
  id: string;
  source_id: string;
  filename: string;
  relative_path: string;
  extension: string;
  modified_at: string;
  content_preview: string;
  extracted_text: string;
  source_url?: string | null;
  canonical_url?: string | null;
  published_at?: string | null;
  language?: string | null;
  status?: string | null;
  business_type?: string | null;
  topic_tags?: string[];
  credibility_tier?: string | null;
  metadata?: Record<string, unknown>;
}

export interface DocumentVersionSummary {
  id: string;
  filename: string;
  source_url?: string | null;
  canonical_url?: string | null;
  checksum: string;
  version_group_id?: string | null;
  version_number: number;
  supersedes_document_id?: string | null;
  status?: string | null;
  indexed_at: string;
  published_at?: string | null;
}

export type KnowledgeSourceType = "web_page" | "url_list" | "rss_feed";
export type BusinessType = "support" | "product" | "engineering" | "compliance" | "operations" | "market" | "finance" | "security";

export interface KnowledgeIngestRequest {
  topic: string;
  query?: string;
  source_id?: string;
  source_name?: string;
  source_type?: KnowledgeSourceType;
  urls: string[];
  domains: string[];
  keywords: string[];
  must_include: string[];
  must_exclude: string[];
  business_type?: BusinessType | null;
  time_window_days?: number | null;
  limit: number;
  auto_publish: boolean;
}

export interface KnowledgeIngestionItemResponse {
  id: string;
  candidate_url: string;
  normalized_url?: string | null;
  title: string;
  status: string;
  reject_reason?: string | null;
  document_id?: string | null;
  trust_score?: number | null;
  relevance_score?: number | null;
  duplicate_score?: number | null;
  source_domain: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeIngestionRunResponse {
  id: string;
  source_id: string;
  source_name: string;
  topic: string;
  query: string;
  status: string;
  total_candidates: number;
  accepted_count: number;
  updated_count: number;
  rejected_count: number;
  created_at: string;
  completed_at?: string | null;
  items: KnowledgeIngestionItemResponse[];
  metadata: Record<string, unknown>;
}

export interface RoleStatusEvent {
  id: string;
  role_name: string;
  role_status: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SummaryTaskResult {
  summary: string;
  highlights: string[];
  todos: string[];
  source_quotes: string[];
  markdown: string;
}

export interface TaskStatusResponse {
  id: string;
  task_type: string;
  status: string;
  input_payload: Record<string, unknown>;
  result_payload?: SummaryTaskResult | null;
  error_message?: string | null;
  events: RoleStatusEvent[];
  created_at: string;
  updated_at: string;
}

export interface MarkdownReportResponse {
  filename: string;
  markdown: string;
}

export interface OpenClawApiError {
  message: string;
  detail?: string | null;
}

export interface OpenClawApiMeta {
  instanceId?: string | null;
  sourceMode?: string | null;
  durationMs?: number | null;
}

export interface OpenClawApiResponse<T> {
  success: boolean;
  data: T;
  error?: OpenClawApiError | null;
  meta: OpenClawApiMeta;
}

export interface OpenClawInstanceSnapshotSummary {
  health_status?: string | null;
  agent_count: number;
  device_count: number;
  config_updated_at?: string | null;
}

export interface OpenClawInstanceResponse {
  id: string;
  name: string;
  gateway_url: string;
  is_active: boolean;
  has_token: boolean;
  last_health_status?: string | null;
  last_health_checked_at?: string | null;
  snapshot_summary: OpenClawInstanceSnapshotSummary;
  created_at: string;
  updated_at: string;
}

export interface OpenClawHealthResponse {
  status: string;
  checked_at: string;
  details: Record<string, unknown>;
}

export interface OpenClawOperationLogRecord {
  id: string;
  instance_id?: string | null;
  operation_type: string;
  target_type: string;
  target_id?: string | null;
  status: string;
  error_message?: string | null;
  request_summary: Record<string, unknown>;
  response_summary?: Record<string, unknown> | null;
  source_mode: string;
  created_at: string;
}

export interface OpenClawAgentSummary {
  id: string;
  name: string;
  status: string;
  channel_count: number;
  metadata: Record<string, unknown>;
}

export interface OpenClawAgentCapabilityRecord {
  id: string;
  instance_id: string;
  agent_id: string;
  capability_key: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
  native_plugin_id?: string | null;
  native_plugin_ready: boolean;
  native_plugin_enabled: boolean;
  bridge_ready: boolean;
  last_sync_status?: string | null;
  last_sync_message?: string | null;
  workspace_synced: boolean;
  message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpenClawDeviceSummary {
  id: string;
  name: string;
  status: string;
  platform?: string | null;
  pending_action?: string | null;
  metadata: Record<string, unknown>;
}

export interface OpenClawConfigResponse {
  path: string;
  value: unknown;
}

export interface OpenClawConfigValidationResponse {
  valid: boolean;
  messages: string[];
}

export interface OpenClawLogEntry {
  timestamp?: string | null;
  level?: string | null;
  message: string;
  raw?: string | null;
}

export interface OpenClawWorkflowConfigResponse {
  instance_id: string;
  controller_agent_id: string;
  search_agent_id: string;
  analysis_agent_id: string;
  report_agent_id: string;
  specialist_agents: OpenClawWorkflowSpecialistAgents;
  routing_rules: OpenClawWorkflowRoutingRule[];
  handoff_policy: OpenClawWorkflowHandoffPolicy;
  created_at: string;
  updated_at: string;
}

export interface OpenClawWorkflowSpecialistBinding {
  agent_id: string;
  enabled: boolean;
}

export interface OpenClawWorkflowSpecialistAgents {
  search_web: OpenClawWorkflowSpecialistBinding;
  organizer: OpenClawWorkflowSpecialistBinding;
  writer: OpenClawWorkflowSpecialistBinding;
  test_design: OpenClawWorkflowSpecialistBinding;
  ui_review: OpenClawWorkflowSpecialistBinding;
  monitor: OpenClawWorkflowSpecialistBinding;
  fullstack_engineer: OpenClawWorkflowSpecialistBinding;
  daily_news_brief: OpenClawWorkflowSpecialistBinding;
  system_inspection: OpenClawWorkflowSpecialistBinding;
}

export interface OpenClawWorkflowRoutingRule {
  key: string;
  label: string;
  enabled: boolean;
  conditions: string[];
  route_to: string[];
}

export interface OpenClawWorkflowHandoffPolicy {
  manual_review_required_on_conflict: boolean;
  manual_review_required_on_high_risk: boolean;
  max_search_retry_count: number;
  max_report_retry_count: number;
  timeout_escalation_seconds: number;
  fallback_mode: "controller" | "fail_fast";
}

export interface OpenClawDailyNewsConfigResponse {
  instance_id: string;
  enabled: boolean;
  brief_name: string;
  topic: string;
  keywords: string[];
  industries: string[];
  regions: string[];
  people: string[];
  companies: string[];
  source_domains: string[];
  source_urls: string[];
  must_include: string[];
  must_exclude: string[];
  focus_points: string[];
  output_format: WebSearchOutputFormat;
  delivery_channel: "telegram" | "discord";
  telegram_target: string;
  discord_channel_id: string;
  schedule_timezone: string;
  schedule_time: string;
  last_scheduled_date?: string | null;
  last_run_id?: string | null;
  last_delivery_status?: string | null;
  last_delivery_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpenClawSystemInspectionConfigResponse {
  instance_id: string;
  enabled: boolean;
  schedule_timezone: string;
  schedule_time: string;
  delivery_channel: "telegram" | "discord";
  telegram_target: string;
  discord_channel_id: string;
  version_check_enabled: boolean;
  log_review_enabled: boolean;
  log_review_window_hours: number;
  log_review_limit: number;
  official_release_url: string;
  last_scheduled_date?: string | null;
  last_run_id?: string | null;
  last_delivery_status?: string | null;
  last_delivery_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpenClawDevelopmentConfigResponse {
  instance_id: string;
  enabled: boolean;
  delivery_channel: "discord";
  discord_channel_id: string;
  last_run_id?: string | null;
  last_delivery_status?: string | null;
  last_delivery_error?: string | null;
  config_source: "stored" | "default";
  effective_delivery_source: "development_config" | "runtime_route" | "none";
  effective_discord_channel_id?: string | null;
  effective_delivery_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export type WorkflowType = "search_report" | "web_search" | "news_brief" | "system_inspection" | "development_execution";
export type WebSearchOutputFormat = "summary" | "bullets" | "table" | "comparison";

export interface WorkflowSearchDocumentItem {
  document_id: string;
  filename: string;
  relative_path: string;
  source_id: string;
  source_name: string;
  snippet: string;
  reason: string;
}

export interface WorkflowEvidenceItem {
  document_id: string;
  filename: string;
  quote: string;
  reason: string;
}

export interface WorkflowReportSection {
  title: string;
  summary: string;
  bullets: string[];
  body: string;
}

export interface WorkflowReportPayload {
  title: string;
  executive_summary: string;
  highlights: string[];
  recommendations: string[];
  evidence: WorkflowEvidenceItem[];
  sections: WorkflowReportSection[];
  appendix: string[];
  markdown: string;
}

export interface WorkflowWebSearchSourceItem {
  title: string;
  source_type: string;
  snippet: string;
  reason: string;
  matched_keywords: string[];
  url?: string | null;
  domain?: string | null;
  source_name?: string | null;
  document_id?: string | null;
  relative_path?: string | null;
}

export interface WorkflowWebSearchResult {
  title: string;
  requested_format: WebSearchOutputFormat;
  summary: string;
  key_points: string[];
  focus_answers: string[];
  included_sources: WorkflowWebSearchSourceItem[];
  applied_filters: string[];
  ingestion_run_id?: string | null;
  ingest_result?: WorkflowWebSearchIngestOutput | null;
  structured_output: string;
  markdown: string;
}

export interface WorkflowWebSearchIngestOutput {
  source_resolution: "explicit_source" | "merged" | "created";
  created_source_id?: string | null;
  merged_source_id?: string | null;
  ingestion_run_id?: string | null;
  stored_documents: string[];
  updated_documents: string[];
  rejected_documents: string[];
  ingest_summary: string;
  source_name?: string | null;
}

export interface WorkflowNewsSourceItem {
  title: string;
  snippet: string;
  source_name: string;
  reason: string;
  published_at?: string | null;
  url?: string | null;
  domain?: string | null;
}

export interface WorkflowNewsStory {
  title: string;
  summary: string;
  importance_reason: string;
  possible_impact: string;
  sources: WorkflowNewsSourceItem[];
  published_at?: string | null;
  background: string;
  watch_points: string[];
  event_key: string;
}

export interface WorkflowNewsBriefPayload {
  title: string;
  top_stories: WorkflowNewsStory[];
  other_stories: WorkflowNewsStory[];
  trend_summary: string;
  watch_items: string[];
  dedupe_notes: string[];
  uncertainties: string[];
  raw_sources: WorkflowNewsSourceItem[];
  markdown: string;
  delivery_status: string;
  delivery_target?: string | null;
  delivery_error?: string | null;
}

export interface WorkflowSystemInspectionLogIssue {
  issue_key: string;
  category: "error" | "warning" | "timeout" | "retry" | "crash" | "performance" | "security" | "config_drift";
  description: string;
  frequency: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  possible_root_causes: string[];
  affected_components: string[];
  impact_scope: string;
  severity: "critical" | "high" | "medium" | "low";
  fix_actions: string[];
  optimization_actions: string[];
  priority: "p0" | "p1" | "p2" | "p3";
  assumptions: string[];
  verification_steps: string[];
}

export interface WorkflowSystemInspectionVersionOutput {
  current_version: string;
  latest_version?: string | null;
  latest_version_status: string;
  update_available?: boolean | null;
  channel_label?: string | null;
  version_source?: "openclaw_cli_update" | "official_release_fallback" | "unknown";
  version_gap: string;
  release_summary: string[];
  breaking_changes: string[];
  deprecations: string[];
  compatibility_risks: string[];
  affected_areas: Record<string, string[]>;
  upgrade_recommendation: "upgrade_now" | "test_before_upgrade" | "do_not_upgrade_yet";
  regression_test_checklist: string[];
  assumptions: string[];
  verification_steps: string[];
}

export interface WorkflowSystemInspectionLogReviewOutput {
  summary: string;
  issues: WorkflowSystemInspectionLogIssue[];
  log_window_hours: number;
  inspected_log_count: number;
}

export interface WorkflowSystemInspectionRiskOutput {
  summary: string;
  upgrade_recommendation: "upgrade_now" | "test_before_upgrade" | "do_not_upgrade_yet";
  high_priority_risks: WorkflowSystemInspectionLogIssue[];
  immediate_actions: string[];
  assumptions: string[];
  verification_steps: string[];
}

export interface WorkflowSystemInspectionReportPayload {
  title: string;
  inspection_summary: string[];
  version_update_check: WorkflowSystemInspectionVersionOutput;
  log_review: WorkflowSystemInspectionLogReviewOutput;
  high_priority_risks: WorkflowSystemInspectionLogIssue[];
  fix_and_optimization_actions: string[];
  open_questions: string[];
  recommended_execution_order: string[];
  telegram_summary: string;
  markdown: string;
  delivery_status: string;
  delivery_target?: string | null;
  delivery_error?: string | null;
  repair_workflow_created?: boolean;
  repair_workflow_run_id?: string | null;
  repair_workflow_reason?: string | null;
}

export interface WorkflowDevelopmentProblemDefinitionOutput {
  task_name: string;
  summary: string;
  problem_background: string;
  goal: string;
  constraints: string[];
  success_criteria: string[];
}

export interface WorkflowDevelopmentRequirementsOutput {
  summary: string;
  functional_requirements: string[];
  non_functional_requirements: string[];
  risks: string[];
  dependencies: string[];
}

export interface WorkflowDevelopmentDesignOutput {
  summary: string;
  modules: string[];
  flows: string[];
  data_structures: string[];
  interfaces: string[];
}

export interface WorkflowDevelopmentTechnologyChoice {
  category: "frontend" | "backend" | "database" | "testing" | "deployment" | "tooling";
  choice: string;
  reason: string;
}

export interface WorkflowDevelopmentTechnologySelectionOutput {
  summary: string;
  selections: WorkflowDevelopmentTechnologyChoice[];
}

export interface WorkflowDevelopmentTaskItem {
  title: string;
  priority: "p0" | "p1" | "p2" | "p3";
  estimate: string;
  description: string;
}

export interface WorkflowDevelopmentTaskPlanningOutput {
  summary: string;
  tasks: WorkflowDevelopmentTaskItem[];
  schedule: string[];
}

export interface WorkflowDevelopmentImplementationOutput {
  summary: string;
  completed_items: string[];
  changed_modules: string[];
  notable_decisions: string[];
}

export interface WorkflowDevelopmentTestingOutput {
  summary: string;
  test_cases: string[];
  test_results: string[];
  validation_status: "passed" | "partial" | "failed";
  remaining_gaps: string[];
}

export interface WorkflowDevelopmentOptimizationOutput {
  summary: string;
  improvements: string[];
  follow_up_todos: string[];
  known_limits: string[];
}

export interface WorkflowDevelopmentExecutionReportPayload {
  task_name: string;
  problem_definition: string;
  requirements_analysis: string[];
  solution_design: string[];
  technology_selection: WorkflowDevelopmentTechnologyChoice[];
  task_breakdown_schedule: WorkflowDevelopmentTaskItem[];
  development_results: string[];
  test_results: string[];
  risks_and_todos: string[];
  final_summary: string;
  delivery_status: string;
  delivery_target?: string | null;
  delivery_error?: string | null;
  delivery_source: "development_config" | "runtime_route" | "none";
  delivery_reason?: string | null;
}

export interface WorkflowStageRun {
  id: string;
  stage_key: string;
  agent_id: string;
  status: string;
  progress_percent: number;
  input_payload: Record<string, unknown>;
  output_payload?: Record<string, unknown> | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEvent {
  id: string;
  run_id: string;
  stage_key?: string | null;
  agent_id?: string | null;
  status: string;
  progress_percent: number;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface WorkflowRunResponse {
  id: string;
  instance_id: string;
  workflow_type: WorkflowType;
  status: string;
  current_stage?: string | null;
  active_agent_id?: string | null;
  overall_progress_percent: number;
  input_payload: Record<string, unknown>;
  final_report?: WorkflowReportPayload | null;
  final_web_result?: WorkflowWebSearchResult | null;
  final_ingestion_run_id?: string | null;
  final_ingest_result?: WorkflowWebSearchIngestOutput | null;
  final_news_brief?: WorkflowNewsBriefPayload | null;
  final_system_inspection?: WorkflowSystemInspectionReportPayload | null;
  final_development_report?: WorkflowDevelopmentExecutionReportPayload | null;
  error_message?: string | null;
  stages: WorkflowStageRun[];
  events: WorkflowEvent[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowWebSearchCreateRequest {
  instance_id: string;
  topic: string;
  target_urls: string[];
  target_sites: string[];
  target_domains: string[];
  keywords: string[];
  must_include: string[];
  must_exclude: string[];
  focus_points: string[];
  output_format: WebSearchOutputFormat;
  include_project_sources: boolean;
  business_type?: BusinessType | null;
  auto_publish: boolean;
  source_merge_hint?: string;
  ingest_mode: "auto_store";
  source_id?: string;
  result_limit: number;
}

export interface WorkflowNewsBriefCreateRequest {
  instance_id: string;
}

export interface WorkflowSystemInspectionCreateRequest {
  instance_id: string;
}

export interface WorkflowDevelopmentExecutionCreateRequest {
  instance_id: string;
  task_name: string;
  problem_background: string;
  goal: string;
  trigger_source?: "manual" | "system_inspection_handoff";
  continued_from_run_id?: string | null;
  origin_workflow_type?: "system_inspection" | null;
  constraints: string[];
  success_criteria: string[];
  context: string;
  attachments: string[];
  references: string[];
}
