import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "@/app/api/control-center/[...path]/route";

describe("control-center proxy route", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("maps engine connection failures to a structured 503", async () => {
    vi.stubEnv("CONTROL_CENTER_ENGINE_BASE_URL", "http://127.0.0.1:4310");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(
        Object.assign(new TypeError("fetch failed"), {
          cause: { code: "ECONNREFUSED" },
        }),
      ),
    );

    const response = await GET(new Request("http://localhost/api/control-center/healthz") as never, {
      params: { path: ["healthz"] },
    });
    const payload = (await response.json()) as {
      code: string;
      message: string;
      path: string;
    };

    expect(response.status).toBe(503);
    expect(payload.code).toBe("ENGINE_UNAVAILABLE");
    expect(payload.message).toBe("Control Center engine unavailable.");
    expect(payload.path).toBe("/healthz");
  });

  it("wraps upstream 500 responses with path-specific metadata", async () => {
    vi.stubEnv("CONTROL_CENTER_ENGINE_BASE_URL", "http://127.0.0.1:4310");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "INTERNAL_ERROR",
            message: "Internal server error.",
          }),
          {
            status: 500,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        ),
      ),
    );

    const response = await GET(new Request("http://localhost/api/control-center/api/hall") as never, {
      params: { path: ["api", "hall"] },
    });
    const payload = (await response.json()) as {
      code: string;
      message: string;
      path: string;
      upstreamStatus: number;
    };

    expect(response.status).toBe(500);
    expect(payload.code).toBe("UPSTREAM_5XX");
    expect(payload.message).toBe("Hall API returned 500. Internal server error.");
    expect(payload.path).toBe("/api/hall");
    expect(payload.upstreamStatus).toBe(500);
  });

  it("passes through healthz JSON payloads even when the engine reports 503 stale health", async () => {
    vi.stubEnv("CONTROL_CENTER_ENGINE_BASE_URL", "http://127.0.0.1:4310");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            ok: false,
            health: {
              generatedAt: "2026-04-06T10:00:00.000Z",
              status: "stale",
              build: {
                name: "openclaw-control-center",
                version: "1.0.0",
                node: "v25.8.1",
                readonlyMode: true,
                approvalActionsEnabled: false,
                approvalActionsDryRun: true,
                distIndexPath: "/tmp/dist/index.js",
              },
              snapshot: {
                generatedAt: "2026-04-06T09:55:00.000Z",
                ageMs: 300000,
                status: "warn",
              },
              monitor: {
                status: "stale",
              },
            },
          }),
          {
            status: 503,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        ),
      ),
    );

    const response = await GET(new Request("http://localhost/api/control-center/healthz") as never, {
      params: { path: ["healthz"] },
    });
    const payload = (await response.json()) as {
      ok: boolean;
      health: { status: string };
    };

    expect(response.status).toBe(503);
    expect(payload.ok).toBe(false);
    expect(payload.health.status).toBe("stale");
  });
});
