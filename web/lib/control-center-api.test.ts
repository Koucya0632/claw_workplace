import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchControlCenterHall,
  fetchControlCenterHealthz,
  fetchControlCenterSessions,
  fetchControlCenterStaffSummary,
} from "@/lib/control-center-api";

function buildHealthzFixture() {
  return {
    generatedAt: new Date().toISOString(),
    status: "ok" as const,
    build: {
      name: "control-center",
      version: "1.0.0",
      node: "v20.0.0",
      readonlyMode: true,
      approvalActionsEnabled: false,
      approvalActionsDryRun: true,
      distIndexPath: "/tmp/dist/index.js",
    },
    snapshot: {
      generatedAt: new Date().toISOString(),
      ageMs: 0,
      status: "ok" as const,
    },
    monitor: {
      status: "ok" as const,
    },
  };
}

describe("control-center-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("unwraps the healthz envelope returned by the engine", async () => {
    const health = buildHealthzFixture();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: true, health }), {
          status: 200,
          headers: {
            "content-type": "application/json; charset=utf-8",
          },
        }),
      ),
    );

    await expect(fetchControlCenterHealthz()).resolves.toEqual(health);
  });

  it("accepts a stale healthz envelope even when the endpoint responds 503", async () => {
    const health = {
      ...buildHealthzFixture(),
      status: "stale" as const,
      snapshot: {
        ...buildHealthzFixture().snapshot,
        status: "warn" as const,
      },
      monitor: {
        status: "stale" as const,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: false, health }), {
          status: 503,
          headers: {
            "content-type": "application/json; charset=utf-8",
          },
        }),
      ),
    );

    await expect(fetchControlCenterHealthz()).resolves.toEqual(health);
  });

  it("surfaces structured proxy errors instead of generic 500 text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "ENGINE_UNAVAILABLE",
            message: "Control Center engine unavailable.",
            path: "/healthz",
            status: 503,
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

    await expect(fetchControlCenterHealthz()).rejects.toThrow("Control Center engine unavailable.");
  });

  it("reports upstream path-specific 5xx messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "UPSTREAM_5XX",
            message: "Hall API returned 500. Internal server error.",
            path: "/api/hall",
            status: 500,
            upstreamStatus: 500,
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

    await expect(fetchControlCenterHall()).rejects.toThrow("Hall API returned 500. Internal server error.");
  });

  it("rejects invalid healthz shapes with a diagnostic message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: true, health: { status: "ok" } }), {
          status: 200,
          headers: {
            "content-type": "application/json; charset=utf-8",
          },
        }),
      ),
    );

    await expect(fetchControlCenterHealthz()).rejects.toThrow(
      "Invalid healthz payload returned by Control Center engine.",
    );
  });

  it("normalizes sessions payloads returned as total/items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            ok: true,
            total: 2,
            items: [
              {
                sessionKey: "agent:main:main",
                agentId: "main",
                state: "idle",
              },
              {
                sessionKey: "agent:support:main",
                agentId: "support",
                state: "running",
              },
            ],
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        ),
      ),
    );

    await expect(fetchControlCenterSessions()).resolves.toEqual({
      ok: true,
      count: 2,
      sessions: [
        {
          sessionKey: "agent:main:main",
          agentId: "main",
          state: "idle",
        },
        {
          sessionKey: "agent:support:main",
          agentId: "support",
          state: "running",
        },
      ],
    });
  });

  it("reads staff summary payloads from the dedicated endpoint", async () => {
    const payload = {
      ok: true,
      generatedAt: new Date().toISOString(),
      groups: [],
      sessionsDetail: {
        count: 0,
        sessions: [],
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: {
            "content-type": "application/json; charset=utf-8",
          },
        }),
      ),
    );

    await expect(fetchControlCenterStaffSummary()).resolves.toEqual(payload);
  });
});
