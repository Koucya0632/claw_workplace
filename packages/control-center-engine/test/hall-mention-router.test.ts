import assert from "node:assert/strict";
import test from "node:test";
import { resolveHallMentionTargets } from "../src/runtime/hall-mention-router";
import type { HallParticipant } from "../src/types";

const participants: HallParticipant[] = [
  {
    participantId: "main",
    agentId: "main",
    displayName: "Main",
    semanticRole: "manager",
    active: true,
    aliases: ["Main", "main"],
  },
  {
    participantId: "pandas",
    agentId: "pandas",
    displayName: "Pandas",
    semanticRole: "coder",
    active: true,
    aliases: ["Pandas", "pandas"],
  },
];

test("hall mention router resolves one exact participant", () => {
  const result = resolveHallMentionTargets("Please review this, @Pandas", participants);
  assert.equal(result.broadcastAll, false);
  assert.equal(result.targets.length, 1);
  assert.equal(result.targets[0].participantId, "pandas");
});

test("hall mention router recognizes @all", () => {
  const result = resolveHallMentionTargets("Heads up, @all", participants);
  assert.equal(result.broadcastAll, true);
});
