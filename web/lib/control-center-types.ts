export type ControlCenterSectionKey =
  | "overview"
  | "usage"
  | "staff"
  | "collaboration"
  | "hall"
  | "tasks"
  | "docs"
  | "memory"
  | "settings";

export interface ControlCenterHealthzPayload {
  generatedAt: string;
  status: "ok" | "warn" | "stale";
  build: {
    name: string;
    version: string;
    node: string;
    readonlyMode: boolean;
    approvalActionsEnabled: boolean;
    approvalActionsDryRun: boolean;
    distIndexPath: string;
    distBuiltAt?: string;
  };
  snapshot: {
    generatedAt: string;
    ageMs: number;
    status: "ok" | "warn" | "stale";
  };
  monitor: {
    status: "ok" | "warn" | "stale" | "missing";
    ageMs?: number;
    detail?: string;
  };
}

export interface ControlCenterHealthzEnvelope {
  ok: boolean;
  health: ControlCenterHealthzPayload;
}

export interface ControlCenterCronOverviewResponse {
  ok: true;
  overview: {
    generatedAt: string;
    nextRunAt?: string;
    health: {
      status: "ok" | "warn";
      enabledJobs: number;
      totalJobs: number;
    };
  };
  rows: Array<{
    jobId: string;
    name: string;
    channel: "cron" | "heartbeat";
    enabled: boolean;
    owner: string;
    ownerAgentId?: string;
    purpose: string;
    schedule: string;
    nextRunAt?: string;
    status: "scheduled" | "due" | "late" | "unknown" | "disabled";
    lastRunAt?: string;
    lastRunStatus?: "success" | "error" | string;
    lastError?: string;
  }>;
}

export interface ControlCenterProxyError {
  code: string;
  message: string;
  path?: string;
  status?: number;
  upstreamStatus?: number;
  detail?: string;
}

export interface ControlCenterUsageResponse {
  ok: true;
  usage: {
    generatedAt: string;
    periods: Array<{
      key: "today" | "7d" | "30d";
      label: string;
      tokens: number;
      estimatedCost: number;
      sourceStatus: "connected" | "partial" | "not_connected";
    }>;
    budget: {
      status: "ok" | "warn" | "over" | "not_connected";
      usedCost30d: number;
      limitCost30d?: number;
      message: string;
      limitSource?: "agent_budgets" | "global_runtime_limit" | "missing";
      detail?: string;
      connectHint?: string;
      configPath?: string;
      recommendedConfigPath?: string;
      templateHref?: string;
      actionLabel?: string;
    };
    subscription: {
      status: "connected" | "partial" | "not_connected";
      planLabel: string;
      consumed?: number;
      remaining?: number;
      limit?: number;
      unit: string;
      detail: string;
      connectHint: string;
      connectHintShort?: string;
      sourceCandidates?: string[];
      templateHref?: string;
      templateSavePath?: string;
      recommendedSourcePath?: string;
      signalMode?: "provider" | "runtime_backfill" | "budget_backfill" | "missing";
    };
    connectors: {
      modelContextCatalog: "connected" | "partial" | "not_connected";
      digestHistory: "connected" | "partial" | "not_connected";
      requestCounts: "connected" | "partial" | "not_connected";
      budgetLimit: "connected" | "partial" | "not_connected";
      providerAttribution: "connected" | "partial" | "not_connected";
      subscriptionUsage: "connected" | "partial" | "not_connected";
      todos: Array<{
        id: string;
        title: string;
        detail: string;
      }>;
    };
  };
}

export interface ControlCenterSessionsResponse {
  ok: true;
  count: number;
  sessions: Array<{
    sessionKey: string;
    label?: string;
    agentId?: string;
    state?: string;
    lastMessageAt?: string;
    updatedAt?: string;
    participants?: string[];
  }>;
}

export interface ControlCenterStaffCard {
  agentId: string;
  displayName: string;
  roleKey: "manager" | "planner" | "coder" | "reviewer" | "generalist" | "unassigned";
  roleLabel: string;
  statusLabel: string;
  statusSource?: "latest_session" | "office_fallback";
  currentWorkLabel: string;
  currentWork: string;
  recentOutput: string;
  recentOutputAt?: string;
  scheduledLabel: string;
}

export interface ControlCenterStaffRoleGroup {
  roleKey: ControlCenterStaffCard["roleKey"];
  roleLabel: string;
  count: number;
  members: ControlCenterStaffCard[];
}

export interface ControlCenterStaffSummaryResponse {
  ok: true;
  generatedAt: string;
  groups: ControlCenterStaffRoleGroup[];
  sessionsDetail: {
    count: number;
    sessions: Array<{
      sessionKey: string;
      label?: string;
      agentId?: string;
      state?: string;
      lastMessageAt?: string;
      updatedAt?: string;
      latestSnippet?: string;
    }>;
  };
}

export interface ControlCenterTasksResponse {
  ok: true;
  updatedAt: string;
  count: number;
  tasks: Array<{
    projectId: string;
    projectTitle: string;
    taskId: string;
    title: string;
    status: string;
    owner?: string;
    roomId?: string;
    dueAt?: string;
    sessionKeys?: string[];
    updatedAt: string;
  }>;
}

export interface ControlCenterHallResponse {
  ok: true;
  hall: {
    hallId: string;
    title?: string;
    description?: string;
  };
  summary?: {
    status?: string;
    headline?: string;
    detail?: string;
  };
  participants: Array<{
    participantId: string;
    displayName: string;
    semanticRole?: string;
    active?: boolean;
  }>;
  count: number;
  taskCards: Array<{
    taskCardId: string;
    projectId: string;
    taskId: string;
    title: string;
    description: string;
    stage: string;
    status?: string;
    currentOwnerLabel?: string;
    latestSummary?: string;
  }>;
  messages: Array<{
    messageId: string;
    authorLabel: string;
    content: string;
    kind: string;
    createdAt: string;
    taskCardId?: string;
  }>;
}

export interface ControlCenterFilesResponse {
  ok: true;
  scope: "memory" | "workspace";
  count: number;
  facetOptions?: Array<{
    key: string;
    label: string;
  }>;
  defaultFacetKey?: string;
  files: Array<{
    title: string;
    sourcePath: string;
    relativePath?: string;
    category?: string;
    excerpt?: string;
    updatedAt?: string;
    sizeBytes?: number;
    size?: number;
    facetKey?: string;
    facetLabel?: string;
  }>;
}

export interface ControlCenterDiagnosticsResponse {
  ok: true;
  diagnostics: {
    generatedAt: string;
    gateway: {
      configuredUrl: string;
      overallStatus: string;
    };
    openclaw: {
      status: string;
      currentVersion?: string;
      latestVersion?: string;
      updateAvailable: boolean;
    };
    tokens: {
      localTokenAuthRequired: boolean;
      entries: Array<{
        key: string;
        present: boolean;
        note: string;
      }>;
    };
    recentIssues: Array<{
      timestamp: string;
      severity: "warn" | "error";
      action: string;
      detail: string;
      requestId?: string;
    }>;
  };
}
