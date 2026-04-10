import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type {
  ChatMessage,
  ChatRoom,
  ChatRoomSummary,
  ChatSummaryStoreSnapshot,
  RoomParticipantRole,
  RoomStage,
} from "../types";

const RUNTIME_DIR = join(process.cwd(), "runtime");
export const CHAT_SUMMARIES_PATH = join(RUNTIME_DIR, "chat-summaries.json");

const EMPTY_SUMMARY_STORE: ChatSummaryStoreSnapshot = {
  summaries: [],
  updatedAt: "1970-01-01T00:00:00.000Z",
};

export interface ChatSummaryMutationResult {
  path: string;
  summary: ChatRoomSummary;
}

export async function loadChatSummaryStore(): Promise<ChatSummaryStoreSnapshot> {
  try {
    const raw = await readFile(CHAT_SUMMARIES_PATH, "utf8");
    return normalizeChatSummaryStore(JSON.parse(raw));
  } catch {
    return cloneEmptySummaryStore();
  }
}

export async function saveChatSummaryStore(next: ChatSummaryStoreSnapshot): Promise<string> {
  const normalized = normalizeChatSummaryStore({
    ...next,
    updatedAt: new Date().toISOString(),
  });
  await mkdir(RUNTIME_DIR, { recursive: true });
  await writeFile(CHAT_SUMMARIES_PATH, JSON.stringify(normalized, null, 2), "utf8");
  return CHAT_SUMMARIES_PATH;
}

export function getChatRoomSummary(
  store: ChatSummaryStoreSnapshot,
  roomId: string,
): ChatRoomSummary | undefined {
  return store.summaries.find((summary) => summary.roomId === roomId.trim());
}

export function listChatRoomSummaries(store: ChatSummaryStoreSnapshot): ChatRoomSummary[] {
  return [...store.summaries].sort((a, b) => toSortableMs(b.updatedAt) - toSortableMs(a.updatedAt));
}

export async function upsertChatRoomSummary(
  room: ChatRoom,
  messages: ChatMessage[],
): Promise<ChatSummaryMutationResult> {
  const store = await loadChatSummaryStore();
  const summary = buildChatRoomSummary(room, messages);
  const existingIndex = store.summaries.findIndex((item) => item.roomId === room.roomId);
  if (existingIndex >= 0) {
    store.summaries[existingIndex] = summary;
  } else {
    store.summaries.push(summary);
  }
  store.updatedAt = summary.updatedAt;
  const path = await saveChatSummaryStore(store);
  return { path, summary };
}

export function buildChatRoomSummary(room: ChatRoom, messages: ChatMessage[]): ChatRoomSummary {
  const ordered = [...messages].sort((a, b) => toSortableMs(a.createdAt) - toSortableMs(b.createdAt));
  const lastDecisionMessage = [...ordered]
    .reverse()
    .find((message) => message.kind === "decision" || message.payload?.decision);
  const lastProposalMessage = [...ordered]
    .reverse()
    .find((message) => message.kind === "proposal" || message.payload?.proposal);
  const latestHumanMessage = [...ordered].reverse().find((message) => message.authorRole === "human");
  const latestQuestion = extractQuestion(latestHumanMessage?.content ?? "");
  const openQuestions = latestQuestion ? [latestQuestion] : [];
  const headline = resolveHeadline(room, lastDecisionMessage, lastProposalMessage);
  const latestDecision = lastDecisionMessage?.payload?.decision ?? room.decision;
  const currentOwner = resolveCurrentOwner(room.stage, room.ownerRole, room.assignedExecutor);

  return {
    roomId: room.roomId,
    headline,
    latestDecision,
    currentOwner,
    nextAction: buildNextAction(room.stage, room.assignedExecutor, latestDecision),
    openQuestions,
    messageCount: ordered.length,
    updatedAt: room.updatedAt,
  };
}

function resolveHeadline(
  room: ChatRoom,
  lastDecisionMessage: ChatMessage | undefined,
  lastProposalMessage: ChatMessage | undefined,
): string {
  const decision = lastDecisionMessage?.payload?.decision ?? room.decision;
  if (decision) return decision;
  const proposal = lastProposalMessage?.payload?.proposal ?? room.proposal;
  if (proposal) return proposal;
  return room.title;
}

function resolveCurrentOwner(
  stage: RoomStage,
  ownerRole: RoomParticipantRole,
  assignedExecutor?: RoomParticipantRole,
): RoomParticipantRole {
  if ((stage === "assigned" || stage === "executing") && assignedExecutor) return assignedExecutor;
  return ownerRole;
}

function buildNextAction(
  stage: RoomStage,
  assignedExecutor: RoomParticipantRole | undefined,
  latestDecision: string | undefined,
): string {
  if (stage === "intake") return "Collect the first human request and begin discussion.";
  if (stage === "discussion") return "Finish planner/coder/reviewer discussion and capture a manager decision.";
  if (stage === "assigned") {
    return assignedExecutor
      ? `${titleCaseRole(assignedExecutor)} should acknowledge the handoff and start execution.`
      : "Confirm the executor and acknowledge the handoff.";
  }
  if (stage === "executing") return "Keep posting execution status until the task is ready for review.";
  if (stage === "review") return "Approve or reject the execution result and sync the task state.";
  return latestDecision ? `Completed: ${latestDecision}` : "Completed and waiting for follow-up.";
}

function extractQuestion(content: string): string | undefined {
  const trimmed = content.trim();
  if (!trimmed) return undefined;
  const match = trimmed.match(/([^?？]+\?|[^?？]+？)$/u);
  if (!match) return undefined;
  const question = match[1].trim();
  return question.length > 220 ? `${question.slice(0, 217)}...` : question;
}

function titleCaseRole(role: RoomParticipantRole): string {
  if (role === "human") return "Operator";
  if (role === "planner") return "Planner";
  if (role === "coder") return "Coder";
  if (role === "reviewer") return "Reviewer";
  return "Manager";
}

function normalizeChatSummaryStore(input: unknown): ChatSummaryStoreSnapshot {
  const obj = asObject(input);
  if (!obj) return cloneEmptySummaryStore();

  return {
    summaries: normalizeSummaries(asArray(obj.summaries)),
    updatedAt: asIsoString(obj.updatedAt),
  };
}

function normalizeSummaries(summaries: unknown[] | undefined): ChatRoomSummary[] {
  if (!summaries) return [];
  return summaries
    .map((summary) => normalizeSummary(summary))
    .filter((summary): summary is ChatRoomSummary => Boolean(summary))
    .sort((a, b) => toSortableMs(b.updatedAt) - toSortableMs(a.updatedAt));
}

function normalizeSummary(input: unknown): ChatRoomSummary | null {
  const obj = asObject(input);
  if (!obj) return null;
  const roomId = asString(obj.roomId)?.trim();
  const headline = asString(obj.headline)?.trim();
  if (!roomId || !headline) return null;

  return {
    roomId,
    headline,
    latestDecision: asString(obj.latestDecision)?.trim() || undefined,
    currentOwner: normalizeOptionalRole(asString(obj.currentOwner)),
    nextAction: asString(obj.nextAction)?.trim() || "Open the room and review the latest state.",
    openQuestions: toStringArray(obj.openQuestions, 220),
    messageCount: asFiniteNumber(obj.messageCount) ?? 0,
    updatedAt: asIsoString(obj.updatedAt),
  };
}

function cloneEmptySummaryStore(): ChatSummaryStoreSnapshot {
  return {
    summaries: [],
    updatedAt: EMPTY_SUMMARY_STORE.updatedAt,
  };
}

function normalizeOptionalRole(value: string | undefined): RoomParticipantRole | undefined {
  if (value === "human" || value === "planner" || value === "coder" || value === "reviewer" || value === "manager") {
    return value;
  }
  return undefined;
}

function toStringArray(value: unknown, maxLength: number): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(
    value
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .map((item) => (item.length > maxLength ? `${item.slice(0, maxLength - 3)}...` : item)),
  )];
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

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asIsoString(value: unknown): string {
  if (typeof value === "string" && !Number.isNaN(Date.parse(value))) {
    return new Date(value).toISOString();
  }
  return new Date().toISOString();
}

function toSortableMs(value: string | undefined): number {
  const parsed = value ? Date.parse(value) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : 0;
}
