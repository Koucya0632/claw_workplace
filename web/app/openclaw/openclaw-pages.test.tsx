import React from "react";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import OpenClawActionsPage from "@/app/openclaw/actions/page";
import OpenClawAgentsPage from "@/app/openclaw/agents/page";
import OpenClawCollaborationPage from "@/app/openclaw/collaboration/page";
import OpenClawConfigPage from "@/app/openclaw/config/page";
import OpenClawDevelopmentPage from "@/app/openclaw/development/page";
import OpenClawDailyNewsPage from "@/app/openclaw/daily-news/page";
import OpenClawDevicesPage from "@/app/openclaw/devices/page";
import OpenClawDocsPage from "@/app/openclaw/docs/page";
import OpenClawInstancesPage from "@/app/openclaw/instances/page";
import OpenClawKnowledgePage from "@/app/openclaw/knowledge/page";
import OpenClawLogsPage from "@/app/openclaw/logs/page";
import OpenClawMemoryPage from "@/app/openclaw/memory/page";
import OpenClawOverviewPage from "@/app/openclaw/page";
import OpenClawSettingsPage from "@/app/openclaw/settings/page";
import OpenClawStaffPage from "@/app/openclaw/staff/page";
import OpenClawSystemInspectionPage from "@/app/openclaw/system-inspection/page";
import OpenClawUsagePage from "@/app/openclaw/usage/page";
import OpenClawWorkflowPage from "@/app/openclaw/workflow/page";
import * as api from "@/lib/api";
import * as controlCenterApi from "@/lib/control-center-api";

let mockPathname = "/openclaw";
let mockSearch = "";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useSearchParams: () => new URLSearchParams(mockSearch)
}));

vi.mock("@/lib/api", () => ({
  fetchOpenClawInstances: vi.fn(),
  fetchOpenClawOperations: vi.fn(),
  fetchOpenClawAgents: vi.fn(),
  fetchOpenClawDevices: vi.fn(),
  fetchOpenClawConfig: vi.fn(),
  setOpenClawConfig: vi.fn(),
  validateOpenClawConfig: vi.fn(),
  fetchOpenClawWorkflowConfig: vi.fn(),
  updateOpenClawWorkflowConfig: vi.fn(),
  fetchOpenClawDailyNewsConfig: vi.fn(),
  updateOpenClawDailyNewsConfig: vi.fn(),
  fetchOpenClawDevelopmentConfig: vi.fn(),
  updateOpenClawDevelopmentConfig: vi.fn(),
  fetchOpenClawSystemInspectionConfig: vi.fn(),
  updateOpenClawSystemInspectionConfig: vi.fn(),
  fetchWorkflowRun: vi.fn(),
  fetchWorkflowRuns: vi.fn(),
  createNewsBriefWorkflow: vi.fn(),
  createSystemInspectionWorkflow: vi.fn(),
  fetchSources: vi.fn(),
  fetchKnowledgeIngestionRuns: vi.fn(),
  fetchDocumentVersions: vi.fn(),
  ingestKnowledge: vi.fn(),
  scanSource: vi.fn(),
  updateOpenClawAgentSearchCapability: vi.fn(),
  runOpenClawDeviceAction: vi.fn(),
  dispatchOpenClawAgentHook: vi.fn(),
  dispatchOpenClawWakeHook: vi.fn(),
  createOpenClawAgent: vi.fn(),
  createDevelopmentExecutionWorkflow: vi.fn()
}));

vi.mock("@/lib/control-center-api", () => ({
  fetchControlCenterHealthz: vi.fn(),
  fetchControlCenterCronOverview: vi.fn(),
  fetchControlCenterUsage: vi.fn(),
  fetchControlCenterSessions: vi.fn(),
  fetchControlCenterStaffSummary: vi.fn(),
  fetchControlCenterTasks: vi.fn(),
  fetchControlCenterHall: vi.fn(),
  fetchControlCenterFiles: vi.fn(),
  fetchControlCenterDiagnostics: vi.fn()
}));

const INSTANCE_FIXTURE = [
  {
    id: "oc_1",
    name: "Primary Gateway",
    gateway_url: "http://gateway.internal",
    is_active: true,
    has_token: true,
    last_health_status: "healthy",
    last_health_checked_at: new Date().toISOString(),
    snapshot_summary: {
      health_status: "healthy",
      agent_count: 2,
      device_count: 1,
      config_updated_at: new Date().toISOString()
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

const DEFAULT_SYSTEM_INSPECTION_CONFIG_FIXTURE = {
  instance_id: "oc_1",
  enabled: true,
  schedule_timezone: "Asia/Tokyo",
  schedule_time: "09:30",
  delivery_channel: "telegram" as const,
  telegram_target: "",
  discord_channel_id: "",
  version_check_enabled: true,
  log_review_enabled: true,
  log_review_window_hours: 24,
  log_review_limit: 500,
  official_release_url: "https://docs.openclaw.ai/cli/agents",
  last_scheduled_date: null,
  last_run_id: null,
  last_delivery_status: null,
  last_delivery_error: null,
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString(),
};

const DEFAULT_DAILY_NEWS_CONFIG_FIXTURE = {
  instance_id: "oc_1",
  enabled: true,
  brief_name: "Daily News Brief",
  topic: "AI, OpenClaw, agent systems",
  keywords: [],
  industries: [],
  regions: [],
  people: [],
  companies: [],
  source_domains: [],
  source_urls: [],
  must_include: [],
  must_exclude: [],
  focus_points: [],
  output_format: "summary" as const,
  delivery_channel: "telegram" as const,
  telegram_target: "",
  discord_channel_id: "",
  schedule_timezone: "Asia/Tokyo",
  schedule_time: "09:00",
  last_scheduled_date: null,
  last_run_id: null,
  last_delivery_status: null,
  last_delivery_error: null,
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString(),
};

const DEFAULT_DEVELOPMENT_CONFIG_FIXTURE = {
  instance_id: "oc_1",
  enabled: true,
  delivery_channel: "discord" as const,
  discord_channel_id: "channel_development",
  last_run_id: "run-dev-latest",
  last_delivery_status: "delivered",
  last_delivery_error: null,
  config_source: "stored" as const,
  effective_delivery_source: "development_config" as const,
  effective_discord_channel_id: "channel_development",
  effective_delivery_reason: "已使用 Development 專屬 Discord 設定。",
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString(),
};

function buildHealthzFixture(status: "ok" | "warn" = "ok") {
  return {
    generatedAt: new Date().toISOString(),
    status,
    build: {
      name: "control-center",
      version: "1.0.0",
      node: "v20.0.0",
      readonlyMode: true,
      approvalActionsEnabled: false,
      approvalActionsDryRun: true,
      distIndexPath: "/tmp/dist/index.js"
    },
    snapshot: {
      generatedAt: new Date().toISOString(),
      ageMs: 0,
      status
    },
    monitor: {
      status
    }
  } as const;
}

function buildUsageFixture() {
  return {
    ok: true,
    usage: {
      generatedAt: new Date().toISOString(),
      periods: [],
      budget: {
        status: "not_connected" as const,
        usedCost30d: 0,
        message: "尚無資料",
        limitSource: "missing" as const,
        detail: "尚未設定月預算來源。",
        connectHint: "Use /api/budget/template and save it as runtime/usage-budget.json.",
        configPath: "/tmp/runtime/usage-budget.json",
        recommendedConfigPath: "/tmp/runtime/usage-budget.json",
        templateHref: "/api/budget/template",
        actionLabel: "Add a monthly budget limit from the template or agent cost thresholds.",
      },
      subscription: {
        status: "not_connected" as const,
        planLabel: "未接通",
        unit: "USD",
        detail: "尚未接入 provider subscription snapshot。",
        connectHint: "等待接線",
        connectHintShort: "先建立 provider snapshot 或接上 Codex telemetry。",
        sourceCandidates: ["/tmp/subscription-a.json", "/tmp/subscription-b.json"],
        templateHref: "/api/subscription/template",
        templateSavePath: "/tmp/runtime/subscription-snapshot.json",
        recommendedSourcePath: "/tmp/runtime/subscription-snapshot.json",
        signalMode: "missing" as const,
      },
      connectors: {
        modelContextCatalog: "not_connected" as const,
        digestHistory: "not_connected" as const,
        requestCounts: "not_connected" as const,
        budgetLimit: "not_connected" as const,
        providerAttribution: "not_connected" as const,
        subscriptionUsage: "not_connected" as const,
        todos: [
          {
            id: "cost_budget_limit",
            title: "Configure monthly budget limit",
            detail: "Add a global budget file or agent cost thresholds so burn-rate alerts can compare against a real limit.",
          },
          {
            id: "subscription_usage",
            title: "Connect subscription usage snapshot",
            detail: "Create a provider snapshot via /api/subscription/template or connect Codex telemetry.",
          },
        ]
      }
    }
  };
}

function buildCronOverviewFixture() {
  return {
    ok: true,
    overview: {
      generatedAt: new Date().toISOString(),
      nextRunAt: new Date(Date.now() + 60_000).toISOString(),
      health: {
        status: "ok" as const,
        enabledJobs: 3,
        totalJobs: 3
      }
    },
    rows: [
      {
        jobId: "daily-news:oc_1",
        name: "Daily News Brief",
        channel: "cron" as const,
        enabled: true,
        owner: "daily-news-brief-agent",
        ownerAgentId: "daily-news-brief-agent",
        purpose: "收集與整理每日新聞簡報。",
        schedule: "每天 09:00 Asia/Tokyo",
        nextRunAt: new Date(Date.now() + 60_000).toISOString(),
        status: "scheduled" as const,
        lastRunAt: new Date(Date.now() - 60_000).toISOString(),
        lastRunStatus: "error" as const,
        lastError: "Channel is required when multiple channels are configured."
      },
      {
        jobId: "system-inspection:oc_1",
        name: "System Inspection",
        channel: "cron" as const,
        enabled: true,
        owner: "system-inspection-agent",
        ownerAgentId: "system-inspection-agent",
        purpose: "執行系統巡檢與風險評估。",
        schedule: "每天 09:30 Asia/Tokyo",
        nextRunAt: new Date(Date.now() + 120_000).toISOString(),
        status: "scheduled" as const,
        lastRunAt: new Date(Date.now() - 120_000).toISOString(),
        lastRunStatus: "success" as const
      },
      {
        jobId: "runtime-task-heartbeat-worker",
        name: "Task heartbeat worker",
        channel: "heartbeat" as const,
        enabled: true,
        owner: "task-heartbeat-worker",
        purpose: "檢查任務心跳與拾取節奏。",
        schedule: "system interval",
        nextRunAt: new Date(Date.now() + 30_000).toISOString(),
        status: "scheduled" as const
      }
    ]
  };
}

function buildConnectedUsageFixture() {
  const fixture = buildUsageFixture();
  fixture.usage.subscription = {
    ...fixture.usage.subscription,
    status: "connected" as const,
    planLabel: "Codex telemetry",
    detail: "Live subscription telemetry is connected.",
    connectHint: "Provide one of: /tmp/subscription-a.json, /tmp/subscription-b.json. Or connect Codex session telemetry at /tmp/sessions/**/*.json.",
    connectHintShort: "Live subscription telemetry is connected.",
    signalMode: "provider" as const,
    consumed: 128,
    remaining: 872,
    limit: 1000,
  };

  return fixture;
}

function buildHallFixture() {
  return {
    ok: true,
    hall: { hallId: "main" },
    participants: [],
    count: 0,
    taskCards: [],
    messages: []
  };
}

function buildBusyHallFixture() {
  return {
    ok: true,
    hall: { hallId: "main", title: "Main hall" },
    summary: {
      status: "active",
      headline: "Builder Panda 與 Chief Lobster 正在同步交接與實作細節。",
      detail: "目前協作重心集中在 release handoff 與 implementation follow-up。"
    },
    participants: [
      {
        participantId: "main",
        displayName: "Chief Lobster",
        semanticRole: "主控與協調",
        active: true,
      },
      {
        participantId: "builder-panda",
        displayName: "Builder Panda",
        semanticRole: "工程交付",
        active: true,
      },
      {
        participantId: "support-otter",
        displayName: "Support Otter",
        semanticRole: "搜尋與整理",
        active: false,
      },
    ],
    count: 3,
    taskCards: [
      {
        taskCardId: "thread-release",
        projectId: "release",
        taskId: "release-handoff",
        title: "Release handoff",
        description: "Wrap the latest handoff and sync implementation blockers.",
        stage: "review",
        status: "active",
        currentOwnerLabel: "Chief Lobster",
        latestSummary: "正在確認 handoff 與 implementation 細節。",
      },
      {
        taskCardId: "thread-implementation",
        projectId: "builder",
        taskId: "implementation",
        title: "Implementation follow-up",
        description: "Track the builder workflow follow-up items.",
        stage: "build",
        status: "active",
        currentOwnerLabel: "Builder Panda",
        latestSummary: "Builder Panda 正在整理最新實作項目。",
      },
    ],
    messages: [
      {
        messageId: "m1",
        authorLabel: "Chief Lobster",
        content: "請先確認 release handoff 的最後一輪差異。",
        kind: "note",
        createdAt: new Date(Date.now() - 180_000).toISOString(),
        taskCardId: "thread-release",
      },
      {
        messageId: "m2",
        authorLabel: "Builder Panda",
        content: "已經補上 implementation follow-up 的缺口清單。",
        kind: "reply",
        createdAt: new Date(Date.now() - 120_000).toISOString(),
        taskCardId: "thread-implementation",
      },
      {
        messageId: "m3",
        authorLabel: "Chief Lobster",
        content: "Release handoff 這條 thread 先當主焦點。",
        kind: "decision",
        createdAt: new Date(Date.now() - 60_000).toISOString(),
        taskCardId: "thread-release",
      },
    ],
  };
}

function buildWorkspaceFilesFixture() {
  return {
    ok: true,
    scope: "workspace" as const,
    count: 3,
    defaultFacetKey: "main",
    facetOptions: [
      { key: "main", label: "Main" },
      { key: "builder-panda", label: "Builder Panda" },
    ],
    files: [
      {
        title: "Runbook",
        sourcePath: "/tmp/docs/RUNBOOK.md",
        relativePath: "docs/RUNBOOK.md",
        category: "Main 核心文档",
        excerpt: "Primary operating checklist for the control center.",
        updatedAt: new Date().toISOString(),
        size: 2400,
        facetKey: "main",
        facetLabel: "Main",
      },
      {
        title: "Architecture",
        sourcePath: "/tmp/docs/ARCHITECTURE.md",
        relativePath: "docs/ARCHITECTURE.md",
        category: "Main 核心文档",
        excerpt: "High-level system map and integration notes.",
        updatedAt: new Date().toISOString(),
        size: 1800,
        facetKey: "main",
        facetLabel: "Main",
      },
      {
        title: "Builder Notes",
        sourcePath: "/tmp/agents/builder-panda/WORKFLOW.md",
        relativePath: "agents/builder-panda/WORKFLOW.md",
        category: "Builder Panda 核心文档",
        excerpt: "Implementation notes for the builder workflow.",
        updatedAt: new Date().toISOString(),
        size: 1200,
        facetKey: "builder-panda",
        facetLabel: "Builder Panda",
      },
    ],
  };
}

function buildTasksFixture() {
  return {
    ok: true,
    updatedAt: new Date().toISOString(),
    count: 0,
    tasks: []
  };
}

function buildSessionsFixture() {
  return {
    ok: true,
    count: 0,
    sessions: []
  };
}

function buildStaffSummaryFixture() {
  return {
    ok: true,
    generatedAt: new Date().toISOString(),
    groups: [
      {
        roleKey: "manager" as const,
        roleLabel: "Manager",
        count: 1,
        members: [
          {
            agentId: "main",
            displayName: "Chief Lobster",
            roleKey: "manager" as const,
            roleLabel: "主控與協調",
            statusLabel: "Running",
            currentWorkLabel: "Current focus",
            currentWork: "Coordinating the active control-center queue.",
            recentOutput: "Published the latest execution handoff.",
            scheduledLabel: "Scheduled",
          },
        ],
      },
      {
        roleKey: "coder" as const,
        roleLabel: "Coder",
        count: 1,
        members: [
          {
            agentId: "pandas",
            displayName: "Builder Panda",
            roleKey: "coder" as const,
            roleLabel: "控制中心開發與交付",
            statusLabel: "Idle",
            currentWorkLabel: "Current focus",
            currentWork: "Waiting for the next implementation slice.",
            recentOutput: "Landed the latest dashboard patch.",
            scheduledLabel: "Not scheduled",
          },
        ],
      },
    ],
    sessionsDetail: {
      count: 1,
      sessions: [
        {
          sessionKey: "agent:main:main",
          label: "Main session",
          agentId: "main",
          state: "running",
          updatedAt: new Date().toISOString(),
          latestSnippet: "Reviewing the new staff role view.",
        },
      ],
    },
  };
}

function buildSystemInspectionRunWithNestedAgentError() {
  return {
    id: "run-system-1",
    instance_id: "oc_1",
    workflow_type: "system_inspection" as const,
    status: "failed",
    current_stage: "report",
    active_agent_id: "system-inspection-agent",
    overall_progress_percent: 100,
    input_payload: {
      instance_id: "oc_1",
    },
    error_message: null,
    stages: [
      {
        id: "stage-report-1",
        stage_key: "report",
        agent_id: "system-inspection-agent",
        status: "failed",
        progress_percent: 100,
        input_payload: {
          topic: "inspection",
        },
        output_payload: {
          error: JSON.stringify({
            runId: "09892c3f-bd1a-4c3d-9dab-38f40b3f7125",
            status: "ok",
            summary: "completed",
            result: {
              payloads: [],
              meta: {
                durationMs: 2425,
                agentMeta: {
                  sessionId: "afbe3143-26c9-4f65-9c2c-c3c2e22979cf",
                  provider: "minimax",
                  model: "MiniMax-M1",
                },
              },
            },
          }),
        },
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    events: [
      {
        id: "event-report-1",
        run_id: "run-system-1",
        stage_key: "report",
        agent_id: "system-inspection-agent",
        status: "failed",
        progress_percent: 100,
        message: "report 階段失敗。",
        payload: {
          error: JSON.stringify({
            runId: "09892c3f-bd1a-4c3d-9dab-38f40b3f7125",
            status: "ok",
            summary: "completed",
            result: {
              payloads: [],
              meta: {
                durationMs: 2425,
                agentMeta: {
                  sessionId: "afbe3143-26c9-4f65-9c2c-c3c2e22979cf",
                  provider: "minimax",
                  model: "MiniMax-M1",
                },
              },
            },
          }),
        },
        created_at: new Date().toISOString(),
      },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

function buildSystemInspectionRunWithTruncatedAgentError() {
  return {
    id: "run-system-2",
    instance_id: "oc_1",
    workflow_type: "system_inspection" as const,
    status: "failed",
    current_stage: "report",
    active_agent_id: "system-inspection-agent",
    overall_progress_percent: 100,
    input_payload: {
      instance_id: "oc_1",
    },
    error_message:
      '{"error": "{\\"runId\\": \\"3de1eeef-971e-4645-870d-af8878fdffd8\\", \\"status\\": \\"ok\\", \\"summary\\": \\"completed\\", \\"result\\": {\\"payloads\\": [], \\"meta\\": {\\"durationMs\\": 2423, \\"agentMeta\\": {\\"sessionId\\": \\"afbe3143-26c9-4f65-9c2c-c3c2e22979cf\\", \\"provider\\": \\"minimax\\", \\"model\\": \\"MiniMax-M1\\"}}..."}',
    stages: [],
    events: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

function buildCompletedSystemInspectionRunWithRepairHandoff() {
  return {
    id: "run-system-complete-1",
    instance_id: "oc_1",
    workflow_type: "system_inspection" as const,
    status: "completed",
    current_stage: "report",
    active_agent_id: "system-inspection-agent",
    overall_progress_percent: 100,
    input_payload: {
      instance_id: "oc_1",
      trigger_source: "manual",
    },
    final_system_inspection: {
      title: "系統巡檢與風險評估報告",
      inspection_summary: ["目前系統可用，但仍有 timeout 與 Telegram Markdown 穩定性風險。"],
      version_update_check: {
        current_version: "OpenClaw 2026.4.2 (d74a122)",
        latest_version: "2026.4.5",
        latest_version_status: "available",
        update_available: true,
        channel_label: "stable (default)",
        version_source: "openclaw_cli_update" as const,
        version_gap: "3 patch releases",
        release_summary: ["修復 plugin 載入穩定性問題"],
        breaking_changes: [],
        deprecations: [],
        compatibility_risks: ["升級前需確認 plugin manifest 與 workflow prompt 相容性"],
        affected_areas: {},
        upgrade_recommendation: "test_before_upgrade" as const,
        regression_test_checklist: ["workflow smoke test"],
        assumptions: [],
        verification_steps: [],
      },
      log_review: {
        summary: "近期主要問題集中在 timeout。",
        issues: [],
        log_window_hours: 24,
        inspected_log_count: 4,
      },
      high_priority_risks: [
        {
          issue_key: "timeout:dispatch_workflow_stage",
          category: "timeout",
          description: "workflow stage dispatch 偶發 timeout",
          frequency: 2,
          first_seen_at: "2026-04-05T09:10:00Z",
          last_seen_at: "2026-04-05T09:20:00Z",
          possible_root_causes: ["agent prompt 過大"],
          affected_components: ["workflow_dispatch"],
          impact_scope: "news brief 和 inspection 可能延遲",
          severity: "high" as const,
          fix_actions: ["縮小 stage prompt", "必要時提高 timeout"],
          optimization_actions: ["針對高成本 stage 使用獨立 timeout"],
          priority: "p1" as const,
          assumptions: [],
          verification_steps: ["重跑同類 workflow"],
        },
      ],
      fix_and_optimization_actions: ["先優化高成本 stage prompt", "建立 staging 升級回歸清單"],
      open_questions: [],
      recommended_execution_order: ["先修 timeout 熱點", "再於 staging 測 2026.4.5"],
      telegram_summary: "巡檢結論：先修 timeout，再測試升級到 2026.4.5。",
      markdown: "# 系統巡檢與風險評估報告",
      delivery_status: "delivered",
      delivery_target: "8351185582",
      delivery_error: null,
      repair_workflow_created: true,
      repair_workflow_run_id: "run-dev-1",
      repair_workflow_reason: null,
    },
    error_message: null,
    stages: [],
    events: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

function buildCompletedSystemInspectionRunWithoutRepairLink() {
  const payload = buildCompletedSystemInspectionRunWithRepairHandoff();
  return {
    ...payload,
    final_system_inspection: {
      ...payload.final_system_inspection,
      repair_workflow_run_id: null,
    },
  };
}

function buildDevelopmentRun(id: string, taskName: string) {
  return {
    id,
    instance_id: "oc_1",
    workflow_type: "development_execution" as const,
    status: "completed",
    current_stage: "handoff",
    active_agent_id: "main",
    overall_progress_percent: 100,
    input_payload: {
      instance_id: "oc_1",
      task_name: taskName,
      goal: "完成修復、驗證與交接",
    },
    final_development_report: {
      task_name: taskName,
      problem_definition: `${taskName} 的問題定義`,
      requirements_analysis: ["需求分析"],
      solution_design: ["方案設計"],
      technology_selection: [],
      task_breakdown_schedule: [],
      development_results: ["修復完成"],
      test_results: ["測試通過"],
      risks_and_todos: [],
      final_summary: `${taskName} 已完成`,
      delivery_status: "delivered",
      delivery_target: "channel_development",
      delivery_error: null,
      delivery_source: "development_config" as const,
      delivery_reason: "已使用 Development 專屬 Discord 設定。",
    },
    error_message: null,
    stages: [],
    events: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

function buildDailyNewsRunWithNestedInspectionReportError() {
  return {
    id: "run-news-1",
    instance_id: "oc_1",
    workflow_type: "news_brief" as const,
    status: "failed",
    current_stage: "brief",
    active_agent_id: "daily-news-brief-agent",
    overall_progress_percent: 100,
    input_payload: {
      instance_id: "oc_1",
      topic: "AI, OpenClaw, agent systems",
    },
    error_message:
      '{"error":"{\\"title\\":\\"系統巡檢與風險評估報告（第十三次——系統穩定，false positive 識別）\\",\\"inspection_summary\\":[\\"版本已對齊\\",\\"news_brief 全鏈路成功\\"],\\"markdown\\":\\"# report\\"}"}',
    stages: [],
    events: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

describe("OpenClaw pages", () => {
  afterEach(() => {
    mockSearch = "";
    vi.clearAllMocks();
  });

  it("shows loading then empty state on overview page", async () => {
    mockPathname = "/openclaw";

    let resolveHealthz:
      | ((value: {
          generatedAt: string;
          status: "ok";
          build: {
            name: string;
            version: string;
            node: string;
            readonlyMode: boolean;
            approvalActionsEnabled: boolean;
            approvalActionsDryRun: boolean;
            distIndexPath: string;
          };
          snapshot: {
            generatedAt: string;
            ageMs: number;
            status: "ok";
          };
          monitor: {
            status: "ok";
          };
        }) => void)
      | undefined;

    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockReturnValue(
      new Promise((resolve) => {
        resolveHealthz = resolve;
      })
    );
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockResolvedValue(buildUsageFixture());
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockResolvedValue(buildHallFixture());
    vi.mocked(controlCenterApi.fetchControlCenterTasks).mockResolvedValue(buildTasksFixture());
    vi.mocked(controlCenterApi.fetchControlCenterSessions).mockResolvedValue(buildSessionsFixture());

    render(<OpenClawOverviewPage />);

    expect(screen.getByText("正在同步 Control Center engine 的最新資料...")).toBeInTheDocument();

    resolveHealthz?.({
      generatedAt: new Date().toISOString(),
      status: "ok",
      build: {
        name: "control-center",
        version: "1.0.0",
        node: "v20.0.0",
        readonlyMode: true,
        approvalActionsEnabled: false,
        approvalActionsDryRun: true,
        distIndexPath: "/tmp/dist/index.js"
      },
      snapshot: {
        generatedAt: new Date().toISOString(),
        ageMs: 0,
        status: "ok"
      },
      monitor: {
        status: "ok"
      }
    });

    await waitFor(() => {
      expect(screen.getAllByText("OpenClaw Control Center").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Admin Tools").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Global status, burn, and next operator move.").length).toBeGreaterThan(0);
    });

    expect(screen.queryByText("Section Snapshot")).not.toBeInTheDocument();
    expect(screen.queryByText("Operator Guide")).not.toBeInTheDocument();
  });

  it("shows error state on overview page when API fails", async () => {
    mockPathname = "/openclaw";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockRejectedValue(new Error("overview failed"));
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockResolvedValue(buildUsageFixture());
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockResolvedValue(buildHallFixture());
    vi.mocked(controlCenterApi.fetchControlCenterTasks).mockResolvedValue(buildTasksFixture());
    vi.mocked(controlCenterApi.fetchControlCenterSessions).mockResolvedValue(buildSessionsFixture());

    render(<OpenClawOverviewPage />);

    await waitFor(() => {
      expect(screen.getAllByText("overview failed").length).toBeGreaterThan(0);
    });
  });

  it("keeps overview usable with inspector when one resource fails", async () => {
    mockPathname = "/openclaw";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockResolvedValue(buildHealthzFixture());
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockRejectedValue(new Error("usage failed"));
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockResolvedValue(buildHallFixture());
    vi.mocked(controlCenterApi.fetchControlCenterTasks).mockResolvedValue(buildTasksFixture());
    vi.mocked(controlCenterApi.fetchControlCenterSessions).mockResolvedValue(buildSessionsFixture());

    render(<OpenClawOverviewPage />);

    expect(await screen.findByText("Current status")).toBeInTheDocument();
    expect(screen.getByText("Timed jobs and heartbeat")).toBeInTheDocument();
    expect(screen.getByTestId("overview-executive-summary")).toBeInTheDocument();
    expect(screen.getByTestId("overview-needs-attention")).toBeInTheDocument();
    expect(screen.getByTestId("overview-live-activity")).toBeInTheDocument();
    expect(screen.getByTestId("overview-tools-drilldown")).toBeInTheDocument();
    expect(screen.getAllByText("usage failed").length).toBeGreaterThan(0);
  });

  it("keeps overview subscription detail short when telemetry is connected", async () => {
    mockPathname = "/openclaw";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockResolvedValue(buildHealthzFixture());
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockResolvedValue(buildConnectedUsageFixture());
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockResolvedValue(buildHallFixture());
    vi.mocked(controlCenterApi.fetchControlCenterTasks).mockResolvedValue(buildTasksFixture());
    vi.mocked(controlCenterApi.fetchControlCenterSessions).mockResolvedValue(buildSessionsFixture());

    render(<OpenClawOverviewPage />);

    expect(await screen.findByText("Platform signals")).toBeInTheDocument();
    const signalCard = screen.getByTestId("overview-tools-drilldown");
    expect(within(signalCard).getByText("Live subscription telemetry is connected.")).toBeInTheDocument();
    expect(within(signalCard).queryByText(/Provide one of:/)).not.toBeInTheDocument();
  });

  it("opens timed jobs modal from overview inspector and shows cron plus heartbeat rows", async () => {
    mockPathname = "/openclaw";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockResolvedValue({
      ...buildHealthzFixture(),
      monitor: {
        status: "warn",
        detail: "Task heartbeat worker is checking runtime heartbeats."
      }
    });
    vi.mocked(controlCenterApi.fetchControlCenterCronOverview).mockResolvedValue(buildCronOverviewFixture());
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockResolvedValue(buildUsageFixture());
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockResolvedValue(buildHallFixture());
    vi.mocked(controlCenterApi.fetchControlCenterTasks).mockResolvedValue(buildTasksFixture());
    vi.mocked(controlCenterApi.fetchControlCenterSessions).mockResolvedValue(buildSessionsFixture());

    render(<OpenClawOverviewPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Open timed jobs" }));

    const dialog = await screen.findByRole("dialog", { name: "Timed jobs and heartbeat" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("一眼看懂誰在什麼時間做什麼。")).toBeInTheDocument();
    expect(within(dialog).getAllByText("誰").length).toBeGreaterThan(0);
    expect(within(dialog).getByText("daily-news-brief-agent")).toBeInTheDocument();
    expect(within(dialog).getByText("system-inspection-agent")).toBeInTheDocument();
    expect(within(dialog).getByText("task-heartbeat-worker")).toBeInTheDocument();
    expect(within(dialog).getByText("收集與整理每日新聞簡報。")).toBeInTheDocument();
    expect(within(dialog).getByText("執行系統巡檢與風險評估。")).toBeInTheDocument();
    expect(within(dialog).getByText(/上次結果：error/)).toBeInTheDocument();
    expect(within(dialog).getByText(/錯誤：Channel is required when multiple channels are configured\./)).toBeInTheDocument();
  });

  it("closes timed jobs modal on escape", async () => {
    mockPathname = "/openclaw";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockResolvedValue(buildHealthzFixture());
    vi.mocked(controlCenterApi.fetchControlCenterCronOverview).mockResolvedValue(buildCronOverviewFixture());
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockResolvedValue(buildUsageFixture());
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockResolvedValue(buildHallFixture());
    vi.mocked(controlCenterApi.fetchControlCenterTasks).mockResolvedValue(buildTasksFixture());
    vi.mocked(controlCenterApi.fetchControlCenterSessions).mockResolvedValue(buildSessionsFixture());

    render(<OpenClawOverviewPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Open timed jobs" }));
    expect(await screen.findByRole("dialog", { name: "Timed jobs and heartbeat" })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Timed jobs and heartbeat" })).not.toBeInTheDocument();
    });
  });

  it("shows a path-specific hall degradation message without collapsing overview", async () => {
    mockPathname = "/openclaw";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockResolvedValue(buildHealthzFixture());
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockResolvedValue(buildUsageFixture());
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockRejectedValue(
      new Error("Hall API returned 500. Internal server error.")
    );
    vi.mocked(controlCenterApi.fetchControlCenterTasks).mockResolvedValue(buildTasksFixture());
    vi.mocked(controlCenterApi.fetchControlCenterSessions).mockResolvedValue(buildSessionsFixture());

    render(<OpenClawOverviewPage />);

    expect(await screen.findByText("Current status")).toBeInTheDocument();
    expect(screen.getAllByText("Hall API returned 500. Internal server error.").length).toBeGreaterThan(0);
    expect(screen.getByTestId("overview-tools-drilldown")).toBeInTheDocument();
  });

  it("renders usage page with partial failure instead of collapsing the page", async () => {
    mockPathname = "/openclaw/usage";
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockRejectedValue(new Error("usage unavailable"));

    render(<OpenClawUsagePage />);

    expect(await screen.findByText("Budget posture")).toBeInTheDocument();
    expect(screen.getAllByText("usage unavailable").length).toBeGreaterThan(0);
  });

  it("renders usage setup guidance without dumping raw path lists into the main card", async () => {
    mockPathname = "/openclaw/usage";
    vi.mocked(controlCenterApi.fetchControlCenterUsage).mockResolvedValue(buildUsageFixture());

    render(<OpenClawUsagePage />);

    expect(await screen.findByText("Budget posture")).toBeInTheDocument();
    expect(screen.getAllByText("狀態：not_connected").length).toBeGreaterThan(0);
    expect(screen.getByText("近 30 天：$0.00")).toBeInTheDocument();
    expect(screen.getByText("尚未設定月預算來源。")).toBeInTheDocument();
    expect(screen.getByText("尚未接入 provider subscription snapshot。")).toBeInTheDocument();
    expect(screen.getAllByText("開啟 budget template").length).toBeGreaterThan(0);
    expect(screen.getAllByText("開啟 subscription template").length).toBeGreaterThan(0);
    expect(screen.getByText("設定月預算上限")).toBeInTheDocument();
    expect(screen.getByText("建立 subscription snapshot")).toBeInTheDocument();
    expect(screen.queryByText("config: /tmp/runtime/usage-budget.json")).not.toBeInTheDocument();
    expect(screen.queryByText("推薦存放路徑：/tmp/runtime/usage-budget.json")).not.toBeInTheDocument();
    expect(screen.queryByText("/tmp/subscription-a.json")).not.toBeInTheDocument();
  });

  it("renders staff page with hall data even if sessions fail", async () => {
    mockPathname = "/openclaw/staff";
    vi.mocked(controlCenterApi.fetchControlCenterStaffSummary).mockResolvedValue(buildStaffSummaryFixture());

    render(<OpenClawStaffPage />);

    expect(await screen.findByText("Role view")).toBeInTheDocument();
    expect(screen.getByText("Chief Lobster")).toBeInTheDocument();
    expect(screen.getByText("主控與協調")).toBeInTheDocument();
    expect(screen.getByText("Published the latest execution handoff.")).toBeInTheDocument();
    expect(screen.getByTestId("staff-sessions-details")).not.toHaveAttribute("open");
  });

  it("keeps staff page visible when staff summary fails", async () => {
    mockPathname = "/openclaw/staff";
    vi.mocked(controlCenterApi.fetchControlCenterStaffSummary).mockRejectedValue(new Error("staff summary unavailable"));

    render(<OpenClawStaffPage />);

    expect(await screen.findByText("Role view")).toBeInTheDocument();
    expect(screen.getAllByText("staff summary unavailable").length).toBeGreaterThan(0);
  });

  it("renders collaboration page as a clear live snapshot", async () => {
    mockPathname = "/openclaw/collaboration";
    vi.mocked(controlCenterApi.fetchControlCenterHall).mockResolvedValue(buildBusyHallFixture());

    render(<OpenClawCollaborationPage />);

    expect(await screen.findByText("Collaboration health")).toBeInTheDocument();
    expect(screen.getByText("Live coordination")).toBeInTheDocument();
    expect(screen.getByText("Who is working with whom")).toBeInTheDocument();
    expect(screen.getByText("Builder Panda 與 Chief Lobster 正在同步交接與實作細節。")).toBeInTheDocument();
    expect(screen.getByText(/Chief Lobster、Builder Panda 目前主要圍繞/)).toBeInTheDocument();
    expect(screen.getAllByText("Release handoff").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Builder Panda").length).toBeGreaterThan(0);
    expect(screen.getByText("Support Otter")).toBeInTheDocument();
    expect(screen.getByText("Most active thread")).toBeInTheDocument();
  });

  it("renders diagnostics cards on settings page", async () => {
    mockPathname = "/openclaw/settings";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockResolvedValue({
      generatedAt: new Date().toISOString(),
      status: "warn",
      build: {
        name: "control-center",
        version: "1.0.0",
        node: "v20.0.0",
        readonlyMode: true,
        approvalActionsEnabled: false,
        approvalActionsDryRun: true,
        distIndexPath: "/tmp/dist/index.js"
      },
      snapshot: {
        generatedAt: new Date().toISOString(),
        ageMs: 1200,
        status: "warn"
      },
      monitor: {
        status: "warn"
      }
    });
    vi.mocked(controlCenterApi.fetchControlCenterDiagnostics).mockResolvedValue({
      ok: true,
      diagnostics: {
        generatedAt: new Date().toISOString(),
        gateway: {
          configuredUrl: "ws://127.0.0.1:18789",
          overallStatus: "warn"
        },
        openclaw: {
          status: "ok",
          currentVersion: "2026.4.1",
          latestVersion: "2026.4.1",
          updateAvailable: false
        },
        tokens: {
          localTokenAuthRequired: true,
          entries: [
            {
              key: "LOCAL_API_TOKEN",
              present: false,
              note: "只顯示存在與否"
            }
          ]
        },
        recentIssues: []
      }
    });

    render(<OpenClawSettingsPage />);

    expect(await screen.findByText("Safety Posture")).toBeInTheDocument();
    expect(screen.getByText("Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("LOCAL_API_TOKEN")).toBeInTheDocument();
  });

  it("keeps settings page visible when diagnostics fail", async () => {
    mockPathname = "/openclaw/settings";
    vi.mocked(controlCenterApi.fetchControlCenterHealthz).mockResolvedValue(buildHealthzFixture("warn"));
    vi.mocked(controlCenterApi.fetchControlCenterDiagnostics).mockRejectedValue(new Error("diagnostics unavailable"));

    render(<OpenClawSettingsPage />);

    expect(await screen.findByText("Safety Posture")).toBeInTheDocument();
    expect(screen.getByText("Diagnostics")).toBeInTheDocument();
    expect(screen.getAllByText("diagnostics unavailable").length).toBeGreaterThan(0);
  });

  it("renders empty documents workbench state", async () => {
    mockPathname = "/openclaw/docs";
    vi.mocked(controlCenterApi.fetchControlCenterFiles).mockResolvedValue({
      ok: true,
      scope: "workspace",
      count: 0,
      files: []
    });

    render(<OpenClawDocsPage />);

    expect(await screen.findByText("Workspace files")).toBeInTheDocument();
    expect(screen.getByText("目前這個 scope 尚未回傳可用檔案。")).toBeInTheDocument();
  });

  it("renders documents workbench as a focused browser with facet switching and search", async () => {
    mockPathname = "/openclaw/docs";
    vi.mocked(controlCenterApi.fetchControlCenterFiles).mockResolvedValue(buildWorkspaceFilesFixture());

    render(<OpenClawDocsPage />);

    expect(await screen.findByText("Workspace files")).toBeInTheDocument();
    expect(screen.getByText("Main files")).toBeInTheDocument();
    expect(screen.getByText("Runbook")).toBeInTheDocument();
    expect(screen.queryByText("/tmp/docs/RUNBOOK.md")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Facet"), { target: { value: "builder-panda" } });
    expect(screen.getByText("Builder Notes")).toBeInTheDocument();
    expect(screen.queryByText("Runbook")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "workflow" } });
    expect(screen.getByText("Builder Notes")).toBeInTheDocument();
    expect(screen.queryByText("Architecture")).not.toBeInTheDocument();
  });

  it("renders memory workbench error inline", async () => {
    mockPathname = "/openclaw/memory";
    vi.mocked(controlCenterApi.fetchControlCenterFiles).mockRejectedValue(new Error("memory unavailable"));

    render(<OpenClawMemoryPage />);

    expect(await screen.findByText("Memory files")).toBeInTheDocument();
    expect(screen.getAllByText("memory unavailable").length).toBeGreaterThan(0);
  });

  it("locks only the clicked device action button while action is pending", async () => {
    mockPathname = "/openclaw/devices";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDevices).mockResolvedValue([
      {
        id: "device_pending",
        name: "Alice iPhone",
        status: "pending",
        platform: "ios",
        pending_action: "approve",
        metadata: {}
      }
    ]);

    let resolveAction: (() => void) | undefined;
    vi.mocked(api.runOpenClawDeviceAction).mockReturnValue(
      new Promise((resolve) => {
        resolveAction = () => resolve({});
      })
    );

    render(<OpenClawDevicesPage />);

    const approveButton = await screen.findByRole("button", { name: "approve" });
    fireEvent.click(approveButton);

    expect(screen.getByRole("button", { name: "approve 中..." })).toBeDisabled();

    resolveAction?.();

    await waitFor(() => {
      expect(screen.getByText("Device approve 已完成。")).toBeInTheDocument();
    });
  });

  it("renders paired devices returned by the API", async () => {
    mockPathname = "/openclaw/devices";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDevices).mockResolvedValue([
      {
        id: "device_paired",
        name: "Unknown Device",
        status: "paired",
        platform: "darwin",
        pending_action: null,
        metadata: {
          clientId: "openclaw-control-ui"
        }
      }
    ]);

    render(<OpenClawDevicesPage />);

    expect(await screen.findByText("Unknown Device")).toBeInTheDocument();
    expect(screen.getByText("darwin")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "revoke" })).toBeInTheDocument();
  });

  it("toggles agent search capability from the agents page", async () => {
    mockPathname = "/openclaw/agents";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawAgents)
      .mockResolvedValueOnce([
        {
          id: "support-agent",
          name: "Support Agent",
          status: "ready",
          channel_count: 0,
          metadata: {
            capabilities: {
              search_api: {
                enabled: false,
                plugin_ready: false,
                plugin_enabled: false,
                bridge_ready: false
              }
            }
          }
        }
      ])
      .mockResolvedValueOnce([
        {
          id: "support-agent",
          name: "Support Agent",
          status: "ready",
          channel_count: 0,
          metadata: {
            capabilities: {
              search_api: {
                enabled: false,
                plugin_ready: false,
                plugin_enabled: false,
                bridge_ready: false
              }
            }
          }
        }
      ])
      .mockResolvedValueOnce([
        {
          id: "support-agent",
          name: "Support Agent",
          status: "ready",
          channel_count: 0,
          metadata: {
            capabilities: {
              search_api: {
                enabled: true,
                plugin_ready: true,
                plugin_enabled: true,
                bridge_ready: true,
                plugin_id: "project-search",
                last_sync_message: "原生搜索工具已就緒"
              }
            }
          }
        }
      ]);
    vi.mocked(api.updateOpenClawAgentSearchCapability).mockResolvedValue({
      id: "cap_1",
      instance_id: "oc_1",
      agent_id: "support-agent",
      capability_key: "search_api",
      is_enabled: true,
      config: {},
      native_plugin_id: "project-search",
      native_plugin_ready: true,
      native_plugin_enabled: true,
      bridge_ready: true,
      last_sync_status: "success",
      last_sync_message: "原生搜索工具已就緒",
      workspace_synced: false,
      message: "原生搜索工具已就緒",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });

    render(<OpenClawAgentsPage />);

    const toggleButton = await screen.findByRole("button", { name: "啟用搜索能力" });
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(screen.getByText("原生搜索工具已就緒")).toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: "停用搜索能力" })).toBeInTheDocument();
    expect(screen.getByText("project-search", { exact: false })).toBeInTheDocument();
  });

  it("shows prerequisite guard on agents page when no instances exist", async () => {
    mockPathname = "/openclaw/agents";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawAgentsPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，這裡才能建立與管理 Agent。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "建立 Agent" })).toBeDisabled();
  });

  it("shows prerequisite guard on devices page when no instances exist", async () => {
    mockPathname = "/openclaw/devices";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawDevicesPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，這裡才會出現 Device 與授權操作。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新整理" })).toBeDisabled();
  });

  it("shows prerequisite guard on workflow page when no instances exist", async () => {
    mockPathname = "/openclaw/workflow";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawWorkflowPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，再配置主控秘書與多專職 agent。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存 Workflow 設定" })).toBeDisabled();
  });

  it("shows prerequisite guard on config page when no instances exist", async () => {
    mockPathname = "/openclaw/config";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawConfigPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，這裡才能讀取與寫入 Config。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "讀取" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Validate" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
  });

  it("shows prerequisite guard on daily news page when no instances exist", async () => {
    mockPathname = "/openclaw/daily-news";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawDailyNewsPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，再設定 Daily News Brief。")).toBeInTheDocument();
    expect(screen.getByText("定時來源：OpenClaw cron。手動執行不受每日自動排程去重限制。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存設定" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "手動執行今日簡報" })).toBeDisabled();
  });

  it("shows prerequisite guard on system inspection page when no instances exist", async () => {
    mockPathname = "/openclaw/system-inspection";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawSystemInspectionPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，再設定 System Inspection。")).toBeInTheDocument();
    expect(screen.getByText("定時來源：OpenClaw cron。手動執行不受每日自動排程去重限制。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存設定" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "手動執行巡檢" })).toBeDisabled();
  });

  it("shows the linked development workflow when system inspection auto-hands off repair work", async () => {
    mockPathname = "/openclaw/system-inspection";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawSystemInspectionConfig).mockResolvedValue(DEFAULT_SYSTEM_INSPECTION_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([buildCompletedSystemInspectionRunWithRepairHandoff()]);

    render(<OpenClawSystemInspectionPage />);

    expect(await screen.findByText("已自動交辦 Fullstack Engineer Agent。")).toBeInTheDocument();
    const developmentLink = screen.getByRole("link", { name: "Development Workflow：run-dev-1" });
    expect(developmentLink).toHaveAttribute("href", "/openclaw/development?instanceId=oc_1&runId=run-dev-1");
  });

  it("keeps repair workflow text non-clickable when the linked development run id is missing", async () => {
    mockPathname = "/openclaw/system-inspection";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawSystemInspectionConfig).mockResolvedValue(DEFAULT_SYSTEM_INSPECTION_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([buildCompletedSystemInspectionRunWithoutRepairLink()]);

    render(<OpenClawSystemInspectionPage />);

    expect(await screen.findByText("已自動交辦 Fullstack Engineer Agent。")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Development Workflow/ })).not.toBeInTheDocument();
  });

  it("summarizes nested agent runtime payloads on system inspection page instead of dumping raw JSON", async () => {
    mockPathname = "/openclaw/system-inspection";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawSystemInspectionConfig).mockResolvedValue(DEFAULT_SYSTEM_INSPECTION_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([buildSystemInspectionRunWithNestedAgentError()]);

    render(<OpenClawSystemInspectionPage />);

    expect(await screen.findAllByText("Agent 已完成執行，但沒有回傳可解析文字內容 (provider minimax / model MiniMax-M1 / 耗時約 2.4 秒)。")).not.toHaveLength(0);
    expect(screen.getAllByText("查看原始 payload").length).toBeGreaterThan(0);
    expect(screen.getAllByText("狀態：ok").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Provider：minimax").length).toBeGreaterThan(0);
  });

  it("deep-links into the matching development workflow from query params", async () => {
    mockPathname = "/openclaw/development";
    mockSearch = "instanceId=oc_1&runId=run-dev-linked";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([
      buildDevelopmentRun("run-dev-latest", "最新工程流程"),
      buildDevelopmentRun("run-dev-linked", "巡檢交辦修復流程"),
    ]);

    render(<OpenClawDevelopmentPage />);

    expect(await screen.findByText("已定位到 System Inspection 自動交辦的工程流程。")).toBeInTheDocument();
    expect(screen.getAllByText("巡檢交辦修復流程").length).toBeGreaterThan(0);
  });

  it("fetches the linked development workflow when it is not included in the initial list", async () => {
    mockPathname = "/openclaw/development";
    mockSearch = "instanceId=oc_1&runId=run-dev-linked";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([
      buildDevelopmentRun("run-dev-latest", "最新工程流程"),
    ]);
    vi.mocked(api.fetchWorkflowRun).mockResolvedValue(buildDevelopmentRun("run-dev-linked", "補抓的工程流程"));

    render(<OpenClawDevelopmentPage />);

    expect(await screen.findByText("已定位到 System Inspection 自動交辦的工程流程。")).toBeInTheDocument();
    expect(screen.getAllByText("補抓的工程流程").length).toBeGreaterThan(0);
  });

  it("falls back to the latest development workflow when the linked run id is invalid", async () => {
    mockPathname = "/openclaw/development";
    mockSearch = "instanceId=oc_1&runId=run-dev-missing";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([
      buildDevelopmentRun("run-dev-latest", "最新工程流程"),
    ]);
    vi.mocked(api.fetchWorkflowRun).mockRejectedValue(new Error("run not found"));

    render(<OpenClawDevelopmentPage />);

    expect(await screen.findByText("找不到指定的 Development Workflow，已回到最新工程流程。")).toBeInTheDocument();
    expect(screen.getAllByText("最新工程流程").length).toBeGreaterThan(0);
  });

  it("loads and saves development discord delivery config", async () => {
    mockPathname = "/openclaw/development";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDevelopmentConfig).mockResolvedValue(DEFAULT_DEVELOPMENT_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([]);
    vi.mocked(api.updateOpenClawDevelopmentConfig).mockResolvedValue({
      ...DEFAULT_DEVELOPMENT_CONFIG_FIXTURE,
      discord_channel_id: "channel_updated",
      last_delivery_status: "failed",
      last_delivery_error: "discord send failed",
    });

    render(<OpenClawDevelopmentPage />);

    expect(await screen.findByDisplayValue("channel_development")).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("channel_development"), { target: { value: "channel_updated" } });
    fireEvent.click(screen.getByRole("button", { name: /儲存/ }));

    await waitFor(() => {
      expect(api.updateOpenClawDevelopmentConfig).toHaveBeenCalledWith({
        instance_id: "oc_1",
        enabled: true,
        delivery_channel: "discord",
        discord_channel_id: "channel_updated",
      });
    });
    expect(await screen.findByText("Development Discord 匯報設定已更新。")).toBeInTheDocument();
  });

  it("shows runtime route fallback hint when development config is missing", async () => {
    mockPathname = "/openclaw/development";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDevelopmentConfig).mockResolvedValue({
      ...DEFAULT_DEVELOPMENT_CONFIG_FIXTURE,
      enabled: false,
      discord_channel_id: "",
      last_run_id: null,
      last_delivery_status: null,
      config_source: "default",
      effective_delivery_source: "runtime_route",
      effective_discord_channel_id: "1490511097147687035",
      effective_delivery_reason: "未找到 Development 專屬設定，已回退使用 Discord #develop route（1490511097147687035）。",
    });
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([]);

    render(<OpenClawDevelopmentPage />);

    expect(await screen.findByText("此 Instance 尚未設定 Development Discord 匯報，將回退使用 Discord #develop route（1490511097147687035）。")).toBeInTheDocument();
    expect(screen.getByText("有效來源：runtime_route")).toBeInTheDocument();
    expect(screen.getByText("有效目標：1490511097147687035")).toBeInTheDocument();
  });

  it("summarizes truncated agent runtime errors in the system inspection message banner", async () => {
    mockPathname = "/openclaw/system-inspection";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawSystemInspectionConfig).mockResolvedValue(DEFAULT_SYSTEM_INSPECTION_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockRejectedValue(new Error(buildSystemInspectionRunWithTruncatedAgentError().error_message ?? "failed"));

    render(<OpenClawSystemInspectionPage />);

    expect(await screen.findByText("System Inspection agent 已完成執行，但沒有回傳可解析文字內容 (provider minimax / model MiniMax-M1 / 耗時約 2.4 秒)。")).toBeInTheDocument();
    expect(screen.queryByText(/3de1eeef-971e-4645-870d-af8878fdffd8/)).not.toBeInTheDocument();
  });

  it("summarizes truncated agent runtime errors in the daily news message banner", async () => {
    mockPathname = "/openclaw/daily-news";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDailyNewsConfig).mockResolvedValue(DEFAULT_DAILY_NEWS_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockRejectedValue(new Error(buildSystemInspectionRunWithTruncatedAgentError().error_message ?? "failed"));

    render(<OpenClawDailyNewsPage />);

    expect(await screen.findByText("Daily News Brief agent 已完成執行，但沒有回傳可解析文字內容 (provider minimax / model MiniMax-M1 / 耗時約 2.4 秒)。")).toBeInTheDocument();
    expect(screen.queryByText(/3de1eeef-971e-4645-870d-af8878fdffd8/)).not.toBeInTheDocument();
  });

  it("summarizes nested inspection report payloads on the daily news result panel instead of dumping raw JSON", async () => {
    mockPathname = "/openclaw/daily-news";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDailyNewsConfig).mockResolvedValue(DEFAULT_DAILY_NEWS_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([buildDailyNewsRunWithNestedInspectionReportError()]);

    render(<OpenClawDailyNewsPage />);

    expect(await screen.findByText(/Daily News Brief agent 回傳了結構化巡檢報告/)).toBeInTheDocument();
    expect(screen.getAllByText(/系統巡檢與風險評估報告（第十三次/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("查看原始 payload").length).toBeGreaterThan(0);
  });

  it("shows agent success and disabled wake state on actions page", async () => {
    mockPathname = "/openclaw/actions";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.dispatchOpenClawAgentHook).mockResolvedValue({ accepted: true });

    render(<OpenClawActionsPage />);

    const agentButton = await screen.findByRole("button", { name: "送出 Agent Hook" });
    fireEvent.click(agentButton);

    await waitFor(() => {
      expect(screen.getByText(/Agent Hook 派發完成/)).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Wake Hook 目前未開放" })).toBeDisabled();
    expect(
      screen.getByText("目前這個 OpenClaw 版本沒有穩定可用的 wake 派發入口。若要測試任務派發，請先使用左側的 Agent Hook。")
    ).toBeInTheDocument();
  });

  it("shows prerequisite guard on actions page when no instances exist", async () => {
    mockPathname = "/openclaw/actions";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawActionsPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，這裡才能手動派發 Agent Hook。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "送出 Agent Hook" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Wake Hook 目前未開放" })).toBeDisabled();
  });

  it("shows prerequisite guard on logs page when no instances exist", async () => {
    mockPathname = "/openclaw/logs";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawLogsPage />);

    expect(await screen.findByText("先建立 OpenClaw Instance，這裡才能查看 Gateway logs。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新整理" })).toBeDisabled();
  });

  it("keeps instances page usable for first-time setup", async () => {
    mockPathname = "/openclaw/instances";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([]);

    render(<OpenClawInstancesPage />);

    expect(await screen.findByText("尚未建立任何 OpenClaw Instance。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "建立 Instance" })).toBeEnabled();
  });

  it("renders empty knowledge source state", async () => {
    mockPathname = "/openclaw/knowledge";
    vi.mocked(api.fetchSources).mockResolvedValue([]);
    vi.mocked(api.fetchKnowledgeIngestionRuns).mockResolvedValue([]);
    vi.mocked(api.fetchDocumentVersions).mockResolvedValue([]);

    render(<OpenClawKnowledgePage />);

    expect(await screen.findByText("尚無外部知識來源，第一次手動接入後就會自動生成 reusable source。")).toBeInTheDocument();
    expect(screen.getByText("尚無 knowledge ingestion run，先從上方表單執行一次接入。")).toBeInTheDocument();
  });

  it("renders development workflow console", async () => {
    mockPathname = "/openclaw/development";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDevelopmentConfig).mockResolvedValue(DEFAULT_DEVELOPMENT_CONFIG_FIXTURE);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([]);

    render(<OpenClawDevelopmentPage />);

    expect(await screen.findByRole("heading", { name: "Development" })).toBeInTheDocument();
    expect(screen.getByText("工程任務建立")).toBeInTheDocument();
    expect(screen.getByText("最近投遞狀態：delivered")).toBeInTheDocument();
    expect(screen.getByText("有效來源：development_config")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /儲存/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "建立工程任務" })).toBeInTheDocument();
  });
});
