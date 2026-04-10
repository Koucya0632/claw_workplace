type UnknownRecord = Record<string, unknown>;

export interface ParsedAgentRuntimePayload {
  kind: "runtime" | "system_inspection_report" | "news_brief_report" | "development_structured";
  structuredKind?: "development_stage";
  runId?: string;
  status?: string;
  summary?: string;
  provider?: string;
  model?: string;
  durationMs?: number;
  text?: string;
  title?: string;
  detail?: string;
  highlights?: string[];
  artifacts?: string[];
  raw: unknown;
}

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : null;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function tryParseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function readPartialStringField(text: string, field: string): string | undefined {
  const pattern = new RegExp(String.raw`(?:\\"|")${field}(?:\\"|")\s*:\s*(?:\\"|")([^"]+)`);
  const match = text.match(pattern);
  return match?.[1]?.trim() || undefined;
}

function readPartialNumberField(text: string, field: string): number | undefined {
  const pattern = new RegExp(String.raw`(?:\\"|")${field}(?:\\"|")\s*:\s*(\d+)`);
  const match = text.match(pattern);
  if (!match?.[1]) return undefined;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : undefined;
}

function parseTruncatedAgentRuntimeString(text: string): ParsedAgentRuntimePayload | null {
  const runId = readPartialStringField(text, "runId");
  const status = readPartialStringField(text, "status");
  const summary = readPartialStringField(text, "summary");
  const provider = readPartialStringField(text, "provider");
  const model = readPartialStringField(text, "model");
  const durationMs = readPartialNumberField(text, "durationMs");
  const payloadsEmpty = /(?:\\"|")payloads(?:\\"|")\s*:\s*\[\s*\]/.test(text);

  if (!runId && !status && !summary && !provider && !model && !durationMs && !payloadsEmpty) {
    return null;
  }

  return {
    kind: "runtime",
    runId,
    status,
    summary,
    provider,
    model,
    durationMs,
    text: undefined,
    title: undefined,
    detail: undefined,
    highlights: [],
    artifacts: [],
    raw: text,
  };
}

function extractTextFromResult(result: UnknownRecord | null): string | undefined {
  const payloads = Array.isArray(result?.payloads) ? result.payloads : [];
  const text = payloads
    .map((item) => {
      const payload = asRecord(item);
      return asString(payload?.text);
    })
    .filter((item): item is string => Boolean(item))
    .join("\n\n")
    .trim();

  if (text) return text;
  return asString(result?.text) ?? asString(result?.output_text);
}

function parseAgentRuntimePayloadCandidate(value: unknown): ParsedAgentRuntimePayload | null {
  const payload = asRecord(value);
  if (!payload) return null;

  const result = asRecord(payload.result) ?? payload;
  const meta = asRecord(result.meta);
  const agentMeta = asRecord(meta?.agentMeta);
  const systemPromptReport = asRecord(meta?.systemPromptReport);
  const text = extractTextFromResult(result);
  const runId = asString(payload.runId);
  const status = asString(payload.status);
  const summary = asString(payload.summary);
  const provider = asString(agentMeta?.provider) ?? asString(systemPromptReport?.provider);
  const model = asString(agentMeta?.model) ?? asString(systemPromptReport?.model);
  const durationMs = asNumber(meta?.durationMs);
  const hasRuntimeEnvelope =
    "result" in payload ||
    "runId" in payload ||
    "status" in payload ||
    "message" in payload ||
    "output_text" in payload ||
    "content" in payload ||
    "text" in payload;

  if ((!runId && !status && !summary && !provider && !model && !durationMs && !text) || !hasRuntimeEnvelope) {
    return null;
  }

  return {
    kind: "runtime",
    runId,
    status,
    summary,
    provider,
    model,
    durationMs,
    text,
    title: undefined,
    detail: undefined,
    highlights: [],
    artifacts: [],
    raw: value,
  };
}

function parseDevelopmentStructuredPayloadCandidate(value: unknown): ParsedAgentRuntimePayload | null {
  const payload = asRecord(value);
  if (!payload) return null;

  const summary = asString(payload.summary);
  const completedItems = asStringArray(payload.completed_items);
  const changedModules = asStringArray(payload.changed_modules);
  const notableDecisions = asStringArray(payload.notable_decisions);
  const testResults = asStringArray(payload.test_results);
  const improvements = asStringArray(payload.improvements);
  const tasks = asStructuredTaskTitles(payload.tasks);

  const hasStructuredFields =
    completedItems.length > 0 ||
    changedModules.length > 0 ||
    notableDecisions.length > 0 ||
    testResults.length > 0 ||
    improvements.length > 0 ||
    tasks.length > 0;

  if (!summary || !hasStructuredFields) {
    return null;
  }

  const highlights = [
    ...completedItems.slice(0, 3),
    ...notableDecisions.slice(0, 2),
    ...testResults.slice(0, 2),
    ...improvements.slice(0, 2),
    ...tasks.slice(0, 2)
  ];
  const artifacts = [...changedModules.slice(0, 4), ...completedItems.slice(0, 2)];

  return {
    kind: "development_structured",
    structuredKind: "development_stage",
    summary,
    detail: highlights[0],
    highlights,
    artifacts,
    raw: value,
  };
}

function parseStructuredWorkflowReportCandidate(value: unknown): ParsedAgentRuntimePayload | null {
  const payload = asRecord(value);
  if (!payload) return null;

  const title = asString(payload.title);
  if (!title) return null;

  const inspectionSummary = Array.isArray(payload.inspection_summary)
    ? payload.inspection_summary.map(asString).filter((item): item is string => Boolean(item))
    : [];
  if (inspectionSummary.length > 0) {
    return {
      kind: "system_inspection_report",
      title,
      detail: inspectionSummary[0],
      highlights: inspectionSummary.slice(0, 3),
      artifacts: [],
      raw: value,
    };
  }

  const trendSummary = asString(payload.trend_summary);
  const topStories = Array.isArray(payload.top_stories) ? payload.top_stories : [];
  if (trendSummary || topStories.length > 0) {
    return {
      kind: "news_brief_report",
      title,
      detail: trendSummary,
      highlights: topStories.length > 0 ? topStories.map(() => title).slice(0, 3) : [],
      artifacts: [],
      raw: value,
    };
  }

  return null;
}

function parseNestedAgentRuntimePayload(value: unknown, depth = 0): ParsedAgentRuntimePayload | null {
  if (depth > 3 || value == null) return null;

  const developmentStructured = parseDevelopmentStructuredPayloadCandidate(value);
  if (developmentStructured) return developmentStructured;

  const direct = parseAgentRuntimePayloadCandidate(value);
  if (direct) return direct;

  const structured = parseStructuredWorkflowReportCandidate(value);
  if (structured) return structured;

  if (typeof value === "string") {
    const parsed = tryParseJson(value);
    if (parsed != null) {
      const nested = parseNestedAgentRuntimePayload(parsed, depth + 1);
      if (nested) return nested;
    }
    return parseTruncatedAgentRuntimeString(value) ?? parseSummaryMetaString(value);
  }

  const payload = asRecord(value);
  if (!payload) return null;

  if ("error" in payload) {
    const nested = parseNestedAgentRuntimePayload(payload.error, depth + 1);
    if (nested) return nested;
  }

  if ("detail" in payload) {
    const nested = parseNestedAgentRuntimePayload(payload.detail, depth + 1);
    if (nested) return nested;
  }

  return null;
}

export function inspectWorkflowPayload(value: unknown): ParsedAgentRuntimePayload | null {
  return parseNestedAgentRuntimePayload(value);
}

export function summarizeWorkflowRuntimeIssue(value: unknown, contextLabel = "Agent"): string | null {
  const parsed = inspectWorkflowPayload(value);
  if (!parsed) return null;

  if (parsed.kind === "system_inspection_report") {
    const detail = parsed.detail ? ` ${parsed.detail}` : "";
    return `${contextLabel} 回傳了結構化巡檢報告：${parsed.title ?? "未命名巡檢報告"}。${detail}`.trim();
  }

  if (parsed.kind === "news_brief_report") {
    const detail = parsed.detail ? ` ${parsed.detail}` : "";
    return `${contextLabel} 回傳了結構化 Daily News Brief：${parsed.title ?? "未命名新聞簡報"}。${detail}`.trim();
  }

  if (parsed.text) {
    return parsed.text;
  }

  if (parsed.kind === "development_structured" && parsed.summary) {
    const highlights = parsed.highlights && parsed.highlights.length > 0 ? ` 重點：${parsed.highlights.slice(0, 3).join("；")}` : "";
    return `${parsed.summary}${highlights}`.trim();
  }

  if (parsed.summary && !isGenericRuntimeSummary(parsed.summary)) {
    const details: string[] = [];
    if (parsed.provider) details.push(`provider ${parsed.provider}`);
    if (parsed.model) details.push(`model ${parsed.model}`);
    if (typeof parsed.durationMs === "number") details.push(`耗時約 ${(parsed.durationMs / 1000).toFixed(1)} 秒`);
    const meta = details.length > 0 ? ` (${details.join(" / ")})` : "";
    return `${parsed.summary}${meta}`;
  }

  const details: string[] = [];
  if (parsed.provider) details.push(`provider ${parsed.provider}`);
  if (parsed.model) details.push(`model ${parsed.model}`);
  if (typeof parsed.durationMs === "number") details.push(`耗時約 ${(parsed.durationMs / 1000).toFixed(1)} 秒`);

  const meta = details.length > 0 ? ` (${details.join(" / ")})` : "";
  if (parsed.status === "ok") {
    return `${contextLabel} 已完成執行，但沒有回傳可解析文字內容${meta}。`;
  }
  return `${contextLabel} 回傳了結構化狀態，但目前沒有可讀文字內容${meta}。`;
}

function parseSummaryMetaString(text: string): ParsedAgentRuntimePayload | null {
  const summary = readKeyValue(text, "summary");
  const provider = readKeyValue(text, "provider");
  const model = readKeyValue(text, "model");
  const status = readKeyValue(text, "status");
  const completed = readListValue(text, "completed");
  const decisions = readListValue(text, "decisions");
  const tests = readListValue(text, "tests");
  const improvements = readListValue(text, "improvements");
  const tasks = readListValue(text, "tasks");
  const modules = readListValue(text, "modules");
  const durationMatch = text.match(/耗時約\s*(\d+(?:\.\d+)?)\s*秒/);
  const durationMs = durationMatch ? Number(durationMatch[1]) * 1000 : undefined;

  if (!summary && !provider && !model && !status && modules.length === 0 && completed.length === 0) {
    return null;
  }

  const highlights = [...completed, ...decisions, ...tests, ...improvements, ...tasks];

  return {
    kind: "runtime",
    status,
    summary,
    provider,
    model,
    durationMs,
    raw: text,
    highlights,
    artifacts: modules,
  };
}

function readKeyValue(text: string, key: string): string | undefined {
  const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = text.match(new RegExp(`${escapedKey}=(.*?)(?:\\s\\/\\s[a-z_]+=|$)`));
  return match?.[1]?.trim() || undefined;
}

function readListValue(text: string, key: string): string[] {
  const raw = readKeyValue(text, key);
  if (!raw) return [];
  return raw
    .split(/[;；]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isGenericRuntimeSummary(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return ["completed", "complete", "ok", "success", "succeeded", "finished", "done"].includes(normalized);
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(asString).filter((item): item is string => Boolean(item)) : [];
}

function asStructuredTaskTitles(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      const payload = asRecord(item);
      return asString(payload?.title) ?? asString(payload?.description);
    })
    .filter((item): item is string => Boolean(item));
}
