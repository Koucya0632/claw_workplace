import { randomUUID } from "node:crypto";
import { pickPrimaryParticipantByRole } from "./hall-role-resolver";
import type { HallParticipant, HallTaskCard, HallTaskStage, TaskDiscussionCycle } from "../types";

const DISCUSSION_ROLE_ORDER = ["planner", "coder", "reviewer", "manager"] as const;

export function buildDiscussionParticipantQueue(participants: HallParticipant[]): string[] {
  const queue: string[] = [];
  for (const role of DISCUSSION_ROLE_ORDER) {
    const participant = pickPrimaryParticipantByRole(participants, role);
    if (participant && !queue.includes(participant.participantId)) {
      queue.push(participant.participantId);
    }
  }
  return queue;
}

export function openDiscussionCycle(
  taskCard: HallTaskCard,
  openedByParticipantId: string,
  participants: HallParticipant[],
  expectedParticipantIds?: string[],
  openedAt = new Date().toISOString(),
): HallTaskCard {
  const cycle: TaskDiscussionCycle = {
    cycleId: randomUUID(),
    openedAt,
    openedByParticipantId,
    expectedParticipantIds: expectedParticipantIds && expectedParticipantIds.length > 0
      ? expectedParticipantIds
      : buildDiscussionParticipantQueue(participants),
    completedParticipantIds: [],
  };
  return {
    ...taskCard,
    stage: "discussion",
    discussionCycle: cycle,
    updatedAt: openedAt,
  };
}

export function markDiscussionSpeakerComplete(taskCard: HallTaskCard, participantId: string, at = new Date().toISOString()): HallTaskCard {
  const cycle = taskCard.discussionCycle;
  if (!cycle) return taskCard;
  if (cycle.completedParticipantIds.includes(participantId)) return taskCard;
  return {
    ...taskCard,
    discussionCycle: {
      ...cycle,
      completedParticipantIds: [...cycle.completedParticipantIds, participantId],
    },
    updatedAt: at,
  };
}

export function closeDiscussionCycle(taskCard: HallTaskCard, at = new Date().toISOString()): HallTaskCard {
  const cycle = taskCard.discussionCycle;
  if (!cycle) return taskCard;
  return {
    ...taskCard,
    discussionCycle: {
      ...cycle,
      closedAt: at,
    },
    updatedAt: at,
  };
}

export function resolveNextDiscussionSpeaker(taskCard: HallTaskCard): string | undefined {
  const cycle = taskCard.discussionCycle;
  if (!cycle || cycle.closedAt) return undefined;
  return cycle.expectedParticipantIds.find((participantId) => !cycle.completedParticipantIds.includes(participantId));
}

export function resolveDefaultSpeakerForStage(
  taskCard: HallTaskCard | undefined,
  participants: HallParticipant[],
): string | undefined {
  if (!taskCard) {
    return pickPrimaryParticipantByRole(participants, "planner")?.participantId ?? participants[0]?.participantId;
  }
  if (taskCard.stage === "discussion") {
    return resolveNextDiscussionSpeaker(taskCard) ?? pickPrimaryParticipantByRole(participants, "manager")?.participantId;
  }
  if (taskCard.stage === "execution") {
    return taskCard.currentOwnerParticipantId;
  }
  if (taskCard.stage === "review") {
    return pickPrimaryParticipantByRole(participants, "reviewer")?.participantId
      ?? pickPrimaryParticipantByRole(participants, "manager")?.participantId;
  }
  if (taskCard.stage === "blocked") {
    return pickPrimaryParticipantByRole(participants, "manager")?.participantId;
  }
  return taskCard.currentOwnerParticipantId ?? pickPrimaryParticipantByRole(participants, "manager")?.participantId;
}

export function coerceTaskStage(taskCard: HallTaskCard, nextStage: HallTaskStage, updatedAt = new Date().toISOString()): HallTaskCard {
  return {
    ...taskCard,
    stage: nextStage,
    updatedAt,
  };
}
