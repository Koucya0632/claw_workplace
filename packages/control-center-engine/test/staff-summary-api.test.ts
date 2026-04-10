import assert from "node:assert/strict";
import test from "node:test";
import { ReadonlyToolClient } from "../src/clients/tool-client";
import { buildApiDocs } from "../src/runtime/api-docs";
import { buildStaffSummaryResponse, startUiServer } from "../src/ui/server";

test("buildStaffSummaryResponse keeps empty staff summaries readable", () => {
  const payload = buildStaffSummaryResponse({
    generatedAt: "2026-04-06T00:00:00.000Z",
    cards: [],
    sessions: [],
  });

  assert.equal(payload.ok, true);
  assert.equal(payload.generatedAt, "2026-04-06T00:00:00.000Z");
  assert.deepEqual(payload.groups, []);
  assert.equal(payload.sessionsDetail.count, 0);
  assert.deepEqual(payload.sessionsDetail.sessions, []);
});

test("buildStaffSummaryResponse groups members by role and preserves raw sessions", () => {
  const payload = buildStaffSummaryResponse({
    generatedAt: "2026-04-06T00:00:00.000Z",
    cards: [
      {
        agentId: "main",
        displayName: "Chief Lobster",
        identity: { animal: "lobster", title: "Lobster", accent: "#f97316", sprite: "lobster" },
        roleKey: "manager",
        roleLabel: "主控與協調",
        statusLabel: "Running",
        currentWorkLabel: "Current focus",
        currentWork: "Coordinating the queue",
        recentOutput: "Published a handoff",
        scheduledLabel: "Scheduled",
      },
      {
        agentId: "support-agent",
        displayName: "Support Otter",
        identity: { animal: "otter", title: "Otter", accent: "#14b8a6", sprite: "otter" },
        roleKey: "unassigned",
        roleLabel: "工作區未寫明職責",
        statusLabel: "Idle",
        currentWorkLabel: "Current focus",
        currentWork: "Standing by",
        recentOutput: "No recent output yet.",
        scheduledLabel: "Not scheduled",
      },
    ],
    sessions: [
      {
        sessionKey: "agent:main:main",
        label: "Main session",
        agentId: "main",
        state: "running",
        latestSnippet: "Reviewing the role view",
        lastMessageAt: "2026-04-06T00:05:00.000Z",
        latestHistoryAt: "2026-04-06T00:06:00.000Z",
        historyCount: 3,
        toolEventCount: 0,
        interSessionSignals: [],
      },
    ],
  });

  assert.equal(payload.groups.length, 2);
  assert.equal(payload.groups[0]?.roleKey, "manager");
  assert.equal(payload.groups[1]?.roleKey, "unassigned");
  assert.equal(payload.groups[1]?.members[0]?.roleLabel, "工作區未寫明職責");
  assert.equal(payload.sessionsDetail.count, 1);
  assert.equal(payload.sessionsDetail.sessions[0]?.updatedAt, "2026-04-06T00:06:00.000Z");
});

test("staff summary API route and docs are exposed", async () => {
  const docs = buildApiDocs();
  assert(docs.routes.some((route) => route.path === "/api/staff-summary"));
  assert(docs.routes.some((route) => route.path === "/api/budget/template"));

  const server = startUiServer(0, new ReadonlyToolClient());
  try {
    if (!server.listening) {
      await new Promise<void>((resolve, reject) => {
        server.once("listening", resolve);
        server.once("error", reject);
      });
    }
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("Failed to bind ephemeral UI port.");
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/api/staff-summary`);
    assert.equal(response.status, 200);
    const payload = await response.json() as {
      ok: boolean;
      generatedAt: string;
      groups: Array<{ roleKey: string; members: unknown[] }>;
      sessionsDetail: { count: number; sessions: unknown[] };
    };

    assert.equal(payload.ok, true);
    assert.equal(typeof payload.generatedAt, "string");
    assert(Array.isArray(payload.groups));
    assert.equal(typeof payload.sessionsDetail.count, "number");
    assert(Array.isArray(payload.sessionsDetail.sessions));

    const budgetTemplateResponse = await fetch(`${baseUrl}/api/budget/template`);
    assert.equal(budgetTemplateResponse.status, 200);
    const budgetTemplatePayload = await budgetTemplateResponse.json() as {
      ok: boolean;
      template: { monthlyCostLimitUsd: number };
      hint: string;
    };
    assert.equal(budgetTemplatePayload.ok, true);
    assert.equal(typeof budgetTemplatePayload.template.monthlyCostLimitUsd, "number");
    assert(budgetTemplatePayload.hint.includes("usage-budget.json"));
  } finally {
    if (server.listening) {
      await new Promise<void>((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
    }
  }
});
