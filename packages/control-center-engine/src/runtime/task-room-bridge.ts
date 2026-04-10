import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { getRuntimeDir, resolveRuntimePath } from "./runtime-path";
import {
  OPENCLAW_CONTROL_UI_URL,
  TASK_ROOM_BRIDGE_DISCORD_WEBHOOK_URL,
  TASK_ROOM_BRIDGE_ENABLED,
  TASK_ROOM_BRIDGE_TELEGRAM_BOT_TOKEN,
  TASK_ROOM_BRIDGE_TELEGRAM_CHAT_ID,
} from "../config";
import type {
  ChatMessage,
  ChatRoom,
  MessageKind,
  ProjectTask,
  RoomParticipantRole,
  RoomStage,
  TaskState,
} from "../types";

const RUNTIME_DIR = getRuntimeDir();
export const TASK_ROOM_BRIDGE_EVENTS_PATH = resolveRuntimePath("task-room-bridge-events.json");

export type TaskRoomBridgeTarget = "discord" | "telegram";
export type TaskRoomBridgeEventType =
  | "room_created"
  | "message_posted"
  | "handoff_recorded"
  | "executor_assigned"
  | "review_submitted"
  | "stage_changed";

export type TaskRoomBridgeDeliveryStatus = "delivered" | "partial" | "local_only" | "failed";

export interface TaskRoomBridgeEvent {
  eventId: string;
  type: TaskRoomBridgeEventType;
  status: TaskRoomBridgeDeliveryStatus;
  roomId: string;
  projectId: string;
  taskId: string;
  roomTitle: string;
  roomStage: RoomStage;
  ownerRole: RoomParticipantRole;
  assignedExecutor?: RoomParticipantRole;
  taskStatus?: TaskState;
  authorRole?: RoomParticipantRole;
  messageId?: string;
  messageKind?: MessageKind;
  messageSnippet?: string;
  decision?: string;
  note?: string;
  requestId?: string;
  roomUrl?: string;
  deliveredTargets: TaskRoomBridgeTarget[];
  skippedTargets: string[];
  errorTargets: string[];
  metadata?: Record<string, unknown>;
  createdAt: string;
}

export interface TaskRoomBridgeStoreSnapshot {
  events: TaskRoomBridgeEvent[];
  updatedAt: string;
}

export interface PublishTaskRoomBridgeInput {
  type: TaskRoomBridgeEventType;
  room: ChatRoom;
  task?: ProjectTask;
  message?: ChatMessage;
  note?: string;
  requestId?: string;
  metadata?: Record<string, unknown>;
}

export interface PublishTaskRoomBridgeOptions {
  enabled?: boolean;
  discordWebhookUrl?: string;
  telegramBotToken?: string;
  telegramChatId?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

export interface PublishTaskRoomBridgeResult {
  path: string;
  event: TaskRoomBridgeEvent;
}

const EMPTY_STORE: TaskRoomBridgeStoreSnapshot = {
  events: [],
  updatedAt: "1970-01-01T00:00:00.000Z",
};

export async function loadTaskRoomBridgeStore(): Promise<TaskRoomBridgeStoreSnapshot> {
  try {
    const raw = await readFile(TASK_ROOM_BRIDGE_EVENTS_PATH, "utf8");
    return normalizeTaskRoomBridgeStore(JSON.parse(raw));
  } catch {
    return cloneEmptyStore();
  }
}

export async function saveTaskRoomBridgeStore(next: TaskRoomBridgeStoreSnapshot): Promise<string> {
  const normalized = normalizeTaskRoomBridgeStore({
    ...next,
    updatedAt: new Date().toISOString(),
  });
  await mkdir(RUNTIME_DIR, { recursive: true });
  await writeFile(TASK_ROOM_BRIDGE_EVENTS_PATH, JSON.stringify(normalized, null, 2), "utf8");
  return TASK_ROOM_BRIDGE_EVENTS_PATH;
}

export function listTaskRoomBridgeEvents(
  store: TaskRoomBridgeStoreSnapshot,
  options?: { roomId?: string; limit?: number },
): TaskRoomBridgeEvent[] {
  const roomId = options?.roomId?.trim();
  const limit = Number.isFinite(options?.limit) ? Math.max(1, Number(options?.limit)) : undefined;
  const filtered = [...store.events]
    .filter((event) => !roomId || event.roomId === roomId)
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  return limit ? filtered.slice(0, limit) : filtered;
}

export async function publishTaskRoomBridgeEvent(
  input: PublishTaskRoomBridgeInput,
  options: PublishTaskRoomBridgeOptions = {},
): Promise<PublishTaskRoomBridgeResult> {
  const store = await loadTaskRoomBridgeStore();
  const event = buildTaskRoomBridgeEvent(input);
  const webhookUrl = options.discordWebhookUrl ?? TASK_ROOM_BRIDGE_DISCORD_WEBHOOK_URL;
  const telegramBotToken = options.telegramBotToken ?? TASK_ROOM_BRIDGE_TELEGRAM_BOT_TOKEN;
  const telegramChatId = options.telegramChatId ?? TASK_ROOM_BRIDGE_TELEGRAM_CHAT_ID;
  const enabled = options.enabled ?? TASK_ROOM_BRIDGE_ENABLED;
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  const timeoutMs = options.timeoutMs ?? 4_000;

  if (!enabled) {
    event.skippedTargets.push("bridge-disabled");
  } else {
    if (typeof fetchImpl !== "function") {
      event.errorTargets.push("fetch-unavailable");
    } else {
      if (!webhookUrl) {
        event.skippedTargets.push("discord-not-configured");
      } else {
        try {
          const response = await fetchImpl(webhookUrl, {
            method: "POST",
            headers: {
              "content-type": "application/json",
            },
            body: JSON.stringify(buildDiscordWebhookPayload(event)),
            signal: AbortSignal.timeout(timeoutMs),
          });
          if (response.ok) {
            event.deliveredTargets.push("discord");
          } else {
            event.errorTargets.push(`discord:${response.status}`);
          }
        } catch (error) {
          event.errorTargets.push(`discord:${error instanceof Error ? error.message : "unknown error"}`);
        }
      }

      if (!telegramBotToken || !telegramChatId) {
        event.skippedTargets.push("telegram-not-configured");
      } else {
        try {
          const response = await fetchImpl(buildTelegramBotApiUrl(telegramBotToken), {
            method: "POST",
            headers: {
              "content-type": "application/json",
            },
            body: JSON.stringify(buildTelegramBotPayload(event, telegramChatId)),
            signal: AbortSignal.timeout(timeoutMs),
          });
          if (response.ok) {
            event.deliveredTargets.push("telegram");
          } else {
            event.errorTargets.push(`telegram:${response.status}`);
          }
        } catch (error) {
          event.errorTargets.push(`telegram:${error instanceof Error ? error.message : "unknown error"}`);
        }
      }
    }
  }

  event.status = resolveBridgeStatus(event);
  store.events.push(event);
  store.updatedAt = event.createdAt;
  const path = await saveTaskRoomBridgeStore(store);
  return { path, event };
}

export function buildTaskRoomBridgeEvent(input: PublishTaskRoomBridgeInput): TaskRoomBridgeEvent {
  const createdAt = new Date().toISOString();
  return {
    eventId: randomUUID(),
    type: input.type,
    status: "local_only",
    roomId: input.room.roomId,
    projectId: input.room.projectId,
    taskId: input.room.taskId,
    roomTitle: input.room.title,
    roomStage: input.room.stage,
    ownerRole: input.room.ownerRole,
    assignedExecutor: input.room.assignedExecutor,
    taskStatus: input.task?.status,
    authorRole: input.message?.authorRole,
    messageId: input.message?.messageId,
    messageKind: input.message?.kind,
    messageSnippet: truncateText(input.message?.content, 280),
    decision: input.room.decision,
    note: input.note,
    requestId: input.requestId,
    roomUrl: buildTaskRoomUrl(input.room.roomId),
    deliveredTargets: [],
    skippedTargets: [],
    errorTargets: [],
    metadata: input.metadata,
    createdAt,
  };
}

export function buildTaskRoomUrl(roomId: string): string | undefined {
  if (!OPENCLAW_CONTROL_UI_URL) return undefined;
  try {
    const url = new URL(OPENCLAW_CONTROL_UI_URL);
    url.searchParams.set("section", "collaboration");
    url.searchParams.set("roomId", roomId);
    return url.toString();
  } catch {
    return undefined;
  }
}

export function buildDiscordWebhookPayload(event: TaskRoomBridgeEvent): {
  content: string;
  allowed_mentions: { parse: [] };
} {
  const lines = [
    `Task room update: ${humanizeBridgeType(event.type)}`,
    `Room: ${event.roomTitle} (${event.roomId})`,
    `Task: ${event.projectId}:${event.taskId}`,
    `Stage: ${event.roomStage} | Owner: ${event.ownerRole}${event.assignedExecutor ? ` | Executor: ${event.assignedExecutor}` : ""}`,
  ];
  if (event.taskStatus) lines.push(`Task status: ${event.taskStatus}`);
  if (event.messageKind || event.messageSnippet) {
    lines.push(`Message: ${event.messageKind ?? "chat"}${event.messageSnippet ? ` — ${event.messageSnippet}` : ""}`);
  }
  if (event.decision) lines.push(`Decision: ${event.decision}`);
  if (event.note) lines.push(`Note: ${event.note}`);
  if (event.roomUrl) lines.push(`Open: ${event.roomUrl}`);
  return {
    content: truncateText(lines.join("\n"), 1_900) ?? "Task room update",
    allowed_mentions: { parse: [] },
  };
}

export function buildTelegramBotApiUrl(botToken: string): string {
  return `https://api.telegram.org/bot${encodeURIComponent(botToken)}/sendMessage`;
}

export function buildTelegramBotPayload(
  event: TaskRoomBridgeEvent,
  chatId: string,
): {
  chat_id: string;
  text: string;
  disable_web_page_preview: boolean;
} {
  const lines = [
    `Task room update: ${humanizeBridgeType(event.type)}`,
    `Room: ${event.roomTitle} (${event.roomId})`,
    `Task: ${event.projectId}:${event.taskId}`,
    `Stage: ${event.roomStage} | Owner: ${event.ownerRole}${event.assignedExecutor ? ` | Executor: ${event.assignedExecutor}` : ""}`,
  ];
  if (event.taskStatus) lines.push(`Task status: ${event.taskStatus}`);
  if (event.messageKind || event.messageSnippet) {
    lines.push(`Message: ${event.messageKind ?? "chat"}${event.messageSnippet ? ` - ${event.messageSnippet}` : ""}`);
  }
  if (event.decision) lines.push(`Decision: ${event.decision}`);
  if (event.note) lines.push(`Note: ${event.note}`);
  if (event.roomUrl) lines.push(`Open: ${event.roomUrl}`);
  return {
    chat_id: chatId,
    text: truncateText(lines.join("\n"), 4_000) ?? "Task room update",
    disable_web_page_preview: true,
  };
}

function normalizeTaskRoomBridgeStore(input: unknown): TaskRoomBridgeStoreSnapshot {
  const root = asObject(input) ?? {};
  return {
    events: asArray(root.events)
      .map((item) => normalizeTaskRoomBridgeEvent(item))
      .filter((item): item is TaskRoomBridgeEvent => Boolean(item))
      .sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt)),
    updatedAt: normalizeIsoString(root.updatedAt) ?? "1970-01-01T00:00:00.000Z",
  };
}

function normalizeTaskRoomBridgeEvent(input: unknown): TaskRoomBridgeEvent | undefined {
  const root = asObject(input);
  if (!root) return undefined;
  const roomId = asNonEmptyString(root.roomId);
  const projectId = asNonEmptyString(root.projectId);
  const taskId = asNonEmptyString(root.taskId);
  const roomTitle = asNonEmptyString(root.roomTitle);
  const roomStage = asRoomStage(root.roomStage);
  const ownerRole = asRoomRole(root.ownerRole);
  const createdAt = normalizeIsoString(root.createdAt);
  const type = asBridgeType(root.type);
  const status = asBridgeStatus(root.status) ?? "local_only";
  if (!roomId || !projectId || !taskId || !roomTitle || !roomStage || !ownerRole || !createdAt || !type) return undefined;
  return {
    eventId: asNonEmptyString(root.eventId) ?? randomUUID(),
    type,
    status,
    roomId,
    projectId,
    taskId,
    roomTitle,
    roomStage,
    ownerRole,
    assignedExecutor: asRoomRole(root.assignedExecutor),
    taskStatus: asTaskState(root.taskStatus),
    authorRole: asRoomRole(root.authorRole),
    messageId: asNonEmptyString(root.messageId),
    messageKind: asMessageKind(root.messageKind),
    messageSnippet: asNonEmptyString(root.messageSnippet),
    decision: asNonEmptyString(root.decision),
    note: asNonEmptyString(root.note),
    requestId: asNonEmptyString(root.requestId),
    roomUrl: asNonEmptyString(root.roomUrl),
    deliveredTargets: asArray(root.deliveredTargets).map((item) => asBridgeTarget(item)).filter(Boolean) as TaskRoomBridgeTarget[],
    skippedTargets: asArray(root.skippedTargets).map((item) => asNonEmptyString(item)).filter(Boolean) as string[],
    errorTargets: asArray(root.errorTargets).map((item) => asNonEmptyString(item)).filter(Boolean) as string[],
    metadata: asObject(root.metadata),
    createdAt,
  };
}

function resolveBridgeStatus(event: Pick<TaskRoomBridgeEvent, "deliveredTargets" | "skippedTargets" | "errorTargets">): TaskRoomBridgeDeliveryStatus {
  if (event.deliveredTargets.length > 0 && event.errorTargets.length > 0) return "partial";
  if (event.deliveredTargets.length > 0) return "delivered";
  if (event.errorTargets.length > 0 && event.skippedTargets.length === 0) return "failed";
  return "local_only";
}

function humanizeBridgeType(type: TaskRoomBridgeEventType): string {
  switch (type) {
    case "room_created":
      return "room created";
    case "message_posted":
      return "message posted";
    case "handoff_recorded":
      return "handoff recorded";
    case "executor_assigned":
      return "executor assigned";
    case "review_submitted":
      return "review submitted";
    case "stage_changed":
      return "stage changed";
    default:
      return type;
  }
}

function truncateText(value: string | undefined, maxLength: number): string | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function cloneEmptyStore(): TaskRoomBridgeStoreSnapshot {
  return {
    events: [],
    updatedAt: EMPTY_STORE.updatedAt,
  };
}

function asObject(input: unknown): Record<string, unknown> | undefined {
  return input !== null && typeof input === "object" ? (input as Record<string, unknown>) : undefined;
}

function asArray(input: unknown): unknown[] {
  return Array.isArray(input) ? input : [];
}

function asNonEmptyString(input: unknown): string | undefined {
  return typeof input === "string" && input.trim() !== "" ? input.trim() : undefined;
}

function normalizeIsoString(input: unknown): string | undefined {
  const value = asNonEmptyString(input);
  if (!value) return undefined;
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return undefined;
  return new Date(timestamp).toISOString();
}

function asBridgeType(input: unknown): TaskRoomBridgeEventType | undefined {
  switch (input) {
    case "room_created":
    case "message_posted":
    case "handoff_recorded":
    case "executor_assigned":
    case "review_submitted":
    case "stage_changed":
      return input;
    default:
      return undefined;
  }
}

function asBridgeStatus(input: unknown): TaskRoomBridgeDeliveryStatus | undefined {
  switch (input) {
    case "delivered":
    case "partial":
    case "local_only":
    case "failed":
      return input;
    default:
      return undefined;
  }
}

function asBridgeTarget(input: unknown): TaskRoomBridgeTarget | undefined {
  switch (input) {
    case "discord":
    case "telegram":
      return input;
    default:
      return undefined;
  }
}

function asRoomStage(input: unknown): RoomStage | undefined {
  switch (input) {
    case "intake":
    case "discussion":
    case "assigned":
    case "executing":
    case "review":
    case "completed":
      return input;
    default:
      return undefined;
  }
}

function asRoomRole(input: unknown): RoomParticipantRole | undefined {
  switch (input) {
    case "human":
    case "planner":
    case "coder":
    case "reviewer":
    case "manager":
      return input;
    default:
      return undefined;
  }
}

function asTaskState(input: unknown): TaskState | undefined {
  switch (input) {
    case "todo":
    case "in_progress":
    case "blocked":
    case "done":
      return input;
    default:
      return undefined;
  }
}

function asMessageKind(input: unknown): MessageKind | undefined {
  switch (input) {
    case "chat":
    case "proposal":
    case "decision":
    case "handoff":
    case "status":
    case "result":
      return input;
    default:
      return undefined;
  }
}
