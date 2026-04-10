import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { getRuntimeDir, resolveRuntimePath } from "./runtime-path";
import { publishRoomStreamEvent } from "./collaboration-stream";
import type {
  ChatMessage,
  ChatMessagePayload,
  ChatMessageStoreSnapshot,
  ChatRoom,
  ChatRoomStoreSnapshot,
  HandoffRecord,
  MessageKind,
  RoomParticipant,
  RoomParticipantRole,
  RoomStage,
} from "../types";

const RUNTIME_DIR = getRuntimeDir();
export const CHAT_ROOMS_PATH = resolveRuntimePath("chat-rooms.json");
export const CHAT_MESSAGES_PATH = resolveRuntimePath("chat-messages.json");

const ROOM_ID_REGEX = /^[A-Za-z0-9._:-]+$/;
const TASK_ID_REGEX = /^[A-Za-z0-9._:-]+$/;
const PROJECT_ID_REGEX = /^[A-Za-z0-9._:-]+$/;
const DEFAULT_ROOM_STAGES: RoomStage[] = [
  "intake",
  "discussion",
  "assigned",
  "executing",
  "review",
  "completed",
];
const DEFAULT_MESSAGE_KINDS: MessageKind[] = ["chat", "proposal", "decision", "handoff", "status", "result"];
const DEFAULT_ROOM_ROLES: RoomParticipantRole[] = ["human", "planner", "coder", "reviewer", "manager"];

const EMPTY_ROOM_STORE: ChatRoomStoreSnapshot = {
  rooms: [],
  updatedAt: "1970-01-01T00:00:00.000Z",
};

const EMPTY_MESSAGE_STORE: ChatMessageStoreSnapshot = {
  messages: [],
  updatedAt: "1970-01-01T00:00:00.000Z",
};

export class ChatStoreValidationError extends Error {
  readonly statusCode: number;
  readonly issues: string[];

  constructor(message: string, issues: string[] = [], statusCode = 400) {
    super(message);
    this.name = "ChatStoreValidationError";
    this.issues = issues;
    this.statusCode = statusCode;
  }
}

export interface CreateChatRoomInput {
  projectId: string;
  taskId: string;
  roomId?: string;
  title?: string;
  stage?: RoomStage;
  ownerRole?: RoomParticipantRole;
  assignedExecutor?: RoomParticipantRole;
  participants?: RoomParticipant[];
  sessionKeys?: string[];
  proposal?: string;
  decision?: string;
  doneWhen?: string;
}

export interface CreateChatMessageInput {
  roomId: string;
  kind?: MessageKind;
  authorRole: RoomParticipantRole;
  authorLabel?: string;
  participantId?: string;
  content: string;
  mentions?: RoomParticipantRole[];
  sessionKey?: string;
  payload?: ChatMessagePayload;
  messageId?: string;
  createdAt?: string;
}

export interface UpdateChatRoomInput {
  roomId: string;
  stage?: RoomStage;
  ownerRole?: RoomParticipantRole;
  assignedExecutor?: RoomParticipantRole | null;
  sessionKeys?: string[];
  proposal?: string | null;
  decision?: string | null;
  doneWhen?: string | null;
}

export interface DeleteChatRoomInput {
  roomId: string;
  deleteMessages?: boolean;
}

export interface CreateChatHandoffInput {
  roomId: string;
  fromRole: RoomParticipantRole;
  toRole: RoomParticipantRole;
  note?: string;
  createdAt?: string;
}

export interface ChatRoomMutationResult {
  path: string;
  room: ChatRoom;
}

export interface ChatMessageMutationResult {
  path: string;
  room: ChatRoom;
  message: ChatMessage;
}

export interface ChatHandoffMutationResult {
  path: string;
  room: ChatRoom;
  handoff: HandoffRecord;
}

export interface ChatRoomDeleteResult {
  path: string;
  room: ChatRoom;
  removedMessages: number;
}

export async function loadChatRoomStore(): Promise<ChatRoomStoreSnapshot> {
  try {
    const raw = await readFile(CHAT_ROOMS_PATH, "utf8");
    return normalizeChatRoomStore(JSON.parse(raw));
  } catch {
    return cloneEmptyRoomStore();
  }
}

export async function loadChatMessageStore(): Promise<ChatMessageStoreSnapshot> {
  try {
    const raw = await readFile(CHAT_MESSAGES_PATH, "utf8");
    return normalizeChatMessageStore(JSON.parse(raw));
  } catch {
    return cloneEmptyMessageStore();
  }
}

export async function saveChatRoomStore(next: ChatRoomStoreSnapshot): Promise<string> {
  const normalized = normalizeChatRoomStore({
    ...next,
    updatedAt: new Date().toISOString(),
  });
  await mkdir(RUNTIME_DIR, { recursive: true });
  await writeFile(CHAT_ROOMS_PATH, JSON.stringify(normalized, null, 2), "utf8");
  return CHAT_ROOMS_PATH;
}

export async function saveChatMessageStore(next: ChatMessageStoreSnapshot): Promise<string> {
  const normalized = normalizeChatMessageStore({
    ...next,
    updatedAt: new Date().toISOString(),
  });
  await mkdir(RUNTIME_DIR, { recursive: true });
  await writeFile(CHAT_MESSAGES_PATH, JSON.stringify(normalized, null, 2), "utf8");
  return CHAT_MESSAGES_PATH;
}

export function listChatRooms(store: ChatRoomStoreSnapshot): ChatRoom[] {
  return [...store.rooms].sort(compareRooms);
}

export function getChatRoom(store: ChatRoomStoreSnapshot, roomId: string): ChatRoom | undefined {
  return store.rooms.find((room) => room.roomId === roomId.trim());
}

export function getChatRoomByTask(
  store: ChatRoomStoreSnapshot,
  taskId: string,
  projectId?: string,
): ChatRoom | undefined {
  const normalizedTaskId = taskId.trim();
  const normalizedProjectId = projectId?.trim();
  return store.rooms.find(
    (room) => room.taskId === normalizedTaskId && (!normalizedProjectId || room.projectId === normalizedProjectId),
  );
}

export function listChatMessages(store: ChatMessageStoreSnapshot, roomId: string): ChatMessage[] {
  const normalizedRoomId = roomId.trim();
  return store.messages
    .filter((message) => message.roomId === normalizedRoomId)
    .sort(compareMessages);
}

export async function createChatRoom(input: unknown): Promise<ChatRoomMutationResult> {
  const payload = validateCreateChatRoomInput(input);
  const store = await loadChatRoomStore();
  if (store.rooms.some((room) => room.roomId === payload.roomId)) {
    throw new ChatStoreValidationError(`roomId '${payload.roomId}' already exists.`, ["roomId"], 409);
  }
  if (getChatRoomByTask(store, payload.taskId, payload.projectId)) {
    throw new ChatStoreValidationError(
      `task '${payload.projectId}:${payload.taskId}' already has a primary room.`,
      ["taskId"],
      409,
    );
  }

  const now = new Date().toISOString();
  const room: ChatRoom = {
    roomId: payload.roomId,
    projectId: payload.projectId,
    taskId: payload.taskId,
    title: payload.title ?? payload.taskId,
    stage: payload.stage ?? "intake",
    ownerRole: payload.ownerRole ?? "human",
    assignedExecutor: payload.assignedExecutor,
    proposal: payload.proposal,
    decision: payload.decision,
    doneWhen: payload.doneWhen,
    participants: payload.participants ?? defaultRoomParticipants(),
    handoffs: [],
    sessionKeys: payload.sessionKeys ?? [],
    lastMessageAt: undefined,
    createdAt: now,
    updatedAt: now,
  };

  store.rooms.push(room);
  store.updatedAt = now;
  const path = await saveChatRoomStore(store);
  publishRoomStreamEvent({
    type: "invalidate",
    roomId: room.roomId,
    projectId: room.projectId,
    taskId: room.taskId,
    reason: "room_created",
  });
  return { path, room };
}

export async function updateChatRoom(input: UpdateChatRoomInput): Promise<ChatRoomMutationResult> {
  const payload = validateUpdateChatRoomInput(input);
  const store = await loadChatRoomStore();
  const room = getChatRoom(store, payload.roomId);
  if (!room) {
    throw new ChatStoreValidationError(`roomId '${payload.roomId}' was not found.`, [], 404);
  }

  const now = new Date().toISOString();
  if (payload.stage) room.stage = payload.stage;
  if (payload.ownerRole) room.ownerRole = payload.ownerRole;
  if (payload.assignedExecutor !== undefined) {
    room.assignedExecutor = payload.assignedExecutor ?? undefined;
  }
  if (payload.sessionKeys) room.sessionKeys = payload.sessionKeys;
  if (payload.proposal !== undefined) room.proposal = payload.proposal ?? undefined;
  if (payload.decision !== undefined) room.decision = payload.decision ?? undefined;
  if (payload.doneWhen !== undefined) room.doneWhen = payload.doneWhen ?? undefined;
  room.updatedAt = now;
  store.updatedAt = now;

  const path = await saveChatRoomStore(store);
  publishRoomStreamEvent({
    type: "invalidate",
    roomId: room.roomId,
    projectId: room.projectId,
    taskId: room.taskId,
    reason: "room_updated",
  });
  return { path, room };
}

export async function appendChatMessage(input: unknown): Promise<ChatMessageMutationResult> {
  const payload = validateCreateChatMessageInput(input);
  const [roomStore, messageStore] = await Promise.all([loadChatRoomStore(), loadChatMessageStore()]);
  const room = getChatRoom(roomStore, payload.roomId);
  if (!room) {
    throw new ChatStoreValidationError(`roomId '${payload.roomId}' was not found.`, ["roomId"], 404);
  }

  const message: ChatMessage = {
    roomId: payload.roomId,
    messageId: payload.messageId ?? randomUUID(),
    kind: payload.kind ?? "chat",
    authorRole: payload.authorRole,
    authorLabel: payload.authorLabel ?? defaultParticipantLabel(payload.authorRole),
    participantId: payload.participantId,
    content: payload.content,
    mentions: payload.mentions ?? [],
    sessionKey: payload.sessionKey,
    payload: payload.payload,
    createdAt: payload.createdAt ?? new Date().toISOString(),
  };

  messageStore.messages.push(message);
  messageStore.updatedAt = message.createdAt;
  room.lastMessageAt = message.createdAt;
  room.updatedAt = message.createdAt;

  if (message.payload?.proposal) room.proposal = message.payload.proposal;
  if (message.payload?.decision) room.decision = message.payload.decision;
  if (message.payload?.executor) room.assignedExecutor = message.payload.executor;
  if (message.payload?.doneWhen) room.doneWhen = message.payload.doneWhen;
  if (message.payload?.sessionKey && !room.sessionKeys.includes(message.payload.sessionKey)) {
    room.sessionKeys = [...room.sessionKeys, message.payload.sessionKey];
  }
  if (message.sessionKey && !room.sessionKeys.includes(message.sessionKey)) {
    room.sessionKeys = [...room.sessionKeys, message.sessionKey];
  }
  roomStore.updatedAt = message.createdAt;

  const [roomsPath, messagesPath] = await Promise.all([
    saveChatRoomStore(roomStore),
    saveChatMessageStore(messageStore),
  ]);
  publishRoomStreamEvent({
    type: "invalidate",
    roomId: room.roomId,
    projectId: room.projectId,
    taskId: room.taskId,
    reason: "message_created",
    messageId: message.messageId,
    messageKind: message.kind,
    authorRole: message.authorRole,
    authorLabel: message.authorLabel,
  });
  return {
    path: `${roomsPath}|${messagesPath}`,
    room,
    message,
  };
}

export async function createChatHandoff(input: unknown): Promise<ChatHandoffMutationResult> {
  const payload = validateCreateChatHandoffInput(input);
  const store = await loadChatRoomStore();
  const room = getChatRoom(store, payload.roomId);
  if (!room) {
    throw new ChatStoreValidationError(`roomId '${payload.roomId}' was not found.`, ["roomId"], 404);
  }

  const handoff: HandoffRecord = {
    handoffId: randomUUID(),
    roomId: payload.roomId,
    taskId: room.taskId,
    fromRole: payload.fromRole,
    toRole: payload.toRole,
    note: payload.note,
    createdAt: payload.createdAt ?? new Date().toISOString(),
  };

  room.handoffs.push(handoff);
  room.ownerRole = payload.toRole;
  room.updatedAt = handoff.createdAt;
  store.updatedAt = handoff.createdAt;

  const path = await saveChatRoomStore(store);
  return { path, room, handoff };
}

export async function deleteChatRoom(input: DeleteChatRoomInput): Promise<ChatRoomDeleteResult> {
  const payload = validateDeleteChatRoomInput(input);
  const [roomStore, messageStore] = await Promise.all([loadChatRoomStore(), loadChatMessageStore()]);
  const room = getChatRoom(roomStore, payload.roomId);
  if (!room) {
    throw new ChatStoreValidationError(`roomId '${payload.roomId}' was not found.`, ["roomId"], 404);
  }

  const deletedRoom = { ...room };
  const now = new Date().toISOString();
  roomStore.rooms = roomStore.rooms.filter((item) => item.roomId !== payload.roomId);
  roomStore.updatedAt = now;

  let removedMessages = 0;
  if (payload.deleteMessages) {
    const nextMessages = messageStore.messages.filter((message) => message.roomId !== payload.roomId);
    removedMessages = messageStore.messages.length - nextMessages.length;
    messageStore.messages = nextMessages;
    messageStore.updatedAt = now;
  }

  const pathParts = await Promise.all([
    saveChatRoomStore(roomStore),
    payload.deleteMessages ? saveChatMessageStore(messageStore) : Promise.resolve(CHAT_MESSAGES_PATH),
  ]);

  publishRoomStreamEvent({
    type: "invalidate",
    roomId: deletedRoom.roomId,
    projectId: deletedRoom.projectId,
    taskId: deletedRoom.taskId,
    reason: "room_deleted",
  });
  return {
    path: pathParts.join("|"),
    room: deletedRoom,
    removedMessages,
  };
}

export function defaultRoomParticipants(): RoomParticipant[] {
  return DEFAULT_ROOM_ROLES.map((role) => ({
    participantId: role,
    role,
    label: defaultParticipantLabel(role),
    active: true,
  }));
}

function validateCreateChatRoomInput(input: unknown): CreateChatRoomInput & { roomId: string } {
  const obj = ensureObject(input, "create room payload");
  const issues: string[] = [];
  const projectId = requiredProjectId(obj.projectId, "projectId", issues);
  const taskId = requiredTaskId(obj.taskId, "taskId", issues);
  const roomId = optionalRoomId(obj.roomId, "roomId", issues) ?? `${projectId}:${taskId}`;
  const title = optionalBoundedString(obj.title, "title", 180, issues);
  const stage = optionalRoomStage(obj.stage, "stage", issues);
  const ownerRole = optionalRoomParticipantRole(obj.ownerRole, "ownerRole", issues);
  const assignedExecutor = optionalRoomParticipantRole(obj.assignedExecutor, "assignedExecutor", issues);
  const sessionKeys = optionalStringArray(obj.sessionKeys, "sessionKeys", issues, 200);
  const participants = optionalParticipants(obj.participants, "participants", issues);
  const proposal = optionalBoundedString(obj.proposal, "proposal", 600, issues);
  const decision = optionalBoundedString(obj.decision, "decision", 600, issues);
  const doneWhen = optionalBoundedString(obj.doneWhen, "doneWhen", 240, issues);

  if (issues.length > 0) {
    throw new ChatStoreValidationError("Invalid create room payload.", issues, 400);
  }

  return {
    roomId,
    projectId,
    taskId,
    title,
    stage,
    ownerRole,
    assignedExecutor,
    sessionKeys,
    participants,
    proposal,
    decision,
    doneWhen,
  };
}

function validateUpdateChatRoomInput(input: UpdateChatRoomInput): UpdateChatRoomInput {
  const obj = ensureObject(input, "update room payload");
  const issues: string[] = [];
  const roomId = requiredRoomId(obj.roomId, "roomId", issues);
  const stage = optionalRoomStage(obj.stage, "stage", issues);
  const ownerRole = optionalRoomParticipantRole(obj.ownerRole, "ownerRole", issues);
  const sessionKeys = optionalStringArray(obj.sessionKeys, "sessionKeys", issues, 200);
  const proposal = optionalNullableBoundedString(obj.proposal, "proposal", 600, issues);
  const decision = optionalNullableBoundedString(obj.decision, "decision", 600, issues);
  const doneWhen = optionalNullableBoundedString(obj.doneWhen, "doneWhen", 240, issues);
  const assignedExecutor = optionalNullableRoomParticipantRole(obj.assignedExecutor, "assignedExecutor", issues);

  if (
    stage === undefined &&
    ownerRole === undefined &&
    sessionKeys === undefined &&
    proposal === undefined &&
    decision === undefined &&
    doneWhen === undefined &&
    assignedExecutor === undefined
  ) {
    issues.push("at least one updatable room field is required");
  }

  if (issues.length > 0) {
    throw new ChatStoreValidationError("Invalid update room payload.", issues, 400);
  }

  return {
    roomId,
    stage,
    ownerRole,
    sessionKeys,
    proposal,
    decision,
    doneWhen,
    assignedExecutor,
  };
}

function validateDeleteChatRoomInput(input: DeleteChatRoomInput): DeleteChatRoomInput & { roomId: string } {
  const obj = ensureObject(input, "delete room payload");
  const issues: string[] = [];
  const roomId = requiredRoomId(obj.roomId, "roomId", issues);
  const deleteMessages = obj.deleteMessages === true;

  if (issues.length > 0) {
    throw new ChatStoreValidationError("Invalid delete room payload.", issues, 400);
  }

  return {
    roomId,
    deleteMessages,
  };
}

function validateCreateChatMessageInput(input: unknown): CreateChatMessageInput {
  const obj = ensureObject(input, "create message payload");
  const issues: string[] = [];
  const roomId = requiredRoomId(obj.roomId, "roomId", issues);
  const kind = optionalMessageKind(obj.kind, "kind", issues);
  const authorRole = requiredRoomParticipantRole(obj.authorRole, "authorRole", issues);
  const authorLabel = optionalBoundedString(obj.authorLabel, "authorLabel", 80, issues);
  const participantId = optionalBoundedString(obj.participantId, "participantId", 80, issues);
  const content = requiredText(obj.content, "content", 4000, issues);
  const mentions = optionalRoleArray(obj.mentions, "mentions", issues);
  const sessionKey = optionalBoundedString(obj.sessionKey, "sessionKey", 220, issues);
  const payload = optionalMessagePayload(obj.payload, "payload", issues);
  const messageId = optionalBoundedString(obj.messageId, "messageId", 120, issues);
  const createdAt = optionalIsoString(obj.createdAt, "createdAt", issues);

  if (issues.length > 0) {
    throw new ChatStoreValidationError("Invalid create message payload.", issues, 400);
  }

  return {
    roomId,
    kind,
    authorRole,
    authorLabel,
    participantId,
    content,
    mentions,
    sessionKey,
    payload,
    messageId,
    createdAt,
  };
}

function validateCreateChatHandoffInput(input: unknown): CreateChatHandoffInput {
  const obj = ensureObject(input, "create handoff payload");
  const issues: string[] = [];
  const roomId = requiredRoomId(obj.roomId, "roomId", issues);
  const fromRole = requiredRoomParticipantRole(obj.fromRole, "fromRole", issues);
  const toRole = requiredRoomParticipantRole(obj.toRole, "toRole", issues);
  const note = optionalBoundedString(obj.note, "note", 320, issues);
  const createdAt = optionalIsoString(obj.createdAt, "createdAt", issues);

  if (issues.length > 0) {
    throw new ChatStoreValidationError("Invalid handoff payload.", issues, 400);
  }

  return {
    roomId,
    fromRole,
    toRole,
    note,
    createdAt,
  };
}

function normalizeChatRoomStore(input: unknown): ChatRoomStoreSnapshot {
  const obj = asObject(input);
  if (!obj) return cloneEmptyRoomStore();

  return {
    rooms: normalizeRooms(asArray(obj.rooms)),
    updatedAt: asIsoString(obj.updatedAt),
  };
}

function normalizeChatMessageStore(input: unknown): ChatMessageStoreSnapshot {
  const obj = asObject(input);
  if (!obj) return cloneEmptyMessageStore();

  return {
    messages: normalizeMessages(asArray(obj.messages)),
    updatedAt: asIsoString(obj.updatedAt),
  };
}

function normalizeRooms(rooms: unknown[] | undefined): ChatRoom[] {
  if (!rooms) return [];
  const unique = new Map<string, ChatRoom>();
  for (const input of rooms) {
    const room = normalizeRoom(input);
    if (!room) continue;
    unique.set(room.roomId, room);
  }
  return [...unique.values()].sort(compareRooms);
}

function normalizeMessages(messages: unknown[] | undefined): ChatMessage[] {
  if (!messages) return [];
  return messages
    .map((message) => normalizeMessage(message))
    .filter((message): message is ChatMessage => Boolean(message))
    .sort(compareMessages);
}

function normalizeRoom(input: unknown): ChatRoom | null {
  const obj = asObject(input);
  if (!obj) return null;

  const roomId = asString(obj.roomId)?.trim();
  const projectId = asString(obj.projectId)?.trim();
  const taskId = asString(obj.taskId)?.trim();
  if (!roomId || !ROOM_ID_REGEX.test(roomId) || !projectId || !taskId) return null;

  return {
    roomId,
    projectId,
    taskId,
    title: asString(obj.title)?.trim() || taskId,
    stage: normalizeRoomStage(asString(obj.stage)),
    ownerRole: normalizeRoomParticipantRole(asString(obj.ownerRole)) ?? "human",
    assignedExecutor: normalizeOptionalRole(asString(obj.assignedExecutor)),
    proposal: asString(obj.proposal)?.trim() || undefined,
    decision: asString(obj.decision)?.trim() || undefined,
    doneWhen: asString(obj.doneWhen)?.trim() || undefined,
    participants: normalizeParticipants(asArray(obj.participants)),
    handoffs: normalizeHandoffs(asArray(obj.handoffs), roomId, taskId),
    sessionKeys: toUniqueStringArray(obj.sessionKeys, 200),
    summaryId: asString(obj.summaryId)?.trim() || undefined,
    lastMessageAt: asOptionalIsoString(obj.lastMessageAt),
    createdAt: asIsoString(obj.createdAt),
    updatedAt: asIsoString(obj.updatedAt),
  };
}

function normalizeMessage(input: unknown): ChatMessage | null {
  const obj = asObject(input);
  if (!obj) return null;

  const roomId = asString(obj.roomId)?.trim();
  const messageId = asString(obj.messageId)?.trim();
  const authorRole = normalizeOptionalRole(asString(obj.authorRole));
  if (!roomId || !messageId || !authorRole) return null;

  return {
    roomId,
    messageId,
    kind: normalizeMessageKind(asString(obj.kind)),
    authorRole,
    authorLabel: asString(obj.authorLabel)?.trim() || defaultParticipantLabel(authorRole),
    participantId: asString(obj.participantId)?.trim() || undefined,
    content: asString(obj.content) ?? "",
    mentions: normalizeRoleArray(asArray(obj.mentions) ?? []),
    sessionKey: asString(obj.sessionKey)?.trim() || undefined,
    payload: normalizePayload(asObject(obj.payload)),
    createdAt: asIsoString(obj.createdAt),
  };
}

function normalizeParticipants(participants: unknown[] | undefined): RoomParticipant[] {
  if (!participants || participants.length === 0) return defaultRoomParticipants();

  const unique = new Map<RoomParticipantRole, RoomParticipant>();
  for (const input of participants) {
    const participant = normalizeParticipant(input);
    if (!participant) continue;
    unique.set(participant.role, participant);
  }

  for (const role of DEFAULT_ROOM_ROLES) {
    if (!unique.has(role)) {
      unique.set(role, {
        participantId: role,
        role,
        label: defaultParticipantLabel(role),
        active: true,
      });
    }
  }

  return DEFAULT_ROOM_ROLES.map((role) => unique.get(role) as RoomParticipant);
}

function normalizeParticipant(input: unknown): RoomParticipant | null {
  const obj = asObject(input);
  if (!obj) return null;
  const role = normalizeOptionalRole(asString(obj.role));
  if (!role) return null;

  return {
    participantId: asString(obj.participantId)?.trim() || role,
    role,
    label: asString(obj.label)?.trim() || defaultParticipantLabel(role),
    agentId: asString(obj.agentId)?.trim() || undefined,
    sessionKey: asString(obj.sessionKey)?.trim() || undefined,
    active: asBoolean(obj.active) !== false,
  };
}

function normalizeHandoffs(
  handoffs: unknown[] | undefined,
  roomId: string,
  taskId: string,
): HandoffRecord[] {
  if (!handoffs) return [];
  return handoffs
    .map((input) => normalizeHandoff(input, roomId, taskId))
    .filter((handoff): handoff is HandoffRecord => Boolean(handoff))
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

function normalizeHandoff(input: unknown, roomId: string, taskId: string): HandoffRecord | null {
  const obj = asObject(input);
  if (!obj) return null;
  const fromRole = normalizeOptionalRole(asString(obj.fromRole));
  const toRole = normalizeOptionalRole(asString(obj.toRole));
  const handoffId = asString(obj.handoffId)?.trim();
  if (!handoffId || !fromRole || !toRole) return null;

  return {
    handoffId,
    roomId,
    taskId,
    fromRole,
    toRole,
    note: asString(obj.note)?.trim() || undefined,
    createdAt: asIsoString(obj.createdAt),
  };
}

function normalizePayload(input: Record<string, unknown> | undefined): ChatMessagePayload | undefined {
  if (!input) return undefined;
  const payload: ChatMessagePayload = {};
  const executor = normalizeOptionalRole(asString(input.executor));
  const fromRole = normalizeOptionalRole(asString(input.fromRole));
  const targetRole = normalizeOptionalRole(asString(input.targetRole));
  const taskStatus = normalizeOptionalTaskState(asString(input.taskStatus));
  const reviewOutcome = asString(input.reviewOutcome);

  if (typeof input.proposal === "string" && input.proposal.trim()) payload.proposal = input.proposal.trim();
  if (typeof input.decision === "string" && input.decision.trim()) payload.decision = input.decision.trim();
  if (executor) payload.executor = executor;
  if (typeof input.doneWhen === "string" && input.doneWhen.trim()) payload.doneWhen = input.doneWhen.trim();
  if (fromRole) payload.fromRole = fromRole;
  if (targetRole) payload.targetRole = targetRole;
  if (typeof input.handoffId === "string" && input.handoffId.trim()) payload.handoffId = input.handoffId.trim();
  if (typeof input.status === "string" && input.status.trim()) payload.status = input.status.trim();
  if (taskStatus) payload.taskStatus = taskStatus;
  if (reviewOutcome === "approved" || reviewOutcome === "rejected") payload.reviewOutcome = reviewOutcome;
  if (typeof input.sessionKey === "string" && input.sessionKey.trim()) payload.sessionKey = input.sessionKey.trim();
  if (typeof input.sourceSessionKey === "string" && input.sourceSessionKey.trim()) {
    payload.sourceSessionKey = input.sourceSessionKey.trim();
  }
  if (typeof input.sourceTool === "string" && input.sourceTool.trim()) payload.sourceTool = input.sourceTool.trim();

  return Object.keys(payload).length > 0 ? payload : undefined;
}

function compareRooms(a: ChatRoom, b: ChatRoom): number {
  return toSortableMs(b.updatedAt || b.createdAt) - toSortableMs(a.updatedAt || a.createdAt);
}

function compareMessages(a: ChatMessage, b: ChatMessage): number {
  const delta = toSortableMs(a.createdAt) - toSortableMs(b.createdAt);
  return delta !== 0 ? delta : a.messageId.localeCompare(b.messageId);
}

function cloneEmptyRoomStore(): ChatRoomStoreSnapshot {
  return {
    rooms: [],
    updatedAt: EMPTY_ROOM_STORE.updatedAt,
  };
}

function cloneEmptyMessageStore(): ChatMessageStoreSnapshot {
  return {
    messages: [],
    updatedAt: EMPTY_MESSAGE_STORE.updatedAt,
  };
}

function ensureObject(input: unknown, label: string): Record<string, unknown> {
  const obj = asObject(input);
  if (!obj) throw new ChatStoreValidationError(`${label} must be a JSON object.`, [], 400);
  return obj;
}

function requiredProjectId(value: unknown, field: string, issues: string[]): string {
  if (typeof value !== "string" || value.trim() === "") {
    issues.push(`${field} must be a non-empty string`);
    return "";
  }
  const trimmed = value.trim();
  if (!PROJECT_ID_REGEX.test(trimmed)) {
    issues.push(`${field} may only contain letters, numbers, '.', '_', ':', '-'`);
  }
  if (trimmed.length > 100) {
    issues.push(`${field} must be <= 100 characters`);
  }
  return trimmed;
}

function requiredTaskId(value: unknown, field: string, issues: string[]): string {
  if (typeof value !== "string" || value.trim() === "") {
    issues.push(`${field} must be a non-empty string`);
    return "";
  }
  const trimmed = value.trim();
  if (!TASK_ID_REGEX.test(trimmed)) {
    issues.push(`${field} may only contain letters, numbers, '.', '_', ':', '-'`);
  }
  if (trimmed.length > 120) {
    issues.push(`${field} must be <= 120 characters`);
  }
  return trimmed;
}

function requiredRoomId(value: unknown, field: string, issues: string[]): string {
  const roomId = optionalRoomId(value, field, issues);
  if (!roomId) issues.push(`${field} is required`);
  return roomId ?? "";
}

function optionalRoomId(value: unknown, field: string, issues: string[]): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string" || value.trim() === "") {
    issues.push(`${field} must be a non-empty string`);
    return undefined;
  }
  const trimmed = value.trim();
  if (!ROOM_ID_REGEX.test(trimmed)) {
    issues.push(`${field} may only contain letters, numbers, '.', '_', ':', '-'`);
    return undefined;
  }
  if (trimmed.length > 140) {
    issues.push(`${field} must be <= 140 characters`);
    return undefined;
  }
  return trimmed;
}

function requiredText(value: unknown, field: string, maxLength: number, issues: string[]): string {
  if (typeof value !== "string" || value.trim() === "") {
    issues.push(`${field} must be a non-empty string`);
    return "";
  }
  if (value.length > maxLength) {
    issues.push(`${field} must be <= ${maxLength} characters`);
  }
  return value.trim();
}

function optionalBoundedString(
  value: unknown,
  field: string,
  maxLength: number,
  issues: string[],
): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string") {
    issues.push(`${field} must be a string`);
    return undefined;
  }
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (trimmed.length > maxLength) {
    issues.push(`${field} must be <= ${maxLength} characters`);
    return undefined;
  }
  return trimmed;
}

function optionalNullableBoundedString(
  value: unknown,
  field: string,
  maxLength: number,
  issues: string[],
): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  const normalized = optionalBoundedString(value, field, maxLength, issues);
  return normalized ?? null;
}

function optionalIsoString(value: unknown, field: string, issues: string[]): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string" || Number.isNaN(Date.parse(value))) {
    issues.push(`${field} must be an ISO date-time string`);
    return undefined;
  }
  return new Date(value).toISOString();
}

function optionalStringArray(
  value: unknown,
  field: string,
  issues: string[],
  maxLength: number,
): string[] | undefined {
  if (value === undefined) return undefined;
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    issues.push(`${field} must be an array of strings`);
    return undefined;
  }

  const normalized = [...new Set(value.map((item) => item.trim()).filter(Boolean))];
  if (normalized.some((item) => item.length > maxLength)) {
    issues.push(`${field} values must be <= ${maxLength} characters`);
  }
  return normalized;
}

function optionalParticipants(
  value: unknown,
  field: string,
  issues: string[],
): RoomParticipant[] | undefined {
  if (value === undefined) return undefined;
  if (!Array.isArray(value)) {
    issues.push(`${field} must be an array`);
    return undefined;
  }
  const participants = normalizeParticipants(value);
  if (participants.length === 0) {
    issues.push(`${field} must contain at least one valid participant`);
    return undefined;
  }
  return participants;
}

function optionalMessagePayload(
  value: unknown,
  field: string,
  issues: string[],
): ChatMessagePayload | undefined {
  if (value === undefined) return undefined;
  const obj = asObject(value);
  if (!obj) {
    issues.push(`${field} must be an object`);
    return undefined;
  }
  return normalizePayload(obj);
}

function optionalRoleArray(
  value: unknown,
  field: string,
  issues: string[],
): RoomParticipantRole[] | undefined {
  if (value === undefined) return undefined;
  if (!Array.isArray(value)) {
    issues.push(`${field} must be an array`);
    return undefined;
  }
  const roles = normalizeRoleArray(value);
  if (roles.length !== value.length) {
    issues.push(`${field} must contain only known room roles`);
    return undefined;
  }
  return roles;
}

function optionalRoomStage(value: unknown, field: string, issues: string[]): RoomStage | undefined {
  if (value === undefined) return undefined;
  const normalized = typeof value === "string" ? normalizeRoomStage(value) : undefined;
  if (!normalized || !DEFAULT_ROOM_STAGES.includes(normalized)) {
    issues.push(`${field} must be one of: ${DEFAULT_ROOM_STAGES.join(", ")}`);
    return undefined;
  }
  return normalized;
}

function optionalMessageKind(value: unknown, field: string, issues: string[]): MessageKind | undefined {
  if (value === undefined) return undefined;
  const normalized = typeof value === "string" ? normalizeMessageKind(value) : undefined;
  if (!normalized || !DEFAULT_MESSAGE_KINDS.includes(normalized)) {
    issues.push(`${field} must be one of: ${DEFAULT_MESSAGE_KINDS.join(", ")}`);
    return undefined;
  }
  return normalized;
}

function optionalRoomParticipantRole(
  value: unknown,
  field: string,
  issues: string[],
): RoomParticipantRole | undefined {
  if (value === undefined) return undefined;
  const normalized = typeof value === "string" ? normalizeRoomParticipantRole(value) : undefined;
  if (!normalized) {
    issues.push(`${field} must be one of: ${DEFAULT_ROOM_ROLES.join(", ")}`);
  }
  return normalized;
}

function optionalNullableRoomParticipantRole(
  value: unknown,
  field: string,
  issues: string[],
): RoomParticipantRole | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return optionalRoomParticipantRole(value, field, issues) ?? null;
}

function requiredRoomParticipantRole(
  value: unknown,
  field: string,
  issues: string[],
): RoomParticipantRole {
  const normalized = optionalRoomParticipantRole(value, field, issues);
  if (!normalized) issues.push(`${field} is required`);
  return normalized ?? "human";
}

function normalizeRoomStage(value: string | undefined): RoomStage {
  return value && DEFAULT_ROOM_STAGES.includes(value as RoomStage) ? (value as RoomStage) : "intake";
}

function normalizeMessageKind(value: string | undefined): MessageKind {
  return value && DEFAULT_MESSAGE_KINDS.includes(value as MessageKind) ? (value as MessageKind) : "chat";
}

function normalizeRoomParticipantRole(value: string | undefined): RoomParticipantRole | undefined {
  return value && DEFAULT_ROOM_ROLES.includes(value as RoomParticipantRole)
    ? (value as RoomParticipantRole)
    : undefined;
}

function normalizeOptionalRole(value: string | undefined): RoomParticipantRole | undefined {
  return normalizeRoomParticipantRole(value);
}

function normalizeOptionalTaskState(value: string | undefined): ChatMessagePayload["taskStatus"] | undefined {
  if (value === "todo" || value === "in_progress" || value === "blocked" || value === "done") {
    return value;
  }
  return undefined;
}

function normalizeRoleArray(values: unknown[]): RoomParticipantRole[] {
  return [...new Set(
    values
      .map((value) => (typeof value === "string" ? normalizeRoomParticipantRole(value) : undefined))
      .filter((value): value is RoomParticipantRole => Boolean(value)),
  )];
}

function toUniqueStringArray(value: unknown, maxLength: number): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(
    value
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter((item) => item.length > 0 && item.length <= maxLength),
  )];
}

function defaultParticipantLabel(role: RoomParticipantRole): string {
  if (role === "human") return "Operator";
  if (role === "planner") return "Planner";
  if (role === "coder") return "Coder";
  if (role === "reviewer") return "Reviewer";
  return "Manager";
}

function asIsoString(value: unknown): string {
  if (typeof value === "string" && !Number.isNaN(Date.parse(value))) {
    return new Date(value).toISOString();
  }
  return new Date().toISOString();
}

function asOptionalIsoString(value: unknown): string | undefined {
  if (typeof value !== "string" || Number.isNaN(Date.parse(value))) return undefined;
  return new Date(value).toISOString();
}

function asObject(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function asArray(value: unknown): unknown[] | undefined {
  return Array.isArray(value) ? value : undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function toSortableMs(value: string | undefined): number {
  const parsed = value ? Date.parse(value) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : 0;
}
