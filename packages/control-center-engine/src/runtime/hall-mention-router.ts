import type { HallParticipant, MentionTarget } from "../types";

export interface HallMentionRoutingResult {
  broadcastAll: boolean;
  targets: MentionTarget[];
}

export function resolveHallMentionTargets(
  content: string,
  participants: HallParticipant[],
): HallMentionRoutingResult {
  const trimmed = content.trim();
  if (!trimmed) {
    return { broadcastAll: false, targets: [] };
  }

  const broadcastAll = /(^|[\s(])@all(?=$|[\s),.!?;:])/i.test(trimmed);
  const matched = new Map<string, MentionTarget>();

  for (const participant of participants) {
    for (const alias of participant.aliases) {
      if (!alias) continue;
      if (!containsExplicitMention(trimmed, alias)) continue;
      matched.set(participant.participantId, {
        raw: `@${alias}`,
        participantId: participant.participantId,
        displayName: participant.displayName,
        semanticRole: participant.semanticRole,
      });
      break;
    }
  }

  return {
    broadcastAll,
    targets: [...matched.values()],
  };
}

function containsExplicitMention(content: string, alias: string): boolean {
  const escaped = escapeRegex(alias);
  const pattern = new RegExp(`(^|[\\s(])@${escaped}(?=$|[\\s),.!?;:])`, "i");
  return pattern.test(content);
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
