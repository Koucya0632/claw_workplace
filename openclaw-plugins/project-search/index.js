const PLUGIN_ID = "project-search";

function resolvePluginConfig(ctx) {
  const runtimePlugins = ctx?.runtimeConfig?.plugins?.entries;
  const staticPlugins = ctx?.config?.plugins?.entries;
  const entry = runtimePlugins?.[PLUGIN_ID] ?? staticPlugins?.[PLUGIN_ID];
  if (!entry || typeof entry !== "object") {
    return {};
  }

  const config = entry.config;
  return config && typeof config === "object" ? config : {};
}

function resolveCurrentAgentId(ctx) {
  if (typeof ctx?.agentId === "string" && ctx.agentId.trim()) {
    return ctx.agentId.trim();
  }

  if (typeof ctx?.sessionKey === "string") {
    const match = ctx.sessionKey.match(/^agent:([^:]+)/);
    if (match?.[1]) {
      return match[1];
    }
  }

  return null;
}

function resolveCurrentSessionId(ctx) {
  if (typeof ctx?.sessionId === "string" && ctx.sessionId.trim()) {
    return ctx.sessionId.trim();
  }

  if (typeof ctx?.sessionKey === "string" && ctx.sessionKey.trim()) {
    return ctx.sessionKey.trim();
  }

  return null;
}

function isAgentEnabled(ctx) {
  const agentId = resolveCurrentAgentId(ctx);
  if (!agentId) {
    return false;
  }

  const enabledAgents = resolvePluginConfig(ctx).enabledAgents;
  if (!Array.isArray(enabledAgents)) {
    return false;
  }

  return enabledAgents.some((value) => typeof value === "string" && value.trim() === agentId);
}

function readStringParam(params, key, { required = false } = {}) {
  const value = params?.[key];
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (required) {
    throw new Error(`${key} is required`);
  }
  return undefined;
}

function readNumberParam(params, key) {
  const value = params?.[key];
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return undefined;
}

function jsonResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2)
      }
    ],
    details: payload
  };
}

async function callBridge(ctx, path, payload) {
  const agentId = resolveCurrentAgentId(ctx);
  const sessionId = resolveCurrentSessionId(ctx);
  if (!agentId) {
    return jsonResult({
      error: "missing_agent_id",
      message: "OpenClaw runtime did not provide agentId or a parseable sessionKey."
    });
  }
  if (!sessionId) {
    return jsonResult({
      error: "missing_session_id",
      message: "OpenClaw runtime did not provide sessionId."
    });
  }

  const pluginConfig = resolvePluginConfig(ctx);
  const apiBaseUrl = typeof pluginConfig.apiBaseUrl === "string" ? pluginConfig.apiBaseUrl.trim().replace(/\/$/, "") : "";
  if (!apiBaseUrl) {
    return jsonResult({
      error: "missing_api_base_url",
      message: "plugins.entries.project-search.config.apiBaseUrl is not configured."
    });
  }

  const timeoutMs = typeof pluginConfig.timeoutMs === "number" && Number.isFinite(pluginConfig.timeoutMs)
    ? Math.max(1000, pluginConfig.timeoutMs)
    : 15000;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${apiBaseUrl}/openclaw/agent-tools/${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        agent_id: agentId,
        session_id: sessionId,
        ...payload
      }),
      signal: controller.signal
    });

    const parsed = await response.json().catch(() => null);
    if (!response.ok) {
      return jsonResult({
        error: "bridge_http_error",
        message: parsed?.error?.detail ?? parsed?.error?.message ?? `HTTP ${response.status}`,
        status: response.status
      });
    }

    if (!parsed?.success) {
      return jsonResult({
        error: "bridge_request_failed",
        message: parsed?.error?.detail ?? parsed?.error?.message ?? "bridge request failed"
      });
    }

    return jsonResult(parsed.data ?? {});
  } catch (error) {
    return jsonResult({
      error: "bridge_runtime_error",
      message: error instanceof Error ? error.message : String(error)
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

function createProjectSearchTool(ctx) {
  if (!isAgentEnabled(ctx)) {
    return null;
  }

  return {
    name: "project_search",
    label: "Project Search",
    description: "Search the OpenClaw Smart Office indexed knowledge base without using exec.",
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        query: {
          type: "string",
          description: "Search query."
        },
        source_id: {
          type: "string",
          description: "Optional source id filter."
        },
        limit: {
          type: "number",
          description: "Optional result limit."
        }
      },
      required: ["query"]
    },
    async execute(_toolCallId, params) {
      try {
        const query = readStringParam(params, "query", { required: true });
        const sourceId = readStringParam(params, "source_id");
        const limit = readNumberParam(params, "limit");
        return await callBridge(ctx, "search", {
          query,
          source_id: sourceId,
          limit
        });
      } catch (error) {
        return jsonResult({
          error: "tool_input_error",
          message: error instanceof Error ? error.message : String(error)
        });
      }
    }
  };
}

function createProjectDocumentTool(ctx) {
  if (!isAgentEnabled(ctx)) {
    return null;
  }

  return {
    name: "project_document",
    label: "Project Document",
    description: "Read a document body from the OpenClaw Smart Office indexed knowledge base.",
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        document_id: {
          type: "string",
          description: "Document id returned by project_search."
        },
        max_chars: {
          type: "number",
          description: "Optional maximum returned characters."
        }
      },
      required: ["document_id"]
    },
    async execute(_toolCallId, params) {
      try {
        const documentId = readStringParam(params, "document_id", { required: true });
        const maxChars = readNumberParam(params, "max_chars");
        return await callBridge(ctx, "document", {
          document_id: documentId,
          max_chars: maxChars
        });
      } catch (error) {
        return jsonResult({
          error: "tool_input_error",
          message: error instanceof Error ? error.message : String(error)
        });
      }
    }
  };
}

export default {
  id: PLUGIN_ID,
  name: "Project Search",
  description: "Native project search tools for OpenClaw Smart Office.",
  register(api) {
    api.registerTool((ctx) => createProjectSearchTool(ctx), { name: "project_search" });
    api.registerTool((ctx) => createProjectDocumentTool(ctx), { name: "project_document" });
  }
};
