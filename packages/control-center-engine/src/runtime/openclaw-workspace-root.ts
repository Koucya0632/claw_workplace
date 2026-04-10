import { readFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";

interface OpenClawWorkspaceRootInput {
  explicitWorkspaceRoot?: string;
  openclawHomeDir: string;
  configPath: string;
  configText?: string;
}

interface OpenClawAgentWorkspaceRootInput extends OpenClawWorkspaceRootInput {
  agentId: string;
  rawWorkspace?: string;
}

export function resolveOpenClawWorkspaceRoot(input: OpenClawWorkspaceRootInput): string {
  const explicit = input.explicitWorkspaceRoot?.trim();
  if (explicit) return resolve(explicit);
  const configText = input.configText ?? safeReadTextFileSync(input.configPath);
  const inferred = inferWorkspaceRootFromConfigText(configText, dirname(input.configPath));
  if (inferred) return inferred;
  return join(input.openclawHomeDir, "workspace");
}

export function resolveOpenClawAgentWorkspaceRoot(input: OpenClawAgentWorkspaceRootInput): string {
  const agentId = input.agentId.trim();
  const workspaceRoot = resolveOpenClawWorkspaceRoot(input);
  if (normalizeLookupKey(agentId) === "main") return workspaceRoot;

  const explicitWorkspace = normalizeWorkspaceOverride(input.rawWorkspace);
  if (explicitWorkspace) {
    return resolve(dirname(input.configPath), explicitWorkspace);
  }

  const configText = input.configText ?? safeReadTextFileSync(input.configPath);
  const configuredWorkspace = findConfiguredAgentWorkspace(configText, dirname(input.configPath), agentId);
  if (configuredWorkspace) return configuredWorkspace;

  return join(workspaceRoot, "agents", agentId);
}

function safeReadTextFileSync(path: string): string | undefined {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return undefined;
  }
}

function inferWorkspaceRootFromConfigText(raw: string | undefined, configDir: string): string | undefined {
  if (!raw?.trim()) return undefined;
  try {
    return inferWorkspaceRootFromConfigObject(JSON.parse(raw) as unknown, configDir);
  } catch {
    return undefined;
  }
}

function inferWorkspaceRootFromConfigObject(input: unknown, configDir: string): string | undefined {
  const root = asObject(input);
  const agents = asObject(root?.agents);
  const list = asArray(agents?.list);
  const mainRow = list
    .map((item) => asObject(item))
    .find((row) => normalizeLookupKey(asString(row?.id)?.trim() ?? asString(row?.name)?.trim() ?? "") === "main");
  const explicitMainWorkspace = normalizeWorkspaceOverride(asString(mainRow?.workspace));
  if (explicitMainWorkspace) return resolve(configDir, explicitMainWorkspace);

  const inferredRoots = new Set<string>();
  for (const item of list) {
    const row = asObject(item);
    const rawWorkspace = normalizeWorkspaceOverride(asString(row?.workspace));
    if (!rawWorkspace) continue;
    const workspacePath = resolve(configDir, rawWorkspace);
    const parentDir = dirname(workspacePath);
    if (basename(parentDir).toLowerCase() !== "agents") continue;
    inferredRoots.add(dirname(parentDir));
  }
  if (inferredRoots.size === 1) return [...inferredRoots][0];
  return undefined;
}

function findConfiguredAgentWorkspace(
  raw: string | undefined,
  configDir: string,
  agentId: string,
): string | undefined {
  if (!raw?.trim()) return undefined;
  try {
    const root = asObject(JSON.parse(raw) as unknown);
    const agents = asObject(root?.agents);
    const list = asArray(agents?.list);
    const normalizedId = normalizeLookupKey(agentId);
    const match = list
      .map((item) => asObject(item))
      .find((row) => {
        const rowId = normalizeLookupKey(asString(row?.id)?.trim() ?? "");
        const rowName = normalizeLookupKey(asString(row?.name)?.trim() ?? "");
        return rowId === normalizedId || rowName === normalizedId;
      });
    const rawWorkspace = normalizeWorkspaceOverride(asString(match?.workspace));
    return rawWorkspace ? resolve(configDir, rawWorkspace) : undefined;
  } catch {
    return undefined;
  }
}

function normalizeWorkspaceOverride(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  if (trimmed === "未标注" || trimmed === "unlisted") return undefined;
  return trimmed;
}

function normalizeLookupKey(input: string): string {
  return input.trim().toLowerCase();
}

function asObject(input: unknown): Record<string, unknown> | undefined {
  return input !== null && typeof input === "object" && !Array.isArray(input)
    ? (input as Record<string, unknown>)
    : undefined;
}

function asArray(input: unknown): unknown[] {
  return Array.isArray(input) ? input : [];
}

function asString(input: unknown): string | undefined {
  return typeof input === "string" ? input : undefined;
}
