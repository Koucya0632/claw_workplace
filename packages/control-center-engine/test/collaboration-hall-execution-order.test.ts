import assert from "node:assert/strict";
import { readFile, rm, writeFile } from "node:fs/promises";
import test from "node:test";
import { CHAT_MESSAGES_PATH, CHAT_ROOMS_PATH } from "../src/runtime/chat-store";
import {
  COLLABORATION_HALL_MESSAGES_PATH,
  COLLABORATION_HALLS_PATH,
  COLLABORATION_TASK_CARDS_PATH,
} from "../src/runtime/collaboration-hall-store";
import { COLLABORATION_HALL_SUMMARIES_PATH } from "../src/runtime/collaboration-hall-summary-store";
import {
  assignHallTaskExecution,
  createHallTaskFromOperatorRequest,
  readCollaborationHall,
  readCollaborationHallTaskDetail,
  recordHallTaskHandoff,
  setHallTaskExecutionOrder,
} from "../src/runtime/collaboration-hall-orchestrator";
import { PROJECTS_PATH } from "../src/runtime/project-store";
import { TASKS_PATH } from "../src/runtime/task-store";

test("execution order persists in hall detail and advances after assign plus handoff", async () => {
  const backups = await backupFiles([
    COLLABORATION_HALLS_PATH,
    COLLABORATION_HALL_MESSAGES_PATH,
    COLLABORATION_TASK_CARDS_PATH,
    COLLABORATION_HALL_SUMMARIES_PATH,
    PROJECTS_PATH,
    TASKS_PATH,
    CHAT_ROOMS_PATH,
    CHAT_MESSAGES_PATH,
  ]);

  try {
    const created = await createHallTaskFromOperatorRequest(
      {
        content: "Create a hall task whose execution order will be planned and advanced.",
      },
      { skipDiscussion: true },
    );
    assert(created.taskCard);

    await setHallTaskExecutionOrder({
      taskCardId: created.taskCard.taskCardId,
      executionItems: [
        {
          itemId: "item-pandas",
          participantId: "pandas",
          task: "Produce the first reviewable pass.",
          handoffToParticipantId: "monkey",
          handoffWhen: "When the first pass is reviewable in the hall.",
        },
        {
          itemId: "item-monkey",
          participantId: "monkey",
          task: "Review the first pass and call out required changes.",
          handoffToParticipantId: "main",
          handoffWhen: "When the review verdict is explicit.",
        },
        {
          itemId: "item-main",
          participantId: "main",
          task: "Close the loop and decide the next owner.",
        },
      ],
    });

    const hallAfterPlanning = await readCollaborationHall();
    const plannedTask = hallAfterPlanning.taskCards.find((taskCard) => taskCard.taskCardId === created.taskCard?.taskCardId);
    assert.deepEqual(plannedTask?.plannedExecutionOrder, ["pandas", "monkey", "main"]);
    assert.equal(plannedTask?.currentOwnerParticipantId, undefined);
    assert.equal(plannedTask?.currentExecutionItem, undefined);
    assert.equal(plannedTask?.plannedExecutionItems[0]?.handoffToParticipantId, "monkey");
    assert.equal(plannedTask?.plannedExecutionItems[1]?.handoffToParticipantId, "main");
    const plannedSummary = hallAfterPlanning.taskSummaries.find((summary) => summary.taskCardId === created.taskCard?.taskCardId);
    assert.match(plannedSummary?.nextAction ?? "", /pandas/i);

    await assignHallTaskExecution({
      taskCardId: created.taskCard.taskCardId,
    });

    const detailAfterAssign = await readCollaborationHallTaskDetail(created.taskCard.taskCardId);
    assert.equal(detailAfterAssign.taskCard.currentOwnerParticipantId, "pandas");
    assert.deepEqual(detailAfterAssign.taskCard.plannedExecutionOrder, ["monkey", "main"]);
    assert.match(detailAfterAssign.taskSummary.nextAction, /monkey/i);

    await recordHallTaskHandoff({
      taskCardId: created.taskCard.taskCardId,
      fromParticipantId: "pandas",
      toParticipantId: "monkey",
      handoff: {
        goal: "Pass to the next queued owner",
        currentResult: "First slice done",
        doneWhen: "Second slice done",
        blockers: [],
        nextOwner: "monkey",
        requiresInputFrom: [],
      },
    });

    const detailAfterHandoff = await readCollaborationHallTaskDetail(created.taskCard.taskCardId);
    assert.equal(detailAfterHandoff.taskCard.currentOwnerParticipantId, "monkey");
    assert.deepEqual(detailAfterHandoff.taskCard.plannedExecutionOrder, ["main"]);
    assert.match(detailAfterHandoff.taskSummary.nextAction, /main/i);
  } finally {
    await restoreFiles(backups);
  }
});

async function backupFiles(paths: string[]): Promise<Map<string, string | undefined>> {
  const backups = new Map<string, string | undefined>();
  for (const path of paths) backups.set(path, await readOptionalFile(path));
  return backups;
}

async function restoreFiles(backups: Map<string, string | undefined>): Promise<void> {
  for (const [path, content] of backups.entries()) {
    if (content === undefined) await rm(path, { force: true });
    else await writeFile(path, content, "utf8");
  }
}

async function readOptionalFile(path: string): Promise<string | undefined> {
  try {
    return await readFile(path, "utf8");
  } catch {
    return undefined;
  }
}
