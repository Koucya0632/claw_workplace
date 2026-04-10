import assert from "node:assert/strict";
import test from "node:test";
import { resolveHallParticipantsFromRoster } from "../src/runtime/hall-role-resolver";

test("hall role resolver prefers generic role signals and does not hard-code project agent names", () => {
  const participants = resolveHallParticipantsFromRoster([
    { agentId: "main", displayName: "Main coordinator" },
    { agentId: "builder-bot", displayName: "Builder Bot" },
    { agentId: "research-bot", displayName: "Research Planner" },
    { agentId: "qa-bot", displayName: "QA Bot" },
    { agentId: "pandas", displayName: "Pandas" },
  ]);

  const builder = participants.find((participant) => participant.agentId === "builder-bot");
  const research = participants.find((participant) => participant.agentId === "research-bot");
  const qa = participants.find((participant) => participant.agentId === "qa-bot");
  const pandas = participants.find((participant) => participant.agentId === "pandas");

  assert.equal(builder?.semanticRole, "coder");
  assert.equal(research?.semanticRole, "planner");
  assert.equal(qa?.semanticRole, "reviewer");
  assert.equal(pandas?.semanticRole, "generalist");
});
