import type { ChatMessage, RoomParticipantRole } from "../types";
import type { CreateChatMessageInput } from "./chat-store";
import type { ProjectTask } from "../types";

interface AgentDispatchContext {
  roomId: string;
  task: ProjectTask;
  recentMessages: ChatMessage[];
}

export function buildDiscussionDispatchMessage(
  role: RoomParticipantRole,
  input: AgentDispatchContext,
): CreateChatMessageInput {
  if (role === "planner") return buildPlannerMessage(input);
  if (role === "coder") return buildCoderMessage(input);
  if (role === "reviewer") return buildReviewerMessage(input);
  return buildManagerMessage(input);
}

export function buildExecutionStartedMessage(
  roomId: string,
  executor: RoomParticipantRole,
  task: ProjectTask,
): CreateChatMessageInput {
  return {
    roomId,
    kind: "status",
    authorRole: executor,
    authorLabel: titleCaseRole(executor),
    content: `${titleCaseRole(executor)} accepted "${task.title}" and started execution.`,
    payload: {
      status: "execution_started",
      executor,
      taskStatus: "in_progress",
    },
  };
}

export function buildReviewOutcomeMessage(input: {
  roomId: string;
  outcome: "approved" | "rejected";
  note?: string;
  taskStatus: "done" | "blocked" | "in_progress";
}): CreateChatMessageInput {
  const base =
    input.outcome === "approved"
      ? "Reviewer approved the execution result."
      : "Reviewer rejected the execution result and requested another pass.";
  return {
    roomId: input.roomId,
    kind: "result",
    authorRole: "reviewer",
    authorLabel: "Reviewer",
    content: input.note ? `${base} ${input.note}` : base,
    payload: {
      reviewOutcome: input.outcome,
      taskStatus: input.taskStatus,
      status: input.outcome === "approved" ? "review_passed" : "review_rejected",
    },
  };
}

function buildPlannerMessage(input: AgentDispatchContext): CreateChatMessageInput {
  const latestHumanPrompt = latestHumanRequest(input.recentMessages);
  const proposal = [
    `Scope the request for "${input.task.title}".`,
    latestHumanPrompt ? `Anchor the work on: ${latestHumanPrompt}.` : "Use the latest operator request as the main requirement.",
    "Implement the smallest safe slice first, then verify with concrete evidence.",
  ].join(" ");

  return {
    roomId: input.roomId,
    kind: "proposal",
    authorRole: "planner",
    authorLabel: "Planner",
    content: proposal,
    payload: {
      proposal,
    },
  };
}

function buildCoderMessage(input: AgentDispatchContext): CreateChatMessageInput {
  const plan = [
    `Implementation path for "${input.task.title}":`,
    "wire the room/task state first,",
    "keep mutations traceable,",
    "and finish with tests that prove the happy path and review flow.",
  ].join(" ");

  return {
    roomId: input.roomId,
    kind: "proposal",
    authorRole: "coder",
    authorLabel: "Coder",
    content: plan,
    payload: {
      proposal: plan,
    },
  };
}

function buildReviewerMessage(input: AgentDispatchContext): CreateChatMessageInput {
  const checklist = [
    `Review focus for "${input.task.title}":`,
    "one room per task,",
    "ordered discussion turns,",
    "task-state sync,",
    "summary persistence,",
    "and regression coverage for the main API flow.",
  ].join(" ");

  return {
    roomId: input.roomId,
    kind: "proposal",
    authorRole: "reviewer",
    authorLabel: "Reviewer",
    content: checklist,
    payload: {
      proposal: checklist,
    },
  };
}

function buildManagerMessage(input: AgentDispatchContext): CreateChatMessageInput {
  const executor: RoomParticipantRole = "coder";
  const doneWhen = resolveDoneWhen(input.task);
  const decision = `Use the room-first implementation plan for "${input.task.title}" and move execution to ${titleCaseRole(executor)}.`;
  const proposal = `Planner, coder, and reviewer aligned on a safe incremental build for "${input.task.title}".`;

  return {
    roomId: input.roomId,
    kind: "decision",
    authorRole: "manager",
    authorLabel: "Manager",
    content: `${decision} Done when: ${doneWhen}.`,
    payload: {
      proposal,
      decision,
      executor,
      doneWhen,
    },
  };
}

function latestHumanRequest(messages: ChatMessage[]): string | undefined {
  const human = [...messages].reverse().find((message) => message.authorRole === "human");
  if (!human) return undefined;
  const trimmed = human.content.trim().replace(/\s+/g, " ");
  if (trimmed.length <= 160) return trimmed;
  return `${trimmed.slice(0, 157)}...`;
}

function resolveDoneWhen(task: ProjectTask): string {
  if (task.definitionOfDone.length > 0) {
    return task.definitionOfDone.join("; ");
  }
  if (task.dueAt) {
    return `the requested changes are implemented and reviewed before ${task.dueAt}`;
  }
  return "the main flow works, the result is reviewed, and the task state is updated";
}

function titleCaseRole(role: RoomParticipantRole): string {
  if (role === "human") return "Operator";
  if (role === "planner") return "Planner";
  if (role === "coder") return "Coder";
  if (role === "reviewer") return "Reviewer";
  return "Manager";
}
