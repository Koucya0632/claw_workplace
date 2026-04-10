import assert from "node:assert/strict";
import { readFile, rm, writeFile } from "node:fs/promises";
import test from "node:test";
import { CHAT_MESSAGES_PATH, CHAT_ROOMS_PATH, createChatRoom } from "../src/runtime/chat-store";
import { CHAT_SUMMARIES_PATH } from "../src/runtime/chat-summary-store";
import { PROJECTS_PATH, saveProjectStore } from "../src/runtime/project-store";
import { assignRoomExecution, submitRoomReview } from "../src/runtime/room-orchestrator";
import { TASKS_PATH, loadTaskStore, saveTaskStore } from "../src/runtime/task-store";
import type { ProjectStoreSnapshot, TaskStoreSnapshot } from "../src/types";

test("room assignment and review keep task state synchronized", async () => {
  const roomsBefore = await readOptionalFile(CHAT_ROOMS_PATH);
  const messagesBefore = await readOptionalFile(CHAT_MESSAGES_PATH);
  const summariesBefore = await readOptionalFile(CHAT_SUMMARIES_PATH);
  const projectsBefore = await readOptionalFile(PROJECTS_PATH);
  const tasksBefore = await readOptionalFile(TASKS_PATH);

  try {
    await saveProjectStore({
      projects: [
        {
          projectId: "sync-project",
          title: "Sync Project",
          status: "active",
          owner: "operator",
          budget: {},
          updatedAt: "2026-03-19T11:00:00.000Z",
        },
      ],
      updatedAt: "2026-03-19T11:00:00.000Z",
    } satisfies ProjectStoreSnapshot);
    await saveTaskStore({
      tasks: [
        {
          projectId: "sync-project",
          taskId: "sync-task",
          title: "Sync task",
          status: "todo",
          owner: "operator",
          definitionOfDone: ["Execution done", "Review complete"],
          artifacts: [],
          rollback: { strategy: "manual", steps: [] },
          sessionKeys: [],
          budget: {},
          updatedAt: "2026-03-19T11:00:00.000Z",
        },
      ],
      agentBudgets: [],
      updatedAt: "2026-03-19T11:00:00.000Z",
    } satisfies TaskStoreSnapshot);

    const room = await createChatRoom({
      projectId: "sync-project",
      taskId: "sync-task",
      title: "Sync task",
      stage: "discussion",
      ownerRole: "manager",
      assignedExecutor: "coder",
    });

    const assigned = await assignRoomExecution({ roomId: room.room.roomId });
    assert.equal(assigned.room.stage, "executing");
    assert.equal(assigned.task.status, "in_progress");
    assert.equal(assigned.task.owner, "coder");
    assert.equal(assigned.task.roomId, room.room.roomId);

    const rejected = await submitRoomReview({
      roomId: room.room.roomId,
      outcome: "rejected",
      note: "Need a second pass.",
      blockTask: true,
    });
    assert.equal(rejected.room.stage, "review");
    assert.equal(rejected.task.status, "blocked");

    const approved = await submitRoomReview({
      roomId: room.room.roomId,
      outcome: "approved",
      note: "Looks good now.",
    });
    assert.equal(approved.room.stage, "completed");
    assert.equal(approved.task.status, "done");

    const reloaded = await loadTaskStore();
    const task = reloaded.tasks.find((item) => item.projectId === "sync-project" && item.taskId === "sync-task");
    assert(task);
    assert.equal(task.status, "done");
    assert.equal(task.roomId, room.room.roomId);
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
