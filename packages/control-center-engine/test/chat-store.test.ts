import assert from "node:assert/strict";
import { readFile, rm, writeFile } from "node:fs/promises";
import test from "node:test";
import { appendChatMessage, CHAT_MESSAGES_PATH, CHAT_ROOMS_PATH, createChatRoom, loadChatMessageStore, loadChatRoomStore } from "../src/runtime/chat-store";
import { CHAT_SUMMARIES_PATH, buildChatRoomSummary, upsertChatRoomSummary } from "../src/runtime/chat-summary-store";

test("chat store persists rooms, messages, and summaries across reloads", async () => {
  const roomsBefore = await readOptionalFile(CHAT_ROOMS_PATH);
  const messagesBefore = await readOptionalFile(CHAT_MESSAGES_PATH);
  const summariesBefore = await readOptionalFile(CHAT_SUMMARIES_PATH);

  try {
    const created = await createChatRoom({
      projectId: "chat-project",
      taskId: "chat-task",
      title: "Chat room persistence",
    });
    const posted = await appendChatMessage({
      roomId: created.room.roomId,
      authorRole: "human",
      content: "Please keep this room state on disk.",
    });
    const summaryResult = await upsertChatRoomSummary(created.room, [posted.message]);

    const roomStore = await loadChatRoomStore();
    const messageStore = await loadChatMessageStore();
    const room = roomStore.rooms.find((item) => item.roomId === created.room.roomId);
    assert(room);
    assert.equal(room.title, "Chat room persistence");
    assert.equal(messageStore.messages.filter((item) => item.roomId === created.room.roomId).length, 1);

    const storedSummaryRaw = await readFile(CHAT_SUMMARIES_PATH, "utf8");
    const storedSummary = JSON.parse(storedSummaryRaw) as { summaries?: Array<{ roomId?: string }> };
    assert((storedSummary.summaries ?? []).some((item) => item.roomId === created.room.roomId));
    assert.equal(summaryResult.summary.messageCount, 1);
    assert.equal(buildChatRoomSummary(created.room, [posted.message]).roomId, created.room.roomId);
  } finally {
    await restoreOptionalFile(CHAT_ROOMS_PATH, roomsBefore);
    await restoreOptionalFile(CHAT_MESSAGES_PATH, messagesBefore);
    await restoreOptionalFile(CHAT_SUMMARIES_PATH, summariesBefore);
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
