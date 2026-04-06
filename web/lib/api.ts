import type {
  DocumentSummary,
  DocumentVersionSummary,
  KnowledgeIngestRequest,
  KnowledgeIngestionRunResponse,
  OpenClawAgentSummary,
  OpenClawAgentCapabilityRecord,
  OpenClawApiResponse,
  OpenClawConfigResponse,
  OpenClawConfigValidationResponse,
  OpenClawDailyNewsConfigResponse,
  OpenClawDeviceSummary,
  OpenClawHealthResponse,
  OpenClawInstanceResponse,
  OpenClawLogEntry,
  OpenClawOperationLogRecord,
  OpenClawSystemInspectionConfigResponse,
  OpenClawWorkflowHandoffPolicy,
  OpenClawWorkflowRoutingRule,
  OpenClawWorkflowSpecialistAgents,
  OpenClawWorkflowConfigResponse,
  MarkdownReportResponse,
  ScanSourceResponse,
  SearchRequest,
  SearchResponse,
  SourceDetailResponse,
  SourceMetricsResponse,
  SourceResponse,
  SourceSyncEventResponse,
  SourceUpdateRequest,
  TaskStatusResponse,
  WebSearchOutputFormat,
  WorkflowNewsBriefCreateRequest,
  WorkflowSystemInspectionCreateRequest,
  WorkflowType,
  WorkflowWebSearchCreateRequest,
  WorkflowRunResponse
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // 所有 API 呼叫都走這裡，統一處理錯誤訊息與 no-store 行為。
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(errorPayload?.detail ?? `API request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function requestOpenClaw<T>(path: string, init?: RequestInit): Promise<T> {
  // OpenClaw 管理 API 使用 envelope，因此這裡先統一解包再把錯誤丟出去。
  const payload = await request<OpenClawApiResponse<T>>(path, init);

  if (!payload.success) {
    throw new Error(payload.error?.detail ?? payload.error?.message ?? "OpenClaw API request failed");
  }

  return payload.data;
}

export async function fetchSources(params?: {
  q?: string;
  status?: string;
  type?: string;
  sort?: "updated_at" | "last_sync" | "name" | "document_count" | "status";
  order?: "asc" | "desc";
}) {
  const searchParams = new URLSearchParams();
  if (params?.q) {
    searchParams.set("q", params.q);
  }
  if (params?.status) {
    searchParams.set("status", params.status);
  }
  if (params?.type) {
    searchParams.set("type", params.type);
  }
  if (params?.sort) {
    searchParams.set("sort", params.sort);
  }
  if (params?.order) {
    searchParams.set("order", params.order);
  }
  const suffix = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  return request<SourceResponse[]>(`/sources${suffix}`);
}

export async function fetchSourceMetrics() {
  return request<SourceMetricsResponse>("/sources/summary");
}

export async function fetchSourceDetail(sourceId: string) {
  return request<SourceDetailResponse>(`/sources/${sourceId}`);
}

export async function fetchSourceActivity(sourceId: string) {
  return request<SourceSyncEventResponse[]>(`/sources/${sourceId}/activity`);
}

export async function createLocalSource(name: string, path: string) {
  return request<SourceResponse>("/sources/local", {
    method: "POST",
    body: JSON.stringify({
      name,
      type: "local",
      config: {
        path
      }
    })
  });
}

export async function createSource(payload: {
  name: string;
  type: "local" | "google_drive" | "notion" | "web_page" | "rss_feed" | "url_list";
  config: {
    path?: string | null;
    url?: string | null;
    urls?: string[];
    root_page_id?: string | null;
    database_id?: string | null;
    workspace_name?: string | null;
    extra?: Record<string, unknown>;
  };
  role_hint?: string;
}) {
  return request<SourceResponse>("/sources", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function scanSource(sourceId: string) {
  return request<ScanSourceResponse>(`/sources/${sourceId}/scan`, {
    method: "POST"
  });
}

export async function updateSource(sourceId: string, payload: SourceUpdateRequest) {
  return request<SourceResponse>(`/sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function enableSource(sourceId: string) {
  return request<SourceResponse>(`/sources/${sourceId}/enable`, {
    method: "POST"
  });
}

export async function disableSource(sourceId: string) {
  return request<SourceResponse>(`/sources/${sourceId}/disable`, {
    method: "POST"
  });
}

export async function deleteSource(sourceId: string) {
  return request<void>(`/sources/${sourceId}`, {
    method: "DELETE"
  });
}

export async function searchDocuments(payload: SearchRequest) {
  return request<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchDocument(documentId: string) {
  return request<DocumentSummary>(`/documents/${documentId}`);
}

export async function fetchKnowledgeIngestionRuns(params?: { sourceId?: string; limit?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.sourceId) {
    searchParams.set("source_id", params.sourceId);
  }
  if (params?.limit) {
    searchParams.set("limit", String(params.limit));
  }
  const suffix = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  return request<KnowledgeIngestionRunResponse[]>(`/knowledge/ingestion-runs${suffix}`);
}

export async function ingestKnowledge(payload: KnowledgeIngestRequest) {
  return request<KnowledgeIngestionRunResponse>("/knowledge/ingest", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchDocumentVersions(documentId: string) {
  return request<DocumentVersionSummary[]>(`/knowledge/documents/${documentId}/versions`);
}

export async function createSummaryTask(documentId: string) {
  return request<TaskStatusResponse>("/tasks/summary", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId })
  });
}

export async function fetchTask(taskId: string) {
  return request<TaskStatusResponse>(`/tasks/${taskId}`);
}

export async function exportMarkdownReport(taskId: string) {
  return request<MarkdownReportResponse>("/reports/markdown", {
    method: "POST",
    body: JSON.stringify({ task_id: taskId })
  });
}

export async function fetchOpenClawInstances() {
  return requestOpenClaw<OpenClawInstanceResponse[]>("/openclaw/instances");
}

export async function createOpenClawInstance(payload: {
  name: string;
  gateway_url: string;
  token?: string;
  is_active?: boolean;
}) {
  return requestOpenClaw<OpenClawInstanceResponse>("/openclaw/instances", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateOpenClawInstance(
  instanceId: string,
  payload: {
    name?: string;
    gateway_url?: string;
    token?: string;
    clear_token?: boolean;
    is_active?: boolean;
  }
) {
  return requestOpenClaw<OpenClawInstanceResponse>(`/openclaw/instances/${instanceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function fetchOpenClawHealth(instanceId: string) {
  return requestOpenClaw<OpenClawHealthResponse>(`/openclaw/instances/${instanceId}/health`);
}

export async function fetchOpenClawOperations(limit = 20, instanceId?: string) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (instanceId) {
    params.set("instanceId", instanceId);
  }

  return requestOpenClaw<OpenClawOperationLogRecord[]>(`/openclaw/operations?${params.toString()}`);
}

export async function fetchOpenClawAgents(instanceId: string) {
  const params = new URLSearchParams({ instanceId });
  return requestOpenClaw<OpenClawAgentSummary[]>(`/openclaw/agents?${params.toString()}`);
}

export async function createOpenClawAgent(payload: {
  instance_id: string;
  name: string;
  prompt?: string;
  role_hint?: string;
  metadata?: Record<string, unknown>;
}) {
  return requestOpenClaw<OpenClawAgentSummary>("/openclaw/agents", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchOpenClawAgentCapabilities(instanceId: string, agentId: string) {
  const params = new URLSearchParams({ instanceId });
  return requestOpenClaw<OpenClawAgentCapabilityRecord[]>(`/openclaw/agents/${agentId}/capabilities?${params.toString()}`);
}

export async function updateOpenClawAgentSearchCapability(payload: {
  instance_id: string;
  agent_id: string;
  enabled: boolean;
  config?: Record<string, unknown>;
}) {
  return requestOpenClaw<OpenClawAgentCapabilityRecord>(`/openclaw/agents/${payload.agent_id}/capabilities/search`, {
    method: "POST",
    body: JSON.stringify({
      instance_id: payload.instance_id,
      enabled: payload.enabled,
      config: payload.config ?? {}
    })
  });
}

export async function fetchOpenClawDevices(instanceId: string) {
  const params = new URLSearchParams({ instanceId });
  return requestOpenClaw<OpenClawDeviceSummary[]>(`/openclaw/devices?${params.toString()}`);
}

export async function runOpenClawDeviceAction(
  action: "approve" | "reject" | "revoke",
  deviceId: string,
  instanceId: string
) {
  return requestOpenClaw<Record<string, unknown>>(`/openclaw/devices/${deviceId}/${action}`, {
    method: "POST",
    body: JSON.stringify({ instance_id: instanceId })
  });
}

export async function fetchOpenClawConfig(instanceId: string, path: string) {
  const params = new URLSearchParams({ instanceId, path });
  return requestOpenClaw<OpenClawConfigResponse>(`/openclaw/config?${params.toString()}`);
}

export async function setOpenClawConfig(payload: {
  instance_id: string;
  path: string;
  value: unknown;
}) {
  return requestOpenClaw<OpenClawConfigResponse>("/openclaw/config/set", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function validateOpenClawConfig(payload: {
  instance_id: string;
  path: string;
  value: unknown;
}) {
  return requestOpenClaw<OpenClawConfigValidationResponse>("/openclaw/config/validate", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchOpenClawLogs(instanceId: string, limit = 200) {
  const params = new URLSearchParams({ instanceId, limit: String(limit) });
  return requestOpenClaw<OpenClawLogEntry[]>(`/openclaw/logs?${params.toString()}`);
}

export async function dispatchOpenClawAgentHook(payload: {
  instance_id: string;
  agent_id: string;
  session_key: string;
  message: string;
  deliver?: boolean;
  channel?: string;
  to?: string;
  metadata?: Record<string, unknown>;
}) {
  return requestOpenClaw<Record<string, unknown>>("/openclaw/hooks/agent", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function dispatchOpenClawWakeHook(payload: {
  instance_id: string;
  agent_id: string;
  session_key: string;
  deliver?: boolean;
  channel?: string;
  to?: string;
  metadata?: Record<string, unknown>;
}) {
  return requestOpenClaw<Record<string, unknown>>("/openclaw/hooks/wake", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchOpenClawWorkflowConfig(instanceId: string) {
  const params = new URLSearchParams({ instanceId });
  return requestOpenClaw<OpenClawWorkflowConfigResponse>(`/openclaw/workflow-config?${params.toString()}`);
}

export async function updateOpenClawWorkflowConfig(payload: {
  instance_id: string;
  controller_agent_id: string;
  search_agent_id: string;
  analysis_agent_id: string;
  report_agent_id: string;
  specialist_agents: OpenClawWorkflowSpecialistAgents;
  routing_rules: OpenClawWorkflowRoutingRule[];
  handoff_policy: OpenClawWorkflowHandoffPolicy;
}) {
  return requestOpenClaw<OpenClawWorkflowConfigResponse>("/openclaw/workflow-config", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchOpenClawDailyNewsConfig(instanceId: string) {
  const params = new URLSearchParams({ instanceId });
  return requestOpenClaw<OpenClawDailyNewsConfigResponse>(`/openclaw/daily-news-config?${params.toString()}`);
}

export async function updateOpenClawDailyNewsConfig(payload: OpenClawDailyNewsConfigResponse | {
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
}) {
  return requestOpenClaw<OpenClawDailyNewsConfigResponse>("/openclaw/daily-news-config", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchOpenClawSystemInspectionConfig(instanceId: string) {
  const params = new URLSearchParams({ instanceId });
  return requestOpenClaw<OpenClawSystemInspectionConfigResponse>(`/openclaw/system-inspection-config?${params.toString()}`);
}

export async function updateOpenClawSystemInspectionConfig(payload: OpenClawSystemInspectionConfigResponse | {
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
}) {
  return requestOpenClaw<OpenClawSystemInspectionConfigResponse>("/openclaw/system-inspection-config", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function createSearchReportWorkflow(payload: {
  instance_id: string;
  query: string;
  source_id?: string;
}) {
  return request<WorkflowRunResponse>("/workflows/search-report", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchWorkflowRun(runId: string) {
  return request<WorkflowRunResponse>(`/workflows/${runId}`);
}

export async function fetchWorkflowRuns(params?: { instanceId?: string; workflowType?: WorkflowType; limit?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.instanceId) {
    searchParams.set("instanceId", params.instanceId);
  }
  if (params?.workflowType) {
    searchParams.set("workflowType", params.workflowType);
  }
  if (params?.limit) {
    searchParams.set("limit", String(params.limit));
  }

  const suffix = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  return request<WorkflowRunResponse[]>(`/workflows${suffix}`);
}

export async function createWebSearchWorkflow(payload: WorkflowWebSearchCreateRequest) {
  return request<WorkflowRunResponse>("/workflows/web-search", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function continueWorkflowToReport(runId: string) {
  return request<WorkflowRunResponse>(`/workflows/${runId}/continue-to-report`, {
    method: "POST"
  });
}

export async function createNewsBriefWorkflow(payload: WorkflowNewsBriefCreateRequest) {
  return request<WorkflowRunResponse>("/workflows/news-brief", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function createSystemInspectionWorkflow(payload: WorkflowSystemInspectionCreateRequest) {
  return request<WorkflowRunResponse>("/workflows/system-inspection", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
