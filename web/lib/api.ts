import type {
  DocumentSummary,
  MarkdownReportResponse,
  ScanSourceResponse,
  SearchRequest,
  SearchResponse,
  SourceResponse,
  TaskStatusResponse
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
