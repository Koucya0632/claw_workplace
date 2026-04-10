import type { NextRequest } from "next/server";

import type { ControlCenterProxyError } from "@/lib/control-center-types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PROXY_TIMEOUT_MS = 10_000;

function resolveControlCenterBaseUrl() {
  // 代理層優先使用顯式 base URL，否則回退到本機 engine port。
  const explicitBaseUrl = process.env.CONTROL_CENTER_ENGINE_BASE_URL?.trim();
  if (explicitBaseUrl) {
    return explicitBaseUrl.replace(/\/+$/, "");
  }

  const port = process.env.CONTROL_CENTER_ENGINE_PORT?.trim() || "4310";
  return `http://127.0.0.1:${port}`;
}

async function proxyControlCenterRequest(
  request: NextRequest,
  context: { params: { path?: string[] } }
) {
  const pathSegments = context.params.path ?? [];
  const targetPath = pathSegments.join("/");
  const incomingUrl = new URL(request.url);
  const targetUrl = `${resolveControlCenterBaseUrl()}/${targetPath}${incomingUrl.search}`;
  const normalizedPath = formatControlCenterPath(targetPath);

  // 只轉發 Control Center 真正需要的標頭，避免把 Next 內部標頭原樣外洩出去。
  const headers = new Headers();
  const allowedHeaders = [
    "accept",
    "content-type",
    "authorization",
    "x-local-token",
    "last-event-id"
  ];

  for (const headerName of allowedHeaders) {
    const value = request.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  }

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.text();

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      signal: shouldApplyProxyTimeout(request, normalizedPath) ? AbortSignal.timeout(PROXY_TIMEOUT_MS) : undefined,
      // 讓 route handler 能無緩存地轉發 SSE 與最新 JSON。
      cache: "no-store"
    });
  } catch (error) {
    return buildProxyErrorResponse(classifyProxyFailure(error, normalizedPath));
  }

  const responseHeaders = new Headers();
  upstreamResponse.headers.forEach((value, key) => {
    if (["connection", "content-length", "transfer-encoding", "keep-alive"].includes(key.toLowerCase())) {
      return;
    }
    responseHeaders.set(key, value);
  });

  if (shouldBufferJsonResponse(request, normalizedPath)) {
    const rawBody = await upstreamResponse.text();
    if (normalizedPath === "/healthz" && isValidJsonPayload(rawBody)) {
      return new Response(rawBody, {
        status: upstreamResponse.status,
        headers: responseHeaders
      });
    }

    if (upstreamResponse.ok) {
      if (!isValidJsonPayload(rawBody)) {
        return buildProxyErrorResponse({
          code: "UPSTREAM_INVALID_JSON",
          message: `${formatControlCenterLabel(normalizedPath)} returned invalid JSON.`,
          path: normalizedPath,
          status: 502,
          upstreamStatus: upstreamResponse.status,
          detail: truncateDetail(rawBody)
        });
      }

      return new Response(rawBody, {
        status: upstreamResponse.status,
        headers: responseHeaders
      });
    }

    return buildProxyErrorResponse(
      buildUpstreamError({
        path: normalizedPath,
        status: upstreamResponse.status,
        rawBody,
        contentType: upstreamResponse.headers.get("content-type")
      })
    );
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: responseHeaders
  });
}

export async function GET(request: NextRequest, context: { params: { path?: string[] } }) {
  return proxyControlCenterRequest(request, context);
}

export async function POST(request: NextRequest, context: { params: { path?: string[] } }) {
  return proxyControlCenterRequest(request, context);
}

export async function PUT(request: NextRequest, context: { params: { path?: string[] } }) {
  return proxyControlCenterRequest(request, context);
}

export async function PATCH(request: NextRequest, context: { params: { path?: string[] } }) {
  return proxyControlCenterRequest(request, context);
}

export async function DELETE(request: NextRequest, context: { params: { path?: string[] } }) {
  return proxyControlCenterRequest(request, context);
}

export async function HEAD(request: NextRequest, context: { params: { path?: string[] } }) {
  return proxyControlCenterRequest(request, context);
}

function buildProxyErrorResponse(error: ControlCenterProxyError): Response {
  return new Response(JSON.stringify(error), {
    status: error.status ?? 500,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}

function buildUpstreamError({
  path,
  status,
  rawBody,
  contentType
}: {
  path: string;
  status: number;
  rawBody: string;
  contentType: string | null;
}): ControlCenterProxyError {
  const upstreamPayload = parseStructuredPayload(rawBody, contentType);
  const detail = upstreamPayload.detail ?? truncateDetail(rawBody);
  const baseMessage = `${formatControlCenterLabel(path)} returned ${status}.`;

  return {
    code: status >= 500 ? "UPSTREAM_5XX" : "UPSTREAM_ERROR",
    message: upstreamPayload.message ? `${baseMessage} ${upstreamPayload.message}`.trim() : baseMessage,
    path,
    status,
    upstreamStatus: status,
    detail
  };
}

function classifyProxyFailure(error: unknown, path: string): ControlCenterProxyError {
  const code = readErrorCode(error);
  if (code === "ECONNREFUSED" || code === "ENOTFOUND" || code === "EHOSTUNREACH" || code === "ECONNRESET") {
    return {
      code: "ENGINE_UNAVAILABLE",
      message: "Control Center engine unavailable.",
      path,
      status: 503
    };
  }

  if (error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError")) {
    return {
      code: "ENGINE_TIMEOUT",
      message: `${formatControlCenterLabel(path)} timed out before the engine replied.`,
      path,
      status: 504
    };
  }

  return {
    code: "PROXY_FETCH_FAILED",
    message: `Control Center proxy could not reach ${formatControlCenterPath(path)}.`,
    path,
    status: 502,
    detail: error instanceof Error ? truncateDetail(error.message) : undefined
  };
}

function readErrorCode(error: unknown): string | undefined {
  if (error && typeof error === "object") {
    if ("code" in error && typeof error.code === "string") return error.code;
    if ("cause" in error && error.cause && typeof error.cause === "object" && "code" in error.cause && typeof error.cause.code === "string") {
      return error.cause.code;
    }
  }
  return undefined;
}

function shouldApplyProxyTimeout(request: NextRequest, path: string) {
  if (request.method === "HEAD") return false;
  if (path === "/api/hall/events") return false;
  return !request.headers.get("accept")?.includes("text/event-stream");
}

function shouldBufferJsonResponse(request: NextRequest, path: string) {
  if (request.method === "HEAD") return false;
  if (path === "/api/hall/events") return false;
  if (path === "/api/files/content") return false;
  if (path === "/api/diagnostics") {
    const format = new URL(request.url).searchParams.get("format");
    if (format === "text") return false;
  }
  return path === "/healthz" || path.startsWith("/api/");
}

function parseStructuredPayload(rawBody: string, contentType: string | null) {
  if (!rawBody.trim() || !contentType?.toLowerCase().includes("application/json")) {
    return { message: undefined, detail: truncateDetail(rawBody) };
  }

  try {
    const payload = JSON.parse(rawBody) as Record<string, unknown>;
    return {
      message: typeof payload.message === "string" ? payload.message : undefined,
      detail:
        typeof payload.detail === "string"
          ? truncateDetail(payload.detail)
          : truncateDetail(rawBody)
    };
  } catch {
    return { message: undefined, detail: truncateDetail(rawBody) };
  }
}

function isValidJsonPayload(rawBody: string) {
  if (!rawBody.trim()) return false;
  try {
    JSON.parse(rawBody);
    return true;
  } catch {
    return false;
  }
}

function truncateDetail(value: string, maxLength = 300) {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  return trimmed.length > maxLength ? `${trimmed.slice(0, maxLength)}...` : trimmed;
}

function formatControlCenterPath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

function formatControlCenterLabel(path: string) {
  switch (path) {
    case "/healthz":
      return "Healthz API";
    case "/api/hall":
      return "Hall API";
    case "/api/diagnostics":
      return "Diagnostics API";
    case "/api/usage-cost":
      return "Usage API";
    case "/api/sessions":
      return "Sessions API";
    case "/api/tasks":
      return "Tasks API";
    default:
      return `${formatControlCenterPath(path)} API`;
  }
}
