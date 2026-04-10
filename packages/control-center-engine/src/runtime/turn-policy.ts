import type { ChatMessage, ChatRoom, RoomParticipantRole } from "../types";

export const DISCUSSION_SEQUENCE: RoomParticipantRole[] = ["planner", "coder", "reviewer", "manager"];

export function nextDiscussionRole(
  room: ChatRoom,
  messages: ChatMessage[],
): RoomParticipantRole | undefined {
  if (room.stage !== "discussion") return undefined;
  const lastHumanIndex = findLastHumanMessageIndex(messages);
  const roundMessages = lastHumanIndex >= 0 ? messages.slice(lastHumanIndex + 1) : messages;
  const responded = new Set(
    roundMessages
      .map((message) => message.authorRole)
      .filter((role): role is RoomParticipantRole => DISCUSSION_SEQUENCE.includes(role)),
  );
  return DISCUSSION_SEQUENCE.find((role) => !responded.has(role));
}

export function isDiscussionRoundComplete(room: ChatRoom, messages: ChatMessage[]): boolean {
  return room.stage === "discussion" && nextDiscussionRole(room, messages) === undefined;
}

export function roleCanSpeak(
  room: ChatRoom,
  messages: ChatMessage[],
  role: RoomParticipantRole,
  mentions: RoomParticipantRole[] = [],
): boolean {
  if (role === "human") return true;

  if (room.stage === "intake") {
    return role === "planner";
  }

  if (room.stage === "discussion") {
    return nextDiscussionRole(room, messages) === role;
  }

  if (room.stage === "assigned" || room.stage === "executing") {
    if (room.assignedExecutor && role === room.assignedExecutor) return true;
    return mentions.includes(role);
  }

  if (room.stage === "review") {
    return role === "reviewer" || role === "manager" || mentions.includes(role);
  }

  if (room.stage === "completed") {
    return role === "manager" || mentions.includes(role);
  }

  return false;
}

export function findLastHumanMessageIndex(messages: ChatMessage[]): number {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    if (messages[idx].authorRole === "human") return idx;
  }
  return -1;
}
