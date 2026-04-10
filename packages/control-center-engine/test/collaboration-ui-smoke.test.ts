import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { renderTaskRoomClientScript, renderTaskRoomWorkbenchForSmoke } from "../src/ui/task-room-workbench";

test("task room workbench renders the three-pane collaboration UI shell", () => {
  const html = renderTaskRoomWorkbenchForSmoke("en");
  assert(html.includes('id="task-room-hub"'));
  assert(html.includes("Task room workbench"));
  assert(html.includes('data-task-room-root'));
  assert(html.includes('data-task-room-list'));
  assert(html.includes('data-task-room-thread'));
  assert(html.includes('data-task-room-detail'));
  assert(html.includes('data-task-room-compose'));
  assert(html.includes('data-task-room-assign'));
  assert(html.includes('data-task-room-approve'));
  assert(html.includes('data-task-room-reject'));
  assert(html.includes("Runtime evidence is merged into this timeline"));
  const script = renderTaskRoomClientScript("en");
  assert(script.includes("new EventSource('/api/rooms/"));
  assert(script.includes("draft_start"));
  assert(script.includes("draft_delta"));
  assert(script.includes("const shouldRetryLocalToken = (response, data) => {"));
  assert(script.includes("response.status !== 403"));
  assert(script.includes("/invalid local token/i.test(extractErrorMessage(data))"));
});

test("collaboration page source keeps the legacy collaboration board and linked task-room threads", async () => {
  const source = await readFile("src/ui/server.ts", "utf8");
  assert(source.includes('const collaborationSection = activeSection === "collaboration" ? `'));
  assert(source.includes("Collaboration threads"));
  assert(source.includes("${collaborationThreadHtml}"));
  assert(source.includes("taskRoomWorkbench"));
  assert(source.includes("renderTaskRoomWorkbench({"));
  assert(source.includes("renderTaskRoomClientScript(options.language)"));
  assert(source.includes('const taskRoomWorkbench = needsTaskRoomWorkbench'));
  assert(source.includes("${taskRoomWorkbenchScript}"));
  assert(source.includes('if (options.section === "collaboration") sectionBody = collaborationSection;'));
});
