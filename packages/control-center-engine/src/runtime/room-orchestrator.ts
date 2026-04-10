import { buildDiscussionDispatchMessage, buildExecutionStartedMessage, buildReviewOutcomeMessage } from "./agent-dispatch";
import { completeRoomDraftReply, streamRoomDraftReply } from "./collaboration-stream";
import {
  ChatStoreValidationError,
  appendChatMessage,
  createChatHandoff,
  getChatRoom,
  listChatMessages,
  loadChatMessageStore,
  loadChatRoomStore,
  updateChatRoom,
  type CreateChatMessageInput,
} from "./chat-store";
import { buildChatRoomSummary, upsertChatRoomSummary } from "./chat-summary-store";
import { nextDiscussionRole } from "./turn-policy";
import { loadTaskStore, patchTask } from "./task-store";
import type {
  ChatMessage,
  ChatRoom,
  ChatRoomSummary,
  ProjectTask,
  RoomParticipantRole,
  TaskState,
} from "../types";

export interface PostRoomMessageInput extends CreateChatMessageInput {}

export interface RoomMutationWithSummaryResult {
  room: ChatRoom;
  summary: ChatRoomSummary;
  generatedMessages: ChatMessage[];
}

export interface RoomAssignmentResult extends RoomMutationWithSummaryResult {
  task: ProjectTask;
}

export interface RoomReviewInput {
  roomId: string;
  outcome: "approved" | "rejected";
  note?: string;
  blockTask?: boolean;
}

export async function recordRoomHandoff(input: {
  roomId: string;
  fromRole: RoomParticipantRole;
  toRole: RoomParticipantRole;
  note?: string;
}): Promise<RoomMutationWithSummaryResult> {
  let room = await requireRoom(input.roomId);
  const generatedMessages: ChatMessage[] = [];
  const handoff = await createChatHandoff({
    roomId: room.roomId,
    fromRole: input.fromRole,
    toRole: input.toRole,
    note: input.note,
  });

  generatedMessages.push(
    await appendStreamedGeneratedRoomMessage({
      roomId: room.roomId,
      projectId: room.projectId,
      taskId: room.taskId,
      kind: "handoff",
      authorRole: input.fromRole === "human" ? "manager" : input.fromRole,
      authorLabel: titleCaseRole(input.fromRole === "human" ? "manager" : input.fromRole),
      content: `${titleCaseRole(input.fromRole)} handed the room to ${titleCaseRole(input.toRole)}.`,
      payload: {
        fromRole: handoff.handoff.fromRole,
        targetRole: handoff.handoff.toRole,
        handoffId: handoff.handoff.handoffId,
        status: "handoff_recorded",
      },
    }),
  );

  room = (await updateChatRoom({ roomId: room.roomId, ownerRole: input.toRole })).room;
  const summary = await refreshRoomSummary(room.roomId);
  return {
    room,
    summary,
    generatedMessages,
  };
}

export async function postRoomMessage(
  input: PostRoomMessageInput,
): Promise<RoomMutationWithSummaryResult & { message: ChatMessage }> {
  const created = await appendChatMessage(input);
  let room = created.room;
  const generatedMessages: ChatMessage[] = [];

  if (created.message.authorRole === "human" && (room.stage === "intake" || room.stage === "discussion")) {
    if (room.stage === "intake") {
      room = (await updateChatRoom({
        roomId: room.roomId,
        stage: "discussion",
        ownerRole: "planner",
      })).room;
    }
    const discussion = await runDiscussionRound(room.roomId);
    room = discussion.room;
    generatedMessages.push(...discussion.generatedMessages);
  } else if (created.message.authorRole === room.assignedExecutor && room.stage === "assigned") {
    room = (await updateChatRoom({
      roomId: room.roomId,
      stage: "executing",
      ownerRole: room.assignedExecutor,
    })).room;
  }

  const summary = await refreshRoomSummary(room.roomId);
  return {
    room,
    message: created.message,
    summary,
    generatedMessages,
  };
}

export async function runDiscussionRound(roomId: string): Promise<RoomMutationWithSummaryResult> {
  let room = await requireRoom(roomId);
  const task = await requireTaskForRoom(room);
  const generatedMessages: ChatMessage[] = [];

  while (true) {
    const messages = await readRoomMessages(room.roomId);
    const role = nextDiscussionRole(room, messages);
    if (!role) break;

    const dispatch = buildDiscussionDispatchMessage(role, {
      roomId: room.roomId,
      task,
      recentMessages: messages,
    });
    const message = await appendStreamedGeneratedRoomMessage({
      roomId: dispatch.roomId,
      projectId: task.projectId,
      taskId: task.taskId,
      kind: dispatch.kind ?? "chat",
      authorRole: dispatch.authorRole,
      authorLabel: dispatch.authorLabel ?? titleCaseRole(dispatch.authorRole),
      content: dispatch.content,
      payload: dispatch.payload,
      mentions: dispatch.mentions,
      participantId: dispatch.participantId,
      sessionKey: dispatch.sessionKey,
    });
    generatedMessages.push(message);
    room = (
      await updateChatRoom({
        roomId: room.roomId,
        stage: "discussion",
        ownerRole: role,
        assignedExecutor: message.payload?.executor ?? room.assignedExecutor,
        proposal: message.payload?.proposal ?? room.proposal,
        decision: message.payload?.decision ?? room.decision,
        doneWhen: message.payload?.doneWhen ?? room.doneWhen,
      })
    ).room;
  }

  const summary = await refreshRoomSummary(room.roomId);
  return {
    room,
    summary,
    generatedMessages,
  };
}

export async function assignRoomExecution(input: {
  roomId: string;
  executorRole?: RoomParticipantRole;
  note?: string;
  autoStartExecution?: boolean;
}): Promise<RoomAssignmentResult> {
  let room = await requireRoom(input.roomId);
  const task = await requireTaskForRoom(room);
  const executor = input.executorRole ?? room.assignedExecutor ?? "coder";
  const generatedMessages: ChatMessage[] = [];

  const handoff = await createChatHandoff({
    roomId: room.roomId,
    fromRole: room.ownerRole,
    toRole: executor,
    note: input.note,
  });
  generatedMessages.push(
    await appendStreamedGeneratedRoomMessage({
      roomId: room.roomId,
      projectId: room.projectId,
      taskId: room.taskId,
      kind: "handoff",
      authorRole: "manager",
      authorLabel: "Manager",
      content: `Manager handed "${task.title}" to ${titleCaseRole(executor)}.`,
      payload: {
        fromRole: handoff.handoff.fromRole,
        targetRole: handoff.handoff.toRole,
        handoffId: handoff.handoff.handoffId,
        executor,
        status: "handoff_recorded",
        taskStatus: "in_progress",
      },
    }),
  );

  room = (
    await updateChatRoom({
      roomId: room.roomId,
      stage: "assigned",
      ownerRole: executor,
      assignedExecutor: executor,
    })
  ).room;

  const patchedTask = await patchTask({
    taskId: task.taskId,
    projectId: task.projectId,
    status: "in_progress",
    owner: executor,
    roomId: room.roomId,
  });

  if (input.autoStartExecution !== false) {
    const executionStartedMessage = buildExecutionStartedMessage(room.roomId, executor, patchedTask.task);
    generatedMessages.push(await appendStreamedGeneratedRoomMessage({
      roomId: executionStartedMessage.roomId,
      projectId: room.projectId,
      taskId: room.taskId,
      kind: executionStartedMessage.kind ?? "status",
      authorRole: executionStartedMessage.authorRole,
      authorLabel: executionStartedMessage.authorLabel ?? titleCaseRole(executionStartedMessage.authorRole),
      content: executionStartedMessage.content,
      payload: executionStartedMessage.payload,
      mentions: executionStartedMessage.mentions,
      participantId: executionStartedMessage.participantId,
      sessionKey: executionStartedMessage.sessionKey,
    }));
    room = (
      await updateChatRoom({
        roomId: room.roomId,
        stage: "executing",
        ownerRole: executor,
      })
    ).room;
  }

  const summary = await refreshRoomSummary(room.roomId);
  return {
    room,
    task: patchedTask.task,
    summary,
    generatedMessages,
  };
}

export async function submitRoomReview(input: RoomReviewInput): Promise<RoomAssignmentResult> {
  let room = await requireRoom(input.roomId);
  const task = await requireTaskForRoom(room);
  const generatedMessages: ChatMessage[] = [];

  const nextTaskStatus: TaskState =
    input.outcome === "approved" ? "done" : input.blockTask ? "blocked" : "in_progress";
  const reviewMessage = buildReviewOutcomeMessage({
    roomId: room.roomId,
    outcome: input.outcome,
    note: input.note,
    taskStatus: nextTaskStatus,
  });
  generatedMessages.push(await appendStreamedGeneratedRoomMessage({
    roomId: reviewMessage.roomId,
    projectId: room.projectId,
    taskId: room.taskId,
    kind: reviewMessage.kind ?? "result",
    authorRole: reviewMessage.authorRole,
    authorLabel: reviewMessage.authorLabel ?? titleCaseRole(reviewMessage.authorRole),
    content: reviewMessage.content,
    payload: reviewMessage.payload,
    mentions: reviewMessage.mentions,
    participantId: reviewMessage.participantId,
    sessionKey: reviewMessage.sessionKey,
  }));

  room = (
    await updateChatRoom({
      roomId: room.roomId,
      stage: input.outcome === "approved" ? "completed" : "review",
      ownerRole: input.outcome === "approved" ? "manager" : room.assignedExecutor ?? "coder",
    })
  ).room;

  const patchedTask = await patchTask({
    taskId: task.taskId,
    projectId: task.projectId,
    status: nextTaskStatus,
    owner:
      input.outcome === "approved"
        ? room.ownerRole
        : room.assignedExecutor ?? task.owner,
    roomId: room.roomId,
  });

  const summary = await refreshRoomSummary(room.roomId);
  return {
    room,
    task: patchedTask.task,
    summary,
    generatedMessages,
  };
}

export async function refreshRoomSummary(roomId: string): Promise<ChatRoomSummary> {
  const room = await requireRoom(roomId);
  const messages = await readRoomMessages(room.roomId);
  return (await upsertChatRoomSummary(room, messages)).summary;
}

export async function readRoomDetail(roomId: string): Promise<{
  room: ChatRoom;
  messages: ChatMessage[];
  summary: ChatRoomSummary;
}> {
  const room = await requireRoom(roomId);
  const messages = await readRoomMessages(roomId);
  const summary = buildChatRoomSummary(room, messages);
  return { room, messages, summary };
}

async function requireRoom(roomId: string): Promise<ChatRoom> {
  const store = await loadChatRoomStore();
  const room = getChatRoom(store, roomId);
  if (!room) {
    throw new ChatStoreValidationError(`roomId '${roomId}' was not found.`, ["roomId"], 404);
  }
  return room;
}

async function requireTaskForRoom(room: ChatRoom): Promise<ProjectTask> {
  const taskStore = await loadTaskStore();
  const task = taskStore.tasks.find(
    (item) => item.projectId === room.projectId && item.taskId === room.taskId,
  );
  if (!task) {
    throw new ChatStoreValidationError(
      `task '${room.projectId}:${room.taskId}' linked to room '${room.roomId}' was not found.`,
      ["taskId"],
      404,
    );
  }
  return task;
}

async function readRoomMessages(roomId: string): Promise<ChatMessage[]> {
  const store = await loadChatMessageStore();
  return listChatMessages(store, roomId);
}

async function appendStreamedGeneratedRoomMessage(input: {
  roomId: string;
  projectId: string;
  taskId: string;
  kind: ChatMessage["kind"];
  authorRole: RoomParticipantRole;
  authorLabel: string;
  content: string;
  mentions?: ChatMessage["mentions"];
  participantId?: string;
  sessionKey?: string;
  payload?: ChatMessage["payload"];
}): Promise<ChatMessage> {
  const draftId = await streamRoomDraftReply({
    roomId: input.roomId,
    projectId: input.projectId,
    taskId: input.taskId,
    authorRole: input.authorRole,
    authorLabel: input.authorLabel,
    messageKind: input.kind,
    content: input.content,
  });
  const message = (
    await appendChatMessage({
      roomId: input.roomId,
      kind: input.kind,
      authorRole: input.authorRole,
      authorLabel: input.authorLabel,
      content: input.content,
      mentions: input.mentions,
      participantId: input.participantId,
      sessionKey: input.sessionKey,
      payload: input.payload,
    })
  ).message;
  completeRoomDraftReply({
    roomId: input.roomId,
    projectId: input.projectId,
    taskId: input.taskId,
    draftId,
    messageId: message.messageId,
    content: input.content,
  });
  return message;
}

function titleCaseRole(role: RoomParticipantRole): string {
  if (role === "human") return "Operator";
  if (role === "planner") return "Planner";
  if (role === "coder") return "Coder";
  if (role === "reviewer") return "Reviewer";
  return "Manager";
}
