import type { StructuredHandoffPacket, TaskArtifact } from "../types";

export type HallHandoffSummaryLanguage = "en" | "zh";

export class HallHandoffValidationError extends Error {
  readonly issues: string[];
  readonly statusCode: number;

  constructor(message: string, issues: string[] = [], statusCode = 400) {
    super(message);
    this.name = "HallHandoffValidationError";
    this.issues = issues;
    this.statusCode = statusCode;
  }
}

export interface CreateStructuredHandoffInput {
  goal: string;
  currentResult: string;
  doneWhen: string;
  blockers?: string[];
  nextOwner: string;
  requiresInputFrom?: string[];
  artifactRefs?: TaskArtifact[];
}

export function buildStructuredHandoffPacket(input: CreateStructuredHandoffInput): StructuredHandoffPacket {
  const issues: string[] = [];
  const goal = requireText(input.goal, "goal", 240, issues);
  const currentResult = requireText(input.currentResult, "currentResult", 500, issues);
  const doneWhen = requireText(input.doneWhen, "doneWhen", 240, issues);
  const nextOwner = requireText(input.nextOwner, "nextOwner", 120, issues);
  const blockers = normalizeStringArray(input.blockers, "blockers", 240, issues);
  const requiresInputFrom = normalizeStringArray(input.requiresInputFrom, "requiresInputFrom", 120, issues);
  const artifactRefs = normalizeArtifactRefs(input.artifactRefs, "artifactRefs", issues);

  if (issues.length > 0) {
    throw new HallHandoffValidationError("Invalid structured handoff payload.", issues);
  }

  return {
    goal,
    currentResult,
    doneWhen,
    blockers,
    nextOwner,
    requiresInputFrom,
    artifactRefs,
  };
}

export function summarizeStructuredHandoff(
  packet: StructuredHandoffPacket,
  options: { language?: HallHandoffSummaryLanguage; includeMention?: boolean } = {},
): string {
  const language = options.language ?? "en";
  const nextOwner = options.includeMention === false ? packet.nextOwner : `@${packet.nextOwner}`;
  const shortResult = shortenHandoffCopy(packet.currentResult, language === "zh" ? 54 : 120);

  if (language === "zh") {
    const blockers = packet.blockers.length > 0 ? ` 卡点：${packet.blockers.join("；")}。` : "";
    const requires = packet.requiresInputFrom.length > 0
      ? ` 还需要 ${packet.requiresInputFrom.join("、")} 配合。`
      : "";
    const artifacts = packet.artifactRefs && packet.artifactRefs.length > 0
      ? ` 先看产物：${packet.artifactRefs.map((artifact) => artifact.label).join("、")}。`
      : "";
    return `${nextOwner} 接棒：先做“${packet.goal}”。现在手里有：${shortResult}。做到“${packet.doneWhen}”后继续往下交。${artifacts}${blockers}${requires}`;
  }

  const blockers = packet.blockers.length > 0 ? ` Blockers: ${packet.blockers.join("; ")}.` : "";
  const requires = packet.requiresInputFrom.length > 0
    ? ` Needs input from: ${packet.requiresInputFrom.join(", ")}.`
    : "";
  const artifacts = packet.artifactRefs && packet.artifactRefs.length > 0
    ? ` Start from these artifacts: ${packet.artifactRefs.map((artifact) => artifact.label).join(", ")}.`
    : "";
  return `${nextOwner} takes this next: ${packet.goal}. Current result: ${shortResult}. Done when ${packet.doneWhen}.${artifacts}${blockers}${requires}`;
}

function shortenHandoffCopy(value: string, maxLength: number): string {
  const trimmed = value.replace(/\s+/g, " ").trim();
  if (!trimmed) return "";
  return trimmed.length > maxLength ? `${trimmed.slice(0, Math.max(0, maxLength - 1)).trim()}…` : trimmed;
}

function requireText(value: string, field: string, maxLength: number, issues: string[]): string {
  const trimmed = typeof value === "string" ? value.trim() : "";
  if (!trimmed) {
    issues.push(field);
    return "";
  }
  return trimmed.length > maxLength ? `${trimmed.slice(0, maxLength - 3)}...` : trimmed;
}

function normalizeStringArray(value: string[] | undefined, field: string, maxLength: number, issues: string[]): string[] {
  if (value === undefined) return [];
  if (!Array.isArray(value)) {
    issues.push(field);
    return [];
  }
  return [...new Set(
    value
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .map((item) => (item.length > maxLength ? `${item.slice(0, maxLength - 3)}...` : item)),
  )];
}

function normalizeArtifactRefs(value: TaskArtifact[] | undefined, field: string, issues: string[]): TaskArtifact[] | undefined {
  if (value === undefined) return undefined;
  if (!Array.isArray(value)) {
    issues.push(field);
    return undefined;
  }
  const refs: TaskArtifact[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") {
      issues.push(field);
      continue;
    }
    const artifactId = requireText(item.artifactId, `${field}.artifactId`, 120, issues);
    const label = requireText(item.label, `${field}.label`, 180, issues);
    const location = requireText(item.location, `${field}.location`, 400, issues);
    const type = item.type === "code" || item.type === "doc" || item.type === "link" || item.type === "other"
      ? item.type
      : undefined;
    if (!type) {
      issues.push(`${field}.type`);
      continue;
    }
    refs.push({ artifactId, type, label, location });
  }
  return refs;
}
