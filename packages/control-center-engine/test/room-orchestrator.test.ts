import assert from "node:assert/strict";
import { readFile, rm, writeFile } from "node:fs/promises";
import test from "node:test";
import { CHAT_MESSAGES_PATH, CHAT_ROOMS_PATH, createChatRoom } from "../src/runtime/chat-store";
import { CHAT_SUMMARIES_PATH } from "../src/runtime/chat-summary-store";
import { PROJECTS_PATH, saveProjectStore } from "../src/runtime/project-store";
import { postRoomMessage } from "../src/runtime/room-orchestrator";
import { TASKS_PATH, saveTaskStore } from "../src/runtime/task-store";
import type { ProjectStoreSnapshot, TaskStoreSnapshot } from "../src/types";

test("room orchestrator generates planner/coder/reviewer/manager discussion turns in order", async () => {
  const roomsBefore = await readOptionalFile(CHAT_ROOMS_PATH);
  const messagesBefore = await readOptionalFile(CHAT_MESSAGES_PATH);
  const summariesBefore = await readOptionalFile(CHAT_SUMMARIES_PATH);
  const projectsBefore = await readOptionalFile(PROJECTS_PATH);
  const tasksBefore = await readOptionalFile(TASKS_PATH);

  try {
    await saveProjectStore({
      projects: [
        {
          projectId: "mvp-project",
          title: "MVP Project",
          status: "active",
          owner: "operator",
          budget: {},
          updatedAt: "2026-03-19T10:00:00.000Z",
        },
      ],
      updatedAt: "2026-03-19T10:00:00.000Z",
    } satisfies ProjectStoreSnapshot);
    await saveTaskStore({
      tasks: [
        {
          projectId: "mvp-project",
          taskId: "room-mvp",
          title: "Room MVP",
          status: "todo",
          owner: "operator",
          definitionOfDone: ["Room API works", "Room UI works"],
          artifacts: [],
          rollback: { strategy: "manual", steps: [] },
          sessionKeys: [],
          budget: {},
          updatedAt: "2026-03-19T10:00:00.000Z",
        },
      ],
      agentBudgets: [],
      updatedAt: "2026-03-19T10:00:00.000Z",
    } satisfies TaskStoreSnapshot);

    const room = await createChatRoom({
      projectId: "mvp-project",
      taskId: "room-mvp",
      title: "Room MVP",
    });
    const result = await postRoomMessage({
      roomId: room.room.roomId,
      authorRole: "human",
      content: "Please build the task room MVP end to end.",
    });

    assert.equal(result.generatedMessages.length, 4);
    assert.deepEqual(
      result.generatedMessages.map((message) => message.authorRole),
      ["planner", "coder", "reviewer", "manager"],
    );
    assert.equal(result.room.stage, "discussion");
    assert.equal(result.room.assignedExecutor, "coder");
    assert.equal(result.summary.currentOwner, "manager");
    assert(result.summary.latestDecision?.includes("room-first"));
  } finally {
    await restoreOptionalFile(CHAT_ROOMS_PATH, roomsBefore);
    await restoreOptionalFile(CHAT_MESSAGES_PATH, messagesBefore);
    await restoreOptionalFile(CHAT_SUMMARIES_PATH, summariesBefore);
    await restoreOptionalFile(PROJECTS_PATH, projectsBefore);
    await restoreOptionalFile(TASKS_PATH, tasksBefore);
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
