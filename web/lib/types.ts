export type SourceType = "local" | "google_drive" | "notion";

export interface SourceConfig {
  path?: string | null;
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
  config: SourceConfig;
  last_scan_at?: string | null;
  created_at: string;
  updated_at: string;
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
  search_agent_id: string;
  analysis_agent_id: string;
  report_agent_id: string;
  created_at: string;
  updated_at: string;
}

export type WorkflowType = "search_report" | "web_search";
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
  structured_output: string;
  markdown: string;
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
  source_id?: string;
  result_limit: number;
}
