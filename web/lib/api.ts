import type {
  DocumentSummary,
  OpenClawAgentSummary,
  OpenClawAgentCapabilityRecord,
  OpenClawApiResponse,
  OpenClawConfigResponse,
  OpenClawConfigValidationResponse,
  OpenClawDeviceSummary,
  OpenClawHealthResponse,
  OpenClawInstanceResponse,
  OpenClawLogEntry,
  OpenClawOperationLogRecord,
  OpenClawWorkflowConfigResponse,
  MarkdownReportResponse,
  ScanSourceResponse,
  SearchRequest,
  SearchResponse,
  SourceResponse,
  TaskStatusResponse,
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

export async function fetchSources() {
  return request<SourceResponse[]>("/sources");
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

export async function scanSource(sourceId: string) {
  return request<ScanSourceResponse>(`/sources/${sourceId}/scan`, {
    method: "POST"
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
  search_agent_id: string;
  analysis_agent_id: string;
  report_agent_id: string;
}) {
  return requestOpenClaw<OpenClawWorkflowConfigResponse>("/openclaw/workflow-config", {
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

export async function fetchWorkflowRuns(params?: { instanceId?: string; limit?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.instanceId) {
    searchParams.set("instanceId", params.instanceId);
  }
  if (params?.limit) {
    searchParams.set("limit", String(params.limit));
  }

  const suffix = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  return request<WorkflowRunResponse[]>(`/workflows${suffix}`);
}
