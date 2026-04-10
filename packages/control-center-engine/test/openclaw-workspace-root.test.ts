import assert from "node:assert/strict";
import test from "node:test";
import {
  resolveOpenClawAgentWorkspaceRoot,
  resolveOpenClawWorkspaceRoot,
} from "../src/runtime/openclaw-workspace-root";

test("workspace root follows explicit override, then config inference, then OPENCLAW_HOME fallback", () => {
  assert.equal(
    resolveOpenClawWorkspaceRoot({
      explicitWorkspaceRoot: "/srv/openclaw/workspace",
      openclawHomeDir: "/tmp/openclaw-home/.openclaw",
      configPath: "/tmp/openclaw-home/.openclaw/openclaw.json",
    }),
    "/srv/openclaw/workspace",
  );

  assert.equal(
    resolveOpenClawWorkspaceRoot({
      openclawHomeDir: "/tmp/openclaw-home/.openclaw",
      configPath: "/tmp/openclaw-home/.openclaw/openclaw.json",
      configText: JSON.stringify({
        agents: {
          list: [
            { id: "main", workspace: "/data/openclaw/workspace" },
            { id: "pandas", workspace: "/data/openclaw/workspace/agents/pandas" },
          ],
        },
      }),
    }),
    "/data/openclaw/workspace",
  );

  assert.equal(
    resolveOpenClawWorkspaceRoot({
      openclawHomeDir: "/tmp/openclaw-home/.openclaw",
      configPath: "/tmp/openclaw-home/.openclaw/openclaw.json",
    }),
    "/tmp/openclaw-home/.openclaw/workspace",
  );
});

test("agent workspace root follows main root, configured workspace, then agents fallback", () => {
  const configText = JSON.stringify({
    agents: {
      list: [
        { id: "main", workspace: "/srv/openclaw/workspace" },
        { id: "pandas", workspace: "/srv/openclaw/workspace/agents/pandas" },
        { id: "coq", name: "Coq-每日新闻", workspace: "/srv/openclaw/workspace/agents/coq" },
      ],
    },
  });

  assert.equal(
    resolveOpenClawAgentWorkspaceRoot({
      agentId: "main",
      openclawHomeDir: "/tmp/openclaw-home/.openclaw",
      configPath: "/tmp/openclaw-home/.openclaw/openclaw.json",
      configText,
    }),
    "/srv/openclaw/workspace",
  );

  assert.equal(
    resolveOpenClawAgentWorkspaceRoot({
      agentId: "pandas",
      openclawHomeDir: "/tmp/openclaw-home/.openclaw",
      configPath: "/tmp/openclaw-home/.openclaw/openclaw.json",
      configText,
    }),
    "/srv/openclaw/workspace/agents/pandas",
  );

  assert.equal(
    resolveOpenClawAgentWorkspaceRoot({
      agentId: "Coq-每日新闻",
      openclawHomeDir: "/tmp/openclaw-home/.openclaw",
      configPath: "/tmp/openclaw-home/.openclaw/openclaw.json",
      configText,
    }),
    "/srv/openclaw/workspace/agents/coq",
  );

  assert.equal(
    resolveOpenClawAgentWorkspaceRoot({
      agentId: "otter",
      openclawHomeDir: "/tmp/openclaw-home/.openclaw",
      configPath: "/tmp/openclaw-home/.openclaw/openclaw.json",
      configText,
    }),
    "/srv/openclaw/workspace/agents/otter",
  );
});
