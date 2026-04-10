import type { AgentRosterEntry } from "./agent-roster";
import type { HallParticipant, HallSemanticRole } from "../types";

const ROLE_PATTERNS: Record<Exclude<HallSemanticRole, "generalist">, RegExp[]> = {
  manager: [/manager/i, /\bmain\b/i, /lead/i, /chief/i, /owner/i, /orchestr/i],
  planner: [/planner/i, /plan/i, /research/i, /architect/i, /product/i, /design/i],
  coder: [/coder/i, /code/i, /dev/i, /engineer/i, /implement/i, /build/i, /builder/i, /maker/i],
  reviewer: [/review/i, /qa/i, /audit/i, /critic/i, /test/i, /verify/i],
};

export function resolveHallParticipantsFromRoster(roster: AgentRosterEntry[]): HallParticipant[] {
  const ordered = [...roster]
    .map((entry) => ({
      agentId: entry.agentId.trim(),
      displayName: entry.displayName.trim() || entry.agentId.trim(),
    }))
    .filter((entry) => entry.agentId.length > 0)
    .sort((a, b) => a.agentId.localeCompare(b.agentId));

  if (ordered.length === 0) {
    return [
      toParticipant("main", "Main", "manager"),
      toParticipant("planner", "Planner", "planner"),
      toParticipant("coder", "Coder", "coder"),
      toParticipant("reviewer", "Reviewer", "reviewer"),
    ];
  }

  const assigned = new Set<string>();
  const participants: HallParticipant[] = [];

  const pushRole = (role: Exclude<HallSemanticRole, "generalist">) => {
    const candidate = pickBestRoleCandidate(ordered, role, assigned);
    if (!candidate) return;
    assigned.add(candidate.agentId);
    participants.push(toParticipant(candidate.agentId, candidate.displayName, role));
  };

  pushRole("manager");
  pushRole("planner");
  pushRole("coder");
  pushRole("reviewer");

  for (const entry of ordered) {
    if (assigned.has(entry.agentId)) continue;
    participants.push(toParticipant(entry.agentId, entry.displayName, "generalist"));
  }

  return participants;
}

export function pickPrimaryParticipantByRole(
  participants: HallParticipant[],
  role: Exclude<HallSemanticRole, "generalist">,
): HallParticipant | undefined {
  const direct = participants.find((participant) => participant.active && participant.semanticRole === role);
  if (direct) return direct;
  if (role === "manager") return participants.find((participant) => participant.active);
  if (role === "planner") {
    return participants.find((participant) => participant.active && participant.semanticRole !== "manager");
  }
  return participants.find((participant) => participant.active && participant.semanticRole === "generalist");
}

export function resolveSemanticRoleLabel(role: HallSemanticRole, language: "en" | "zh" = "en"): string {
  if (language === "zh") {
    if (role === "planner") return "策划";
    if (role === "coder") return "执行";
    if (role === "reviewer") return "审核";
    if (role === "manager") return "经理";
    return "通用";
  }
  if (role === "planner") return "Planner";
  if (role === "coder") return "Coder";
  if (role === "reviewer") return "Reviewer";
  if (role === "manager") return "Manager";
  return "Generalist";
}

function pickBestRoleCandidate(
  entries: Array<{ agentId: string; displayName: string }>,
  role: Exclude<HallSemanticRole, "generalist">,
  assigned: Set<string>,
): { agentId: string; displayName: string } | undefined {
  const patterns = ROLE_PATTERNS[role];
  const fromPattern = entries.find((entry) => !assigned.has(entry.agentId) && matchesRole(entry, patterns));
  if (fromPattern) return fromPattern;
  return entries.find((entry) => !assigned.has(entry.agentId));
}

function matchesRole(
  entry: { agentId: string; displayName: string },
  patterns: RegExp[],
): boolean {
  const haystack = `${entry.agentId} ${entry.displayName}`;
  return patterns.some((pattern) => pattern.test(haystack));
}

function toParticipant(agentId: string, displayName: string, semanticRole: HallSemanticRole): HallParticipant {
  const aliases = [...new Set([displayName, agentId, displayName.replace(/\s+/g, ""), agentId.replace(/\s+/g, "")])]
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return {
    participantId: agentId,
    agentId,
    displayName,
    semanticRole,
    active: true,
    aliases,
  };
}
