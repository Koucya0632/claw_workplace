import assert from "node:assert/strict";
import { readFile, rm, writeFile } from "node:fs/promises";
import test from "node:test";
import {
  TASK_ROOM_BRIDGE_EVENTS_PATH,
  buildTelegramBotApiUrl,
  buildTelegramBotPayload,
  buildDiscordWebhookPayload,
  buildTaskRoomBridgeEvent,
  listTaskRoomBridgeEvents,
  loadTaskRoomBridgeStore,
  publishTaskRoomBridgeEvent,
} from "../src/runtime/task-room-bridge";
import type { ChatMessage, ChatRoom, ProjectTask } from "../src/types";

test("task room bridge stores events locally and formats Discord payloads with deep links", async () => {
  const before = await readOptionalFile(TASK_ROOM_BRIDGE_EVENTS_PATH);
  const room: ChatRoom = {
    roomId: "bridge-room",
    projectId: "bridge-project",
    taskId: "bridge-task",
    title: "Bridge Room",
    stage: "executing",
    ownerRole: "coder",
    assignedExecutor: "coder",
    participants: [],
    handoffs: [],
    sessionKeys: [],
    decision: "Ship the room flow.",
    createdAt: "2026-03-19T12:00:00.000Z",
    updatedAt: "2026-03-19T12:00:00.000Z",
  };
  const task: ProjectTask = {
    projectId: "bridge-project",
    taskId: "bridge-task",
    title: "Bridge task",
    status: "in_progress",
    owner: "coder",
    roomId: "bridge-room",
    definitionOfDone: [],
    artifacts: [],
    rollback: { strategy: "manual", steps: [] },
    sessionKeys: [],
    budget: {},
    updatedAt: "2026-03-19T12:00:00.000Z",
  };
  const message: ChatMessage = {
    roomId: "bridge-room",
    messageId: "bridge-message",
    kind: "status",
    authorRole: "coder",
    authorLabel: "Coder",
    content: "Execution started and the timeline is syncing.",
    mentions: [],
    createdAt: "2026-03-19T12:01:00.000Z",
  };

  try {
    let calls = 0;
    const result = await publishTaskRoomBridgeEvent(
      {
        type: "message_posted",
        room,
        task,
        message,
        requestId: "bridge-request",
      },
      {
        enabled: true,
        discordWebhookUrl: "https://example.com/webhook",
        fetchImpl: async (input, init) => {
          calls += 1;
          assert.equal(String(input), "https://example.com/webhook");
          const payload = JSON.parse(String(init?.body ?? "{}")) as { content?: string };
          assert(payload.content?.includes("Task room update: message posted"));
          return new Response(null, { status: 204 });
        },
      },
    );

    assert.equal(calls, 1);
    assert.equal(result.event.status, "delivered");
    assert.deepEqual(result.event.deliveredTargets, ["discord"]);
    assert(result.event.skippedTargets.includes("telegram-not-configured"));

    const store = await loadTaskRoomBridgeStore();
    const events = listTaskRoomBridgeEvents(store, { roomId: room.roomId });
    assert.equal(events.length, 1);
    assert.equal(events[0]?.roomId, room.roomId);

    const payload = buildDiscordWebhookPayload(
      buildTaskRoomBridgeEvent({
        type: "executor_assigned",
        room,
        task,
        message,
      }),
    );
    assert(payload.content.includes("Bridge Room"));
    assert(payload.content.includes("bridge-project:bridge-task"));
  } finally {
    await restoreOptionalFile(TASK_ROOM_BRIDGE_EVENTS_PATH, before);
  }
});

test("task room bridge can mirror one event to Telegram bot api", async () => {
  const before = await readOptionalFile(TASK_ROOM_BRIDGE_EVENTS_PATH);
  const room: ChatRoom = {
    roomId: "bridge-room",
    projectId: "bridge-project",
    taskId: "bridge-task",
    title: "Bridge Room",
    stage: "executing",
    ownerRole: "coder",
    assignedExecutor: "coder",
    participants: [],
    handoffs: [],
    sessionKeys: [],
    decision: "Ship the room flow.",
    createdAt: "2026-03-19T12:00:00.000Z",
    updatedAt: "2026-03-19T12:00:00.000Z",
  };
  const task: ProjectTask = {
    projectId: "bridge-project",
    taskId: "bridge-task",
    title: "Bridge task",
    status: "in_progress",
    owner: "coder",
    roomId: "bridge-room",
    definitionOfDone: [],
    artifacts: [],
    rollback: { strategy: "manual", steps: [] },
    sessionKeys: [],
    budget: {},
    updatedAt: "2026-03-19T12:00:00.000Z",
  };

  try {
    let calls = 0;
    const result = await publishTaskRoomBridgeEvent(
      {
        type: "executor_assigned",
        room,
        task,
      },
      {
        enabled: true,
        telegramBotToken: "test-bot-token",
        telegramChatId: "-100123456",
        fetchImpl: async (input, init) => {
          calls += 1;
          assert.equal(String(input), buildTelegramBotApiUrl("test-bot-token"));
          const payload = JSON.parse(String(init?.body ?? "{}")) as { chat_id?: string; text?: string };
          assert.equal(payload.chat_id, "-100123456");
          assert(payload.text?.includes("Task room update: executor assigned"));
          return new Response(JSON.stringify({ ok: true }), { status: 200 });
        },
      },
    );

    assert.equal(calls, 1);
    assert.equal(result.event.status, "delivered");
    assert.deepEqual(result.event.deliveredTargets, ["telegram"]);
    assert(result.event.skippedTargets.includes("discord-not-configured"));

    const payload = buildTelegramBotPayload(
      buildTaskRoomBridgeEvent({
        type: "review_submitted",
        room,
        task,
        note: "Ready for a human check.",
      }),
      "-100123456",
    );
    assert.equal(payload.chat_id, "-100123456");
    assert(payload.text.includes("Bridge Room"));
    assert(payload.text.includes("Ready for a human check."));
  } finally {
    await restoreOptionalFile(TASK_ROOM_BRIDGE_EVENTS_PATH, before);
  }
});

async function readOptionalFile(path: string): Promise<string | undefined> {
  try {
    return await readFile(path, "utf8");
  } catch {
    return undefined;
  }
}

async function restoreOptionalFile(path: string, content: string | undefined): Promise<void> {
  if (content === undefined) {
    await rm(path, { force: true });
    return;
  }
  await writeFile(path, content, "utf8");
}
