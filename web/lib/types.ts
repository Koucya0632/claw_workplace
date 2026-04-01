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

