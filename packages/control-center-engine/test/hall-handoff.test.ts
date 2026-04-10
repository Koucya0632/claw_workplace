import assert from "node:assert/strict";
import test from "node:test";
import { buildStructuredHandoffPacket, summarizeStructuredHandoff } from "../src/runtime/hall-handoff";

test("structured handoff packet preserves key fields", () => {
  const packet = buildStructuredHandoffPacket({
    goal: "Finish the hall UI",
    currentResult: "Task cards and timeline are already wired",
    doneWhen: "Hall page renders and polls correctly",
    blockers: ["Need evidence panel"],
    nextOwner: "Pandas",
    requiresInputFrom: ["Main"],
  });
  assert.equal(packet.goal, "Finish the hall UI");
  assert.equal(packet.blockers.length, 1);
  assert.match(summarizeStructuredHandoff(packet), /@Pandas takes this next/);
  assert.match(summarizeStructuredHandoff(packet), /Needs input from: Main/);
});
