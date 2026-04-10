import type {
  ControlCenterCronOverviewResponse,
  ControlCenterDiagnosticsResponse,
  ControlCenterFilesResponse,
  ControlCenterHallResponse,
  ControlCenterHealthzPayload,
  ControlCenterProxyError,
  ControlCenterStaffSummaryResponse,
  ControlCenterSessionsResponse,
  ControlCenterTasksResponse,
  ControlCenterUsageResponse
} from "@/lib/control-center-types";

async function requestControlCenter<T>(
  path: string,
  init?: RequestInit,
  normalize?: (payload: unknown) => T,
  options?: {
    acceptedErrorStatuses?: number[];
  }
): Promise<T> {
  let response: Response;
  try {
    // 所有 Control Center 前端請求都先打同源代理，避免 browser 直接碰 engine port。
    response = await fetch(`/api/control-center${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        ...(init?.headers ?? {})
      }
    });
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : "Control Center proxy unavailable.");
  }

  const rawText = await response.text().catch(() => "");
  const payload = parseJsonText(rawText);

  if (!response.ok && !options?.acceptedErrorStatuses?.includes(response.status)) {
    throw buildControlCenterError(path, response.status, payload, rawText);
  }

  if (payload === undefined) {
    throw new Error(`Invalid JSON payload returned for ${formatControlCenterPath(path)}.`);
  }

  return normalize ? normalize(payload) : (payload as T);
}

export async function fetchControlCenterHealthz() {
  return requestControlCenter<ControlCenterHealthzPayload>(
    "/healthz",
    undefined,
    normalizeHealthzEnvelope,
    { acceptedErrorStatuses: [503] }
  );
}

export async function fetchControlCenterCronOverview() {
  return requestControlCenter<ControlCenterCronOverviewResponse>("/cron");
}

export async function fetchControlCenterUsage() {
  return requestControlCenter<ControlCenterUsageResponse>("/api/usage-cost");
}

export async function fetchControlCenterSessions() {
  return requestControlCenter<ControlCenterSessionsResponse>("/api/sessions", undefined, normalizeSessionsPayload);
}

export async function fetchControlCenterStaffSummary() {
  return requestControlCenter<ControlCenterStaffSummaryResponse>("/api/staff-summary");
}

export async function fetchControlCenterTasks() {
  return requestControlCenter<ControlCenterTasksResponse>("/api/tasks");
}

export async function fetchControlCenterHall() {
  return requestControlCenter<ControlCenterHallResponse>("/api/hall");
}

export async function fetchControlCenterFiles(scope: "memory" | "workspace") {
  return requestControlCenter<ControlCenterFilesResponse>(`/api/files?scope=${scope}`);
}

export async function fetchControlCenterDiagnostics() {
  return requestControlCenter<ControlCenterDiagnosticsResponse>("/api/diagnostics");
}

function normalizeHealthzEnvelope(payload: unknown): ControlCenterHealthzPayload {
  if (isProxyError(payload)) {
    throw new Error(payload.message);
  }
  if (!isRecord(payload) || !isRecord(payload.health) || !isHealthzPayload(payload.health)) {
    throw new Error("Invalid healthz payload returned by Control Center engine.");
  }

  return payload.health;
}

function normalizeSessionsPayload(payload: unknown): ControlCenterSessionsResponse {
  if (!isRecord(payload)) {
    throw new Error("Invalid sessions payload returned by Control Center engine.");
  }

  const sessions = Array.isArray(payload.sessions)
    ? payload.sessions
    : Array.isArray(payload.items)
      ? payload.items
      : [];
  const count =
    typeof payload.count === "number" && Number.isFinite(payload.count)
      ? payload.count
      : typeof payload.total === "number" && Number.isFinite(payload.total)
        ? payload.total
        : sessions.length;

  return {
    ok: true,
    count,
    sessions: sessions as ControlCenterSessionsResponse["sessions"],
  };
}

function buildControlCenterError(
  path: string,
  status: number,
  payload: unknown,
  rawText: string
): Error {
  if (isProxyError(payload)) {
    return new Error(payload.message);
  }

  const trimmed = rawText.trim();
  if (trimmed) {
    return new Error(trimmed);
  }

  if (status === 503) {
    return new Error("Control Center engine unavailable.");
  }
  if (status === 502) {
    return new Error(`Control Center proxy could not reach ${formatControlCenterPath(path)}.`);
  }

  return new Error(`${formatControlCenterPath(path)} request failed with status ${status}.`);
}

function parseJsonText(rawText: string): unknown {
  if (!rawText.trim()) return undefined;
  try {
    return JSON.parse(rawText) as unknown;
  } catch {
    return undefined;
  }
}

function formatControlCenterPath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isProxyError(value: unknown): value is ControlCenterProxyError {
  return isRecord(value) && typeof value.code === "string" && typeof value.message === "string";
}

function isHealthzPayload(value: unknown): value is ControlCenterHealthzPayload {
  return (
    isRecord(value) &&
    typeof value.generatedAt === "string" &&
    (value.status === "ok" || value.status === "warn" || value.status === "stale") &&
    isRecord(value.build) &&
    isRecord(value.snapshot) &&
    isRecord(value.monitor)
  );
}
