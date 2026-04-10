"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useState } from "react";

import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { StaffRoleLottie } from "@/components/lottie/staff-role-lottie";
import {
  fetchControlCenterCronOverview,
  fetchControlCenterDiagnostics,
  fetchControlCenterFiles,
  fetchControlCenterHall,
  fetchControlCenterHealthz,
  fetchControlCenterSessions,
  fetchControlCenterStaffSummary,
  fetchControlCenterTasks,
  fetchControlCenterUsage
} from "@/lib/control-center-api";
import type {
  ControlCenterCronOverviewResponse,
  ControlCenterDiagnosticsResponse,
  ControlCenterFilesResponse,
  ControlCenterHallResponse,
  ControlCenterHealthzPayload,
  ControlCenterSectionKey,
  ControlCenterStaffSummaryResponse,
  ControlCenterSessionsResponse,
  ControlCenterTasksResponse,
  ControlCenterUsageResponse
} from "@/lib/control-center-types";
import { formatDateTime } from "@/lib/utils";

interface ControlCenterSectionPageProps {
  section: ControlCenterSectionKey;
}

interface SectionConfig {
  title: string;
  description: string;
  roles: Array<{
    name: string;
    tagline: string;
    status: string;
    quote: string;
  }>;
}

interface SectionState {
  healthz: Loadable<ControlCenterHealthzPayload>;
  cronOverview: Loadable<ControlCenterCronOverviewResponse>;
  usage: Loadable<ControlCenterUsageResponse>;
  sessions: Loadable<ControlCenterSessionsResponse>;
  staffSummary: Loadable<ControlCenterStaffSummaryResponse>;
  tasks: Loadable<ControlCenterTasksResponse>;
  hall: Loadable<ControlCenterHallResponse>;
  workspaceFiles: Loadable<ControlCenterFilesResponse>;
  memoryFiles: Loadable<ControlCenterFilesResponse>;
  diagnostics: Loadable<ControlCenterDiagnosticsResponse>;
}

type LoadStatus = "idle" | "loading" | "ready" | "error";

interface Loadable<T> {
  status: LoadStatus;
  data?: T;
  error?: string;
}

interface TimedJobRow {
  id: string;
  channel: "cron" | "heartbeat";
  who: string;
  what: string;
  note?: string;
  schedule: string;
  nextRun: string;
  status: string;
}

const SECTION_CONFIG: Record<ControlCenterSectionKey, SectionConfig> = {
  overview: {
    title: "OpenClaw Control Center",
    description:
      "融合後的新主控頁以 claw_kaisya 的像素工作台呈現，但區塊順序、欄位比例與主觀測節奏對齊 `.openclaw-control-center-main`。",
    roles: [
      {
        name: "Chief Lobster",
        tagline: "全局判讀",
        status: "running",
        quote: "我先看健康、風險、當前協作，再決定要不要深入管理工具。"
      },
      {
        name: "Ops Lobster",
        tagline: "連線巡檢",
        status: "ready",
        quote: "Gateway、snapshot、runtime 只要有一個變差，我會先把原因攤開。"
      },
      {
        name: "Hall Steward",
        tagline: "協作節奏",
        status: "ready",
        quote: "多人討論、任務排程與 task room 都會回到這個入口彙總。"
      }
    ]
  },
  usage: {
    title: "Usage & Budget",
    description: "用量頁先給期間視窗與 budget posture，再往下看訂閱與 connector 補線項。",
    roles: [
      {
        name: "Budget Lobster",
        tagline: "成本警戒",
        status: "running",
        quote: "我會先看 30d burn 與 budget status，再看哪個 connector 沒接上。"
      },
      {
        name: "Quota Keeper",
        tagline: "配額視窗",
        status: "ready",
        quote: "沒有訂閱或 Codex 資料時，我會把空訊號標成降級，而不是假裝壞掉。"
      }
    ]
  },
  staff: {
    title: "Staff & Sessions",
    description: "把目前可見會話視為工作現場，區分誰在跑、誰只是排隊、誰最近有輸出。",
    roles: [
      {
        name: "Staff Radar",
        tagline: "工作現場",
        status: "running",
        quote: "我只看當前 session 證據，不把歷史殘影誤判成還在工作。"
      },
      {
        name: "Queue Watcher",
        tagline: "待命與排隊",
        status: "ready",
        quote: "沒有 live session 的人會被歸回 next up，不會和 active 混在一起。"
      }
    ]
  },
  collaboration: {
    title: "Collaboration Snapshot",
    description: "協作頁沿用 hall-first 的資訊優先順序，三欄呈現 threads、timeline 與 context。",
    roles: [
      {
        name: "Hall Lead",
        tagline: "共享討論",
        status: "running",
        quote: "我先把共享線程整理成可決策的摘要，再看誰接手執行。"
      },
      {
        name: "Review Keeper",
        tagline: "交接節奏",
        status: "ready",
        quote: "assign、handoff、review 的節奏會直接影響整個大廳的可信度。"
      }
    ]
  },
  hall: {
    title: "Hall Timeline",
    description: "Hall 頁對齊 reference 的三欄 shared chat layout，左 threads、中 timeline、右 context。",
    roles: [
      {
        name: "Thread Curator",
        tagline: "訊息流",
        status: "running",
        quote: "我會把最近對話與 task card 以 thread-first 方式呈現。"
      },
      {
        name: "Task Narrator",
        tagline: "任務節點",
        status: "ready",
        quote: "每張卡都要看得出目前 stage、owner 與下一步。"
      }
    ]
  },
  tasks: {
    title: "Tasks & Execution",
    description: "任務頁改成 task-room-style workbench，先看房間清單，再看 timeline 與 room context。",
    roles: [
      {
        name: "Task Steward",
        tagline: "任務可信度",
        status: "running",
        quote: "我會先區分 tracked tasks、runtime evidence 與待跟進項。"
      },
      {
        name: "Execution Clerk",
        tagline: "鏈路追蹤",
        status: "ready",
        quote: "roomId、sessionKeys 與 owner 會一起決定任務有沒有真的跑起來。"
      }
    ]
  },
  docs: {
    title: "Documents Workbench",
    description: "文件區先接上 workspace file index，以 reference 的主清單加側欄 context 方式呈現。",
    roles: [
      {
        name: "Doc Keeper",
        tagline: "共用文件",
        status: "running",
        quote: "我先把共用 docs 目錄與可編輯工作檔列清楚，後續再疊編輯器。"
      },
      {
        name: "Context Archivist",
        tagline: "脈絡保存",
        status: "ready",
        quote: "文件區要直接對真實檔案，而不是複製一份假的快照。"
      }
    ]
  },
  memory: {
    title: "Memory Workbench",
    description: "記憶區先呈現 memory scope 檔案與維護 context，作為後續 agent memory 工作台基底。",
    roles: [
      {
        name: "Memory Keeper",
        tagline: "長短期記憶",
        status: "running",
        quote: "我要先把當前可見 memory files 對上真實 agent roster。"
      },
      {
        name: "Recall Guard",
        tagline: "健康檢查",
        status: "ready",
        quote: "哪個 agent 的記憶可讀、可搜尋、可維護，這裡都要看得出來。"
      }
    ]
  },
  settings: {
    title: "Settings & Diagnostics",
    description: "設定頁先顯示安全姿態與關鍵狀態，再往下看 diagnostics、token gate 與近期異常。",
    roles: [
      {
        name: "Safety Auditor",
        tagline: "風險摘要",
        status: "running",
        quote: "高風險開關有沒有關好，我會直接告訴你，不讓你自己猜。"
      },
      {
        name: "Connector Scout",
        tagline: "接線完成度",
        status: "ready",
        quote: "哪些空訊號只是未接線、哪些是真故障，要明確分開。"
      }
    ]
  }
};

export function ControlCenterSectionPage({ section }: ControlCenterSectionPageProps) {
  const config = SECTION_CONFIG[section];
  const [state, setState] = useState<SectionState>(() => createInitialSectionState(section));
  const [timedJobsOpen, setTimedJobsOpen] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadSection() {
      setState(createInitialSectionState(section));
      const nextState = createInitialSectionState(section);

      if (section === "overview") {
        const [healthz, cronOverview, usage, hall, tasks, sessions] = await Promise.allSettled([
          fetchControlCenterHealthz(),
          fetchControlCenterCronOverview(),
          fetchControlCenterUsage(),
          fetchControlCenterHall(),
          fetchControlCenterTasks(),
          fetchControlCenterSessions()
        ]);
        nextState.healthz = fromSettledResult(healthz, "無法載入 healthz");
        nextState.cronOverview = fromSettledResult(cronOverview, "無法載入 cron overview");
        nextState.usage = fromSettledResult(usage, "無法載入 usage snapshot");
        nextState.hall = fromSettledResult(hall, "無法載入 hall snapshot");
        nextState.tasks = fromSettledResult(tasks, "無法載入 tasks snapshot");
        nextState.sessions = fromSettledResult(sessions, "無法載入 sessions snapshot");
      }

      if (section === "usage") {
        nextState.usage = await loadResource(fetchControlCenterUsage, "無法載入 usage snapshot");
      }

      if (section === "staff") {
        nextState.staffSummary = await loadResource(fetchControlCenterStaffSummary, "無法載入 staff summary");
      }

      if (section === "collaboration" || section === "hall") {
        nextState.hall = await loadResource(fetchControlCenterHall, "無法載入 hall snapshot");
      }

      if (section === "tasks") {
        nextState.tasks = await loadResource(fetchControlCenterTasks, "無法載入 tasks snapshot");
      }

      if (section === "docs") {
        nextState.workspaceFiles = await loadResource(
          () => fetchControlCenterFiles("workspace"),
          "無法取得檔案清單"
        );
      }

      if (section === "memory") {
        nextState.memoryFiles = await loadResource(
          () => fetchControlCenterFiles("memory"),
          "無法取得記憶檔案清單"
        );
      }

      if (section === "settings") {
        const [healthz, diagnostics] = await Promise.allSettled([
          fetchControlCenterHealthz(),
          fetchControlCenterDiagnostics()
        ]);
        nextState.healthz = fromSettledResult(healthz, "無法載入 healthz");
        nextState.diagnostics = fromSettledResult(diagnostics, "無法載入 diagnostics bundle");
      }

      if (!isCancelled) {
        setState(nextState);
      }
    }

    void loadSection();

    return () => {
      isCancelled = true;
    };
  }, [section]);

  useEffect(() => {
    if (!timedJobsOpen) return undefined;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setTimedJobsOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [timedJobsOpen]);

  return (
    <OpenClawPageShell
      title={config.title}
      description={config.description}
      roles={config.roles}
      sectionGroup="Control Center"
      sectionLabel={config.title}
      inspector={section === "overview" ? renderOverviewInspector(state, () => setTimedJobsOpen(true)) : undefined}
      childrenClassName={section === "overview" ? "space-y-5" : undefined}
    >
      {shouldShowLoadingBanner(section, state) ? (
        <PixelCard title="正在同步" eyebrow="Loading">
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            正在同步 Control Center engine 的最新資料...
          </div>
        </PixelCard>
      ) : null}

      {section === "overview" ? renderOverview(state) : null}
      {section === "usage" ? renderUsage(state.usage) : null}
      {section === "staff" ? renderStaff(state.staffSummary) : null}
      {section === "collaboration" ? renderCollaboration(state.hall) : null}
      {section === "hall" ? renderHall(state.hall) : null}
      {section === "tasks" ? renderTasks(state.tasks) : null}
      {section === "docs" ? renderFilesWorkbench("workspace", state.workspaceFiles) : null}
      {section === "memory" ? renderFilesWorkbench("memory", state.memoryFiles) : null}
      {section === "settings" ? renderSettings(state.healthz, state.diagnostics) : null}
      {section === "overview" ? (
        <TimedJobsModal
          open={timedJobsOpen}
          onClose={() => setTimedJobsOpen(false)}
          rows={buildTimedJobRows(state.cronOverview, state.healthz)}
        />
      ) : null}
    </OpenClawPageShell>
  );
}

function renderOverview(state: SectionState) {
  const healthz = state.healthz.data;
  const usage = state.usage.data?.usage;
  const hall = state.hall.data;
  const tasks = state.tasks.data;
  const sessions = state.sessions.data;

  return (
    <>
      <div data-testid="overview-executive-summary" className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <PixelCard title="Executive summary" eyebrow="Overview">
          <div className="space-y-4">
            {renderLoadablePanel(state.healthz, {
              loadingText: "等待 health snapshot...",
              emptyText: "目前沒有可用的 healthz snapshot。",
              render: (current) => (
                <div className="rounded-[1.25rem] border border-slate-200 bg-white/90 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Current posture</p>
                  <p className="mt-3 text-2xl font-black tracking-[0.06em] text-ink">{current.status}</p>
                  <p className="mt-3 text-sm leading-6 text-slate-700">
                    {`Snapshot ${current.snapshot.status}，monitor ${current.monitor.status}，readonly=${String(current.build.readonlyMode)}。`}
                  </p>
                </div>
              )
            })}
            <div className="grid gap-3 md:grid-cols-2">
              <DetailTile
                label="Gateway"
                value={hall?.hall.hallId ?? "未接通"}
                detail={describeLoadable(state.hall, hall ? `${hall.participants.length} 位參與者。` : "等待 hall。")}
              />
              <DetailTile
                label="Usage window"
                value={usage?.subscription.planLabel ?? "未接通"}
                detail={describeLoadable(state.usage, usage?.subscription.detail ?? "等待 usage。")}
              />
              <DetailTile
                label="Tracked work"
                value={`${tasks?.count ?? 0} tasks`}
                detail={describeLoadable(state.tasks, tasks ? `${tasks.count} 個 tracked tasks。` : "等待任務快照。")}
              />
              <DetailTile
                label="Crew presence"
                value={`${readSessionCount(sessions)} sessions`}
                detail={describeLoadable(state.sessions, sessions ? "目前可見 session。" : "等待 sessions。")}
              />
            </div>
          </div>
        </PixelCard>

        <PixelCard title="Key signals" eyebrow="Summary" variant="muted">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
          <StatBlock
            label="Health"
            value={healthz?.status ?? "loading"}
            tone="bg-coral/90 text-white"
            detail={describeLoadable(state.healthz, healthz ? `snapshot ${healthz.snapshot.status}` : "等待 healthz")}
          />
          <StatBlock
            label="30d Cost"
            value={usage ? `$${usage.budget.usedCost30d.toFixed(2)}` : "--"}
            tone="bg-gold/85 text-ink"
            detail={describeLoadable(state.usage, usage?.budget.message ?? "等待 usage")}
          />
          <StatBlock
            label="Hall Tasks"
            value={String(hall?.count ?? 0)}
            tone="bg-teal/90 text-white"
            detail={describeLoadable(state.hall, hall ? `${hall.participants.length} 位參與者` : "等待 hall")}
          />
          <StatBlock
            label="Sessions"
            value={String(readSessionCount(sessions))}
            tone="bg-mint text-ink"
            detail={describeLoadable(state.sessions, tasks ? `${tasks.count} 個 tracked tasks` : "等待 session / task")}
          />
          </div>
        </PixelCard>
      </div>

      <div data-testid="overview-needs-attention" className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <PixelCard title="What needs attention" eyebrow="Next moves">
          <div className="space-y-3">
            <DecisionHint
              title="先看 health"
              detail={
                healthz?.status === "ok"
                  ? "目前姿態穩定，可以往 Hall 或 Tasks 深入。"
                  : "不是 ok 時，先去 Settings 檢查 Gateway、token 與 snapshot。"
              }
            />
            <DecisionHint
              title="再看協作是否在跑"
              detail={
                hall && hall.count > 0
                  ? `目前有 ${hall.count} 張 task cards。`
                  : "Hall 目前沒有 task cards。"
              }
            />
          </div>
        </PixelCard>

        <PixelCard title="Decision queue" eyebrow="Hall">
          {renderLoadablePanel(state.hall, {
            loadingText: "正在等待 hall decision queue...",
            emptyText: "目前 hall 尚未建立 task card，這通常代表協作區還沒進線或仍處於空閒狀態。",
            render: (current) => (
              <div className="space-y-3">
                {current.taskCards.slice(0, 2).map((taskCard) => (
                  <article key={taskCard.taskCardId} className="border-4 border-ink bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="text-sm font-black tracking-[0.08em]">{taskCard.title}</h3>
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{taskCard.stage}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {summarizeSentence(taskCard.latestSummary || taskCard.description)}
                    </p>
                  </article>
                ))}
                {current.taskCards.length === 0 ? (
                  <EmptyHint text="目前 hall 尚未建立 task card，這通常代表協作區還沒進線或仍處於空閒狀態。" />
                ) : null}
              </div>
            )
          })}
        </PixelCard>
      </div>

      <div data-testid="overview-live-activity" className="grid gap-5 xl:grid-cols-[1.12fr_0.88fr]">
        <PixelCard title="Shared timeline" eyebrow="Live activity">
          {renderLoadablePanel(state.hall, {
            loadingText: "正在等待共享 timeline...",
            emptyText: "目前 hall 還沒有共享訊息，這通常表示團隊還沒開始在線上協作。",
            render: (current) => (
              <div className="space-y-3">
                {current.messages.slice(-4).reverse().map((message) => (
                  <article key={message.messageId} className="border-4 border-ink bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm font-black tracking-[0.08em]">{message.authorLabel}</p>
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{message.kind}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-700">{summarizeSentence(message.content)}</p>
                    <p className="mt-2 text-xs text-slate-500">{formatDateTime(message.createdAt)}</p>
                  </article>
                ))}
                {current.messages.length === 0 ? (
                  <EmptyHint text="目前 hall 還沒有共享訊息，這通常表示團隊還沒開始在線上協作。" />
                ) : null}
              </div>
            )
          })}
        </PixelCard>

        <PixelCard title="Session visibility" eyebrow="Live activity">
          {renderLoadablePanel(state.sessions, {
            loadingText: "正在等待 sessions visibility...",
            emptyText: "目前沒有可見 session，這通常代表 runtime 尚未產生新活動。",
            render: (current) => (
              <div className="space-y-3">
                {readSessionItems(current).slice(0, 4).map((session) => (
                  <article key={session.sessionKey} className="border-4 border-ink bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="text-sm font-black tracking-[0.08em]">
                        {session.label || session.sessionKey}
                      </h3>
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                        {session.state ?? "unknown"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-700">agent: {session.agentId ?? "未標記"}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      updated {formatDateTime(session.updatedAt || session.lastMessageAt)}
                    </p>
                  </article>
                ))}
                {readSessionItems(current).length === 0 ? (
                  <EmptyHint text="目前沒有可見 session，這通常代表 runtime 尚未產生新活動。" />
                ) : null}
              </div>
            )
          })}
        </PixelCard>
      </div>

      <div data-testid="overview-tools-drilldown" className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <PixelCard title="Tools & drill-down" eyebrow="Admin Tools">
          <div className="grid gap-3">
            <QuickLink href="/openclaw/instances" title="Instances" detail="Gateway、token、instance health。" />
            <QuickLink href="/openclaw/agents" title="Agents" detail="Roster、能力、hook 與 routing 狀態。" />
            <QuickLink href="/openclaw/workflow" title="Workflow" detail="Controller、specialists 與 handoff policy。" />
            <QuickLink href="/openclaw/logs" title="Logs" detail="需要原始 Gateway logs 時再往下鑽。" />
          </div>
        </PixelCard>

        <PixelCard title="Platform signals" eyebrow="Drill-down" variant="muted">
          <div className="grid gap-4 md:grid-cols-2">
            <DetailTile
              label="Snapshot"
              value={healthz?.snapshot.status ?? "loading"}
              detail={
                describeLoadable(
                  state.healthz,
                  healthz ? `generated ${formatDateTime(healthz.snapshot.generatedAt)}` : "等待 snapshot 資料。"
                )
              }
            />
            <DetailTile
              label="Subscription"
              value={usage?.subscription.status ?? "not_connected"}
              detail={describeLoadable(
                state.usage,
                summarizeOverviewSubscriptionDetail(usage?.subscription)
              )}
            />
          </div>
        </PixelCard>
      </div>
    </>
  );
}

function renderUsage(usageState: Loadable<ControlCenterUsageResponse>) {
  const usage = usageState.data?.usage;

  return (
    <>
      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <PixelCard title="Budget posture" eyebrow="Usage">
          {renderLoadablePanel(usageState, {
            loadingText: "正在同步 usage snapshot...",
            emptyText: "目前還沒有 usage snapshot。",
            render: ({ usage: currentUsage }) => (
              <div className="space-y-3 text-sm text-slate-700">
                <p className="font-black text-ink">狀態：{currentUsage.budget.status}</p>
                <p>近 30 天：${currentUsage.budget.usedCost30d.toFixed(2)}</p>
                <p>上限：{currentUsage.budget.limitCost30d !== undefined ? `$${currentUsage.budget.limitCost30d.toFixed(2)}` : "未接通"}</p>
                <p>{summarizeSentence(currentUsage.budget.detail ?? currentUsage.budget.message)}</p>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  <a
                    href={toControlCenterProxyHref(currentUsage.budget.templateHref ?? "/api/budget/template")}
                    className="font-semibold text-ink underline decoration-2 underline-offset-2"
                    target="_blank"
                    rel="noreferrer"
                  >
                    開啟 budget template
                  </a>
                </div>
              </div>
            )
          })}
        </PixelCard>

        <div className="grid gap-4 md:grid-cols-3">
          {(usage?.periods ?? []).map((period) => (
            <article key={period.key} className="border-4 border-ink bg-white p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{period.label}</p>
              <p className="mt-3 text-3xl font-black">{period.tokens.toLocaleString()}</p>
              <p className="mt-2 text-sm text-slate-600">
                ${period.estimatedCost.toFixed(2)} · {period.sourceStatus}
              </p>
            </article>
          ))}
          {usage && usage.periods.length === 0 ? <EmptyHint text="目前還沒有期間統計資料。" /> : null}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <PixelCard title="Subscription window" eyebrow="Connectors">
          {renderLoadablePanel(usageState, {
            loadingText: "正在同步 subscription 視窗...",
            emptyText: "目前還沒有 subscription 視窗。",
            render: ({ usage: currentUsage }) => (
              <div className="space-y-3 text-sm text-slate-700">
                <p className="font-black text-ink">方案：{currentUsage.subscription.planLabel}</p>
                <p>狀態：{currentUsage.subscription.status}</p>
                {currentUsage.subscription.consumed !== undefined ? (
                  <p>已用：{formatSubscriptionValue(currentUsage.subscription.consumed, currentUsage.subscription.unit)}</p>
                ) : null}
                {currentUsage.subscription.remaining !== undefined ? (
                  <p>剩餘：{formatSubscriptionValue(currentUsage.subscription.remaining, currentUsage.subscription.unit)}</p>
                ) : null}
                {currentUsage.subscription.limit !== undefined ? (
                  <p>總額：{formatSubscriptionValue(currentUsage.subscription.limit, currentUsage.subscription.unit)}</p>
                ) : null}
                <p>{summarizeSentence(currentUsage.subscription.detail)}</p>
                {currentUsage.subscription.templateHref ? (
                  <a
                    href={toControlCenterProxyHref(currentUsage.subscription.templateHref)}
                    className="inline-flex text-xs font-semibold text-ink underline decoration-2 underline-offset-2"
                    target="_blank"
                    rel="noreferrer"
                  >
                    開啟 subscription template
                  </a>
                ) : null}
              </div>
            )
          })}
        </PixelCard>

        <PixelCard title="Connector backlog" eyebrow="Visibility">
          {renderLoadablePanel(usageState, {
            loadingText: "正在同步 connector 狀態...",
            emptyText: "目前還沒有 connector 狀態。",
            render: ({ usage: currentUsage }) => (
              <div className="space-y-2">
                {currentUsage.connectors.todos.map((item) => (
                  <article key={item.id} className="border-4 border-ink bg-white p-3 text-sm text-slate-700">
                    <p className="font-black tracking-[0.08em]">{localizeConnectorTodoTitle(item.id, item.title)}</p>
                    <p className="mt-2">{summarizeSentence(localizeConnectorTodoDetail(item.id, item.detail))}</p>
                    {item.id === "cost_budget_limit" ? (
                      <a
                        href={toControlCenterProxyHref("/api/budget/template")}
                        className="mt-3 inline-flex font-semibold text-ink underline decoration-2 underline-offset-2"
                        target="_blank"
                        rel="noreferrer"
                      >
                        取得 budget template
                      </a>
                    ) : null}
                    {item.id === "subscription_usage" ? (
                      <a
                        href={toControlCenterProxyHref("/api/subscription/template")}
                        className="mt-3 inline-flex font-semibold text-ink underline decoration-2 underline-offset-2"
                        target="_blank"
                        rel="noreferrer"
                      >
                        取得 subscription template
                      </a>
                    ) : null}
                  </article>
                ))}
                {currentUsage.connectors.todos.length === 0 ? (
                  <EmptyHint text="所有 connector 目前都沒有待補項。" />
                ) : null}
              </div>
            )
          })}
        </PixelCard>
      </div>
    </>
  );
}

function localizeConnectorTodoTitle(id: string, fallback: string) {
  if (id === "cost_budget_limit") return "設定月預算上限";
  if (id === "subscription_usage") return "建立 subscription snapshot";
  return fallback;
}

function localizeConnectorTodoDetail(id: string, fallback: string) {
  if (id === "cost_budget_limit") {
    return "建立全域 budget 設定，或在 agent budgets 補上 cost threshold，讓 burn-rate 可以對照真實月上限。";
  }
  if (id === "subscription_usage") {
    return "建立 provider snapshot 或補上 Codex telemetry，讓 subscription 視窗顯示完整剩餘額度。";
  }
  return fallback;
}

function summarizeOverviewSubscriptionDetail(
  subscription?: ControlCenterUsageResponse["usage"]["subscription"]
) {
  if (!subscription) {
    return "若沒有訂閱資料，這裡會降級而不是視為安裝失敗。";
  }

  if (subscription.status === "connected") {
    return subscription.connectHintShort ?? subscription.detail;
  }

  return subscription.connectHintShort ?? subscription.connectHint;
}

function formatSubscriptionValue(value: number, unit: string) {
  if (unit === "%") return `${value.toFixed(1)}%`;
  return `${value.toFixed(2)} ${unit}`;
}

function toControlCenterProxyHref(path: string) {
  return `/api/control-center${path.startsWith("/") ? path : `/${path}`}`;
}

function summarizeSentence(value?: string | null, maxLength = 96) {
  if (!value) return "目前沒有額外摘要。";
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`;
}

function renderStaff(staffSummaryState: Loadable<ControlCenterStaffSummaryResponse>) {
  const summary = staffSummaryState.data;
  const sessions = summary?.sessionsDetail.sessions ?? [];

  return (
    <div className="space-y-5">
      <PixelCard title="Role view" eyebrow="Staff">
        {renderLoadablePanel(staffSummaryState, {
          loadingText: "正在整理角色視圖與員工卡...",
          emptyText: "目前還沒有可顯示的員工摘要。",
          render: (current) => (
            <div className="space-y-4">
              {current.groups.map((group) => (
                <section key={group.roleKey} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b-4 border-ink pb-3">
                    <div>
                      <h3 className="text-base font-black tracking-[0.08em] text-ink">{group.roleLabel}</h3>
                      <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">{group.count} members</p>
                    </div>
                    <p className="text-xs text-slate-500">role key: {group.roleKey}</p>
                  </div>
                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    {group.members.map((member) => (
                      <article key={member.agentId} className="border-4 border-ink bg-sand/40 p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="flex items-start gap-4">
                            <StaffRoleLottie roleKey={group.roleKey} statusLabel={member.statusLabel} />
                            <div>
                              <h4 className="text-sm font-black tracking-[0.08em] text-ink">{member.displayName}</h4>
                              <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">{member.agentId}</p>
                            </div>
                          </div>
                          <span className="border-4 border-ink bg-white px-3 py-1 text-[11px] font-black uppercase tracking-[0.18em] text-ink">
                            {member.statusLabel}
                          </span>
                        </div>
                        {member.statusSource || member.recentOutputAt ? (
                          <p className="mt-3 text-xs text-slate-500">
                            {member.statusSource === "latest_session" ? "source: latest session" : "source: office fallback"}
                            {member.recentOutputAt ? ` · output ${formatDateTime(member.recentOutputAt)}` : ""}
                          </p>
                        ) : null}
                        <dl className="mt-4 space-y-3 text-sm text-slate-700">
                          <div>
                            <dt className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Role positioning</dt>
                            <dd className="mt-1 font-semibold text-ink">{member.roleLabel}</dd>
                          </div>
                          <div>
                            <dt className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{member.currentWorkLabel}</dt>
                            <dd className="mt-1">{member.currentWork}</dd>
                          </div>
                          <div>
                            <dt className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Recent output</dt>
                            <dd className="mt-1">{member.recentOutput}</dd>
                          </div>
                          <div>
                            <dt className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Schedule</dt>
                            <dd className="mt-1">{member.scheduledLabel}</dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>
                </section>
              ))}
              {current.groups.length === 0 ? <EmptyHint text="目前還沒有可顯示的員工摘要。" /> : null}
            </div>
          )
        })}
      </PixelCard>

      <PixelCard title="Staff visibility" eyebrow="Coverage">
        <div className="grid gap-3 md:grid-cols-3">
          <DetailTile
            label="Role Groups"
            value={`${summary?.groups.length ?? 0}`}
            detail="角色視圖只顯示目前有成員的分組。"
          />
          <DetailTile
            label="Members"
            value={`${summary?.groups.reduce((sum, group) => sum + group.count, 0) ?? 0}`}
            detail="每位員工只會出現在一個角色分組中。"
          />
          <DetailTile
            label="Sessions"
            value={`${summary?.sessionsDetail.count ?? 0}`}
            detail="raw sessions 明細保留在下方展開區，供排錯時使用。"
          />
        </div>
      </PixelCard>

      <details data-testid="staff-sessions-details" className="border-4 border-ink bg-white p-4">
        <summary className="cursor-pointer text-sm font-black tracking-[0.08em] text-ink">
          Raw sessions detail
        </summary>
        <div className="mt-4 space-y-3">
          {staffSummaryState.status === "error" ? (
            <ErrorHint text={staffSummaryState.error ?? "無法載入 staff sessions detail"} />
          ) : sessions.length === 0 ? (
            <EmptyHint text="目前沒有可見 session，這通常代表 runtime 尚未產生新活動。" />
          ) : (
            sessions.map((session) => (
              <article key={session.sessionKey} className="border-4 border-ink bg-sand/30 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-sm font-black tracking-[0.08em]">{session.label || session.sessionKey}</h3>
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{session.state ?? "unknown"}</span>
                </div>
                <p className="mt-2 text-sm text-slate-700">agent: {session.agentId ?? "未標記"}</p>
                <p className="mt-2 text-xs text-slate-500">
                  updated: {formatDateTime(session.updatedAt || session.lastMessageAt)}
                </p>
                {session.latestSnippet ? (
                  <p className="mt-3 text-sm leading-6 text-slate-700">{session.latestSnippet}</p>
                ) : null}
              </article>
            ))
          )}
        </div>
      </details>
    </div>
  );
}

function renderCollaboration(hallState: Loadable<ControlCenterHallResponse>) {
  const hall = hallState.data;

  return (
    <div className="hall-layout grid gap-5 xl:grid-cols-[0.9fr_1.3fr_0.95fr]">
      <PixelCard title="Collaboration health" eyebrow="Snapshot">
        {renderLoadablePanel(hallState, {
          loadingText: "正在同步 collaboration threads...",
          emptyText: "目前還沒有 task threads。",
          render: (current) => (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <article className="border-4 border-ink bg-white p-4">
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Active participants</p>
                  <p className="mt-3 text-3xl font-black tracking-[0.08em] text-ink">
                    {current.participants.filter((participant) => participant.active).length || current.participants.length}
                  </p>
                  <p className="mt-2 text-xs text-slate-600">已在 hall 內可見、可協作的人員數。</p>
                </article>
                <article className="border-4 border-ink bg-white p-4">
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Active threads</p>
                  <p className="mt-3 text-3xl font-black tracking-[0.08em] text-ink">{current.taskCards.length}</p>
                  <p className="mt-2 text-xs text-slate-600">目前有 owner 或最近互動的 task threads。</p>
                </article>
              </div>

              <article className="border-4 border-ink bg-white p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Snapshot summary</p>
                <p className="mt-3 text-sm leading-7 text-slate-700">
                  {current.summary?.headline || current.summary?.detail || "目前還沒有額外 collaboration headline。"}
                </p>
              </article>

              <div className="space-y-3">
                {current.taskCards.map((taskCard) => {
                  const threadSignalCount = current.messages.filter((message) => message.taskCardId === taskCard.taskCardId).length;
                  return (
                    <article key={taskCard.taskCardId} className="border-4 border-ink bg-white p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="text-sm font-black tracking-[0.08em]">{taskCard.title}</h3>
                        <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{taskCard.stage}</span>
                      </div>
                      <p className="mt-2 text-sm leading-7 text-slate-700">
                        {taskCard.latestSummary || taskCard.description}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                        <span className="border-2 border-slate-300 px-2 py-1">{taskCard.currentOwnerLabel || "未指定 owner"}</span>
                        <span className="border-2 border-slate-300 px-2 py-1">{threadSignalCount} signals</span>
                        <span className="border-2 border-slate-300 px-2 py-1">{taskCard.status || "active"}</span>
                      </div>
                    </article>
                  );
                })}
              </div>
              {current.taskCards.length === 0 ? <EmptyHint text="目前還沒有 task threads。" /> : null}
            </div>
          )
        })}
      </PixelCard>

      <PixelCard title="Live coordination" eyebrow="Timeline">
        {renderLoadablePanel(hallState, {
          loadingText: "正在同步 hall shared timeline...",
          emptyText: "目前 hall 還沒有訊息。",
          render: (current) => (
            <div className="space-y-3">
              {current.messages.slice(-10).reverse().map((message) => (
                <article key={message.messageId} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-black tracking-[0.08em]">{message.authorLabel}</p>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      {message.kind} · {formatDateTime(message.createdAt)}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{message.content}</p>
                  {message.taskCardId ? (
                    <p className="mt-2 text-xs uppercase tracking-[0.14em] text-slate-500">thread {message.taskCardId}</p>
                  ) : null}
                </article>
              ))}
              {current.messages.length === 0 ? <EmptyHint text="目前 hall 還沒有訊息。" /> : null}
            </div>
          )
        })}
      </PixelCard>

      <PixelCard title="Who is working with whom" eyebrow="Roles">
        {hall ? (
          <div className="space-y-4">
            <article className="border-4 border-ink bg-white p-4">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Current focus</p>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                {describeCollaborationFocus(hall)}
              </p>
            </article>

            <div className="space-y-2">
              {hall.participants.map((participant) => (
                <article key={participant.participantId} className="border-4 border-ink bg-white p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-black tracking-[0.08em] text-ink">{participant.displayName}</p>
                      <p className="mt-2 text-xs text-slate-600">{participant.semanticRole ?? "未標記角色"}</p>
                    </div>
                    <span
                      className={`border-2 px-2 py-1 text-[11px] font-black uppercase tracking-[0.14em] ${
                        participant.active ? "border-emerald-700 bg-emerald-100 text-emerald-900" : "border-slate-300 bg-slate-100 text-slate-600"
                      }`}
                    >
                      {participant.active ? "active" : "standby"}
                    </span>
                  </div>
                </article>
              ))}
            </div>

            {hall.taskCards.length > 0 ? (
              <article className="border-4 border-ink bg-white p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Most active thread</p>
                <p className="mt-3 text-sm font-black tracking-[0.08em] text-ink">{pickMostActiveTaskCard(hall)?.title}</p>
                <p className="mt-2 text-xs text-slate-600">
                  owner：{pickMostActiveTaskCard(hall)?.currentOwnerLabel || "未指定"} · stage：{pickMostActiveTaskCard(hall)?.stage || "--"}
                </p>
              </article>
            ) : null}
          </div>
        ) : hallState.status === "error" ? (
          <ErrorHint text={hallState.error ?? "無法載入 collaboration context。"} />
        ) : (
          <EmptyHint text="目前還沒有 collaboration context。" />
        )}
      </PixelCard>
    </div>
  );
}

function pickMostActiveTaskCard(hall: ControlCenterHallResponse) {
  return [...hall.taskCards].sort((left, right) => {
    const leftSignals = hall.messages.filter((message) => message.taskCardId === left.taskCardId).length;
    const rightSignals = hall.messages.filter((message) => message.taskCardId === right.taskCardId).length;
    if (leftSignals !== rightSignals) return rightSignals - leftSignals;
    return (right.latestSummary || right.description).length - (left.latestSummary || left.description).length;
  })[0];
}

function describeCollaborationFocus(hall: ControlCenterHallResponse) {
  const activeParticipants = hall.participants.filter((participant) => participant.active);
  const activeNames = activeParticipants.slice(0, 3).map((participant) => participant.displayName);
  const topThread = pickMostActiveTaskCard(hall);

  if (topThread && activeNames.length > 0) {
    return `${activeNames.join("、")} 目前主要圍繞「${topThread.title}」協作，owner 是 ${topThread.currentOwnerLabel || "未指定"}。`;
  }
  if (topThread) {
    return `目前最活躍的 thread 是「${topThread.title}」，owner 是 ${topThread.currentOwnerLabel || "未指定"}。`;
  }
  if (activeNames.length > 0) {
    return `${activeNames.join("、")} 目前在 hall 內活躍，但尚未形成明確的 task thread。`;
  }
  return "目前 hall 內沒有明確的活躍 thread 或協作焦點。";
}

function renderHall(hallState: Loadable<ControlCenterHallResponse>) {
  const hall = hallState.data;

  return (
    <div className="hall-layout grid gap-5 xl:grid-cols-[0.88fr_1.35fr_0.92fr]">
      <PixelCard title="Threads" eyebrow="Hall">
        {renderLoadablePanel(hallState, {
          loadingText: "正在同步 hall threads...",
          emptyText: "目前沒有 hall task cards。",
          render: (current) => (
            <div className="space-y-3">
              {current.taskCards.map((taskCard) => (
                <article key={taskCard.taskCardId} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-sm font-black tracking-[0.08em]">{taskCard.title}</h3>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{taskCard.stage}</span>
                  </div>
                  <p className="mt-3 text-sm text-slate-700">{taskCard.description}</p>
                  <p className="mt-2 text-xs text-slate-500">owner：{taskCard.currentOwnerLabel ?? "未指定"}</p>
                </article>
              ))}
              {current.taskCards.length === 0 ? <EmptyHint text="目前沒有 hall task cards。" /> : null}
            </div>
          )
        })}
      </PixelCard>

      <PixelCard title="Hall timeline" eyebrow="Thread">
        {renderLoadablePanel(hallState, {
          loadingText: "正在同步 hall timeline...",
          emptyText: "目前沒有可顯示的 hall timeline。",
          render: (current) => (
            <div className="space-y-3">
              {current.messages.slice(-12).reverse().map((message) => (
                <article key={message.messageId} className="border-4 border-ink bg-white p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    {message.authorLabel} · {formatDateTime(message.createdAt)}
                  </p>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{message.content}</p>
                </article>
              ))}
              {current.messages.length === 0 ? <EmptyHint text="目前沒有可顯示的 hall timeline。" /> : null}
            </div>
          )
        })}
      </PixelCard>

      <PixelCard title="Context" eyebrow="Detail">
        {hall ? (
          <div className="space-y-4">
            <div className="space-y-2 text-sm text-slate-700">
              <p>{hall.summary?.headline || "大廳目前沒有額外 headline。"}</p>
              <p>{hall.summary?.detail || "這裡會接住 owner、decision、evidence 等上下文摘要。"}</p>
            </div>
            <div className="space-y-2">
              {hall.participants.map((participant) => (
                <article key={participant.participantId} className="border-4 border-ink bg-white p-3">
                  <p className="text-sm font-black tracking-[0.08em] text-ink">{participant.displayName}</p>
                  <p className="mt-2 text-xs text-slate-600">
                    {participant.active ? "active" : "idle"} · {participant.semanticRole ?? "未標記角色"}
                  </p>
                </article>
              ))}
            </div>
          </div>
        ) : hallState.status === "error" ? (
          <ErrorHint text={hallState.error ?? "目前沒有可顯示的 hall context。"} />
        ) : (
          <EmptyHint text="目前沒有可顯示的 hall context。" />
        )}
      </PixelCard>
    </div>
  );
}

function renderTasks(tasksState: Loadable<ControlCenterTasksResponse>) {
  const tasks = tasksState.data;

  return (
    <div className="task-room-layout grid gap-5 xl:grid-cols-[0.9fr_1.32fr_0.9fr]">
      <PixelCard title="Task rooms" eyebrow="Tasks">
        {renderLoadablePanel(tasksState, {
          loadingText: "正在同步 task rooms...",
          emptyText: "目前沒有 tracked task rooms。",
          render: (current) => (
            <div className="space-y-3">
              {current.tasks.map((task) => (
                <article key={`${task.projectId}:${task.taskId}`} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-sm font-black tracking-[0.08em]">{task.title}</h3>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{task.status}</span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    {task.projectId}:{task.taskId}
                  </p>
                </article>
              ))}
              {current.tasks.length === 0 ? <EmptyHint text="目前沒有 tracked task rooms。" /> : null}
            </div>
          )
        })}
      </PixelCard>

      <PixelCard title="Room timeline" eyebrow="Workbench">
        {renderLoadablePanel(tasksState, {
          loadingText: "正在同步 room timeline...",
          emptyText: "目前還沒有 room timeline 可顯示。",
          render: (current) => (
            <div className="space-y-3">
              {current.tasks.map((task) => (
                <article key={`timeline:${task.projectId}:${task.taskId}`} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-sm font-black tracking-[0.08em]">{task.title}</h3>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{task.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-700">
                    {task.projectTitle} · owner {task.owner ?? "unassigned"}
                  </p>
                  <p className="mt-2 text-sm leading-7 text-slate-700">
                    {task.roomId
                      ? `已連到 room ${task.roomId}，可作為 task room workbench 的主線。`
                      : "尚未連到 room，這代表目前仍缺少 task room 鏈路。"}
                  </p>
                  <p className="mt-2 text-xs text-slate-500">updated {formatDateTime(task.updatedAt)}</p>
                </article>
              ))}
              {current.tasks.length === 0 ? <EmptyHint text="目前還沒有 room timeline 可顯示。" /> : null}
            </div>
          )
        })}
      </PixelCard>

      <PixelCard title="Context" eyebrow="Detail">
        <div className="space-y-3">
          <DetailTile
            label="Tracked tasks"
            value={`${tasks?.count ?? 0}`}
            detail="先看 task 是否存在，再判斷 room、sessionKeys 與 owner 是否接上。"
          />
          <DetailTile
            label="Linked rooms"
            value={`${tasks?.tasks.filter((task) => Boolean(task.roomId)).length ?? 0}`}
            detail="roomId 是 task room workbench 能否成立的關鍵鏈路。"
          />
          <DetailTile
            label="Runtime evidence"
            value={`${tasks?.tasks.filter((task) => (task.sessionKeys?.length ?? 0) > 0).length ?? 0}`}
            detail="sessionKeys 越完整，runtime evidence 越容易回流到任務線上。"
          />
        </div>
      </PixelCard>
    </div>
  );
}

function renderFilesWorkbench(scope: "workspace" | "memory", filesState: Loadable<ControlCenterFilesResponse>) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
      <PixelCard
        title={scope === "workspace" ? "Workspace files" : "Memory files"}
        eyebrow={scope === "workspace" ? "Documents" : "Memory"}
      >
        <FilesWorkbenchBrowser scope={scope} filesState={filesState} />
      </PixelCard>

      <PixelCard title="Workbench context" eyebrow="Detail">
        <FilesWorkbenchContext scope={scope} filesState={filesState} />
      </PixelCard>
    </div>
  );
}

function FilesWorkbenchBrowser({
  scope,
  filesState,
}: {
  scope: "workspace" | "memory";
  filesState: Loadable<ControlCenterFilesResponse>;
}) {
  const files = filesState.data;
  const [selectedFacet, setSelectedFacet] = useState("main");
  const [searchInput, setSearchInput] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const deferredSearch = useDeferredValue(searchInput.trim().toLowerCase());

  const facetOptions = files ? resolveFileFacetOptions(files) : [];
  const normalizedDefaultFacet = files?.defaultFacetKey?.trim().toLowerCase() || "main";

  useEffect(() => {
    if (!files) return;
    const available = facetOptions.map((item) => item.key);
    const nextFacet = available.includes(normalizedDefaultFacet)
      ? normalizedDefaultFacet
      : available[0] ?? "main";
    setSelectedFacet((current) => (available.includes(current) ? current : nextFacet));
  }, [files, facetOptions, normalizedDefaultFacet]);

  const visibleFacet = facetOptions.some((item) => item.key === selectedFacet)
    ? selectedFacet
    : facetOptions[0]?.key ?? normalizedDefaultFacet;

  const categories = files ? resolveFileCategories(files.files, visibleFacet) : [];

  useEffect(() => {
    if (selectedCategory === "all") return;
    if (!categories.includes(selectedCategory)) {
      setSelectedCategory("all");
    }
  }, [categories, selectedCategory]);

  const filteredFiles = files
    ? files.files.filter((file) => {
        const fileFacet = normalizeFileFacetKey(file.facetKey);
        if (visibleFacet !== "all" && fileFacet !== visibleFacet) return false;
        if (selectedCategory !== "all" && (file.category ?? "未分類") !== selectedCategory) return false;
        if (!deferredSearch) return true;
        const haystack = [
          file.title,
          file.relativePath ?? file.sourcePath,
          file.category ?? "",
          file.facetLabel ?? "",
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(deferredSearch);
      })
    : [];

  const latestUpdate = filteredFiles
    .map((file) => file.updatedAt)
    .filter((value): value is string => Boolean(value))
    .sort((a, b) => b.localeCompare(a))[0];
  const mainCount = files?.files.filter((file) => normalizeFileFacetKey(file.facetKey) === "main").length ?? 0;
  const agentViewCount = Math.max(0, facetOptions.filter((item) => item.key !== "main").length);

  return renderLoadablePanel(filesState, {
    loadingText: "正在同步檔案清單...",
    emptyText: "目前這個 scope 尚未回傳可用檔案。",
    render: () => (
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <StatBlock
            label="Main files"
            value={`${mainCount}`}
            tone="bg-mint text-ink"
            detail="Main 會先顯示共享文檔與核心工作檔。"
          />
          <StatBlock
            label="Agent views"
            value={`${agentViewCount}`}
            tone="bg-sand text-ink"
            detail="可快速切換到各 agent 的核心文檔視角。"
          />
          <StatBlock
            label="Latest update"
            value={latestUpdate ? formatDateTime(latestUpdate) : "--"}
            tone="bg-white text-ink"
            detail="這裡只看目前篩選後可見檔案的最新更新時間。"
          />
        </div>

        <div className="grid gap-3 rounded-none border-4 border-ink bg-sand/30 p-4 md:grid-cols-[1.2fr_auto_auto]">
          <label className="space-y-2 text-xs font-black uppercase tracking-[0.16em] text-ink">
            Search
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={scope === "workspace" ? "搜尋檔名、路徑、分類..." : "搜尋記憶檔名、路徑、分類..."}
              className="w-full rounded-none border-4 border-ink bg-white px-3 py-2 text-sm font-medium normal-case tracking-normal text-ink outline-none"
            />
          </label>
          <label className="space-y-2 text-xs font-black uppercase tracking-[0.16em] text-ink">
            Facet
            <select
              value={visibleFacet}
              onChange={(event) => setSelectedFacet(event.target.value)}
              className="rounded-none border-4 border-ink bg-white px-3 py-2 text-sm font-medium normal-case tracking-normal text-ink outline-none"
            >
              {facetOptions.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2 text-xs font-black uppercase tracking-[0.16em] text-ink">
            Category
            <select
              value={selectedCategory}
              onChange={(event) => setSelectedCategory(event.target.value)}
              className="rounded-none border-4 border-ink bg-white px-3 py-2 text-sm font-medium normal-case tracking-normal text-ink outline-none"
            >
              <option value="all">全部分類</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="space-y-3" data-testid={`${scope}-files-browser`}>
          {filteredFiles.map((file) => (
            <article key={file.sourcePath} className="border-4 border-ink bg-white p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-black tracking-[0.08em] text-ink">{file.title}</h3>
                    {file.category ? (
                      <span className="border-2 border-ink bg-mint px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.16em] text-ink">
                        {file.category}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">{file.relativePath ?? file.sourcePath}</p>
                </div>
                <Link
                  href={`/api/control-center/api/files/content?scope=${scope}&path=${encodeURIComponent(file.sourcePath)}`}
                  className="pixel-button bg-sand px-3 py-2 text-xs font-black tracking-[0.08em] text-ink"
                  target="_blank"
                >
                  Open JSON
                </Link>
              </div>
              {file.excerpt ? (
                <p className="mt-3 text-sm leading-6 text-slate-700">{truncateText(file.excerpt, 180)}</p>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                {file.facetLabel ? <span>view: {file.facetLabel}</span> : null}
                <span>{file.updatedAt ? formatDateTime(file.updatedAt) : "未提供更新時間"}</span>
                <span>{formatFileSize(file.sizeBytes ?? file.size)}</span>
              </div>
              <details className="mt-3 border-4 border-ink bg-sand/20 p-3">
                <summary className="cursor-pointer text-xs font-black uppercase tracking-[0.18em] text-ink">
                  Diagnostics
                </summary>
                <div className="mt-3 space-y-2 text-xs leading-6 text-slate-600">
                  <p>source path: {file.sourcePath}</p>
                  <p>relative path: {file.relativePath ?? file.sourcePath}</p>
                </div>
              </details>
            </article>
          ))}
          {filteredFiles.length === 0 ? (
            <EmptyHint text={deferredSearch || selectedCategory !== "all" ? "目前沒有符合篩選條件的檔案。" : "目前這個 scope 尚未回傳可用檔案。"} />
          ) : null}
        </div>
      </div>
    ),
  });
}

function FilesWorkbenchContext({
  scope,
  filesState,
}: {
  scope: "workspace" | "memory";
  filesState: Loadable<ControlCenterFilesResponse>;
}) {
  const files = filesState.data;
  const facetOptions = files ? resolveFileFacetOptions(files) : [];
  const defaultFacet = files?.defaultFacetKey?.trim().toLowerCase() || facetOptions[0]?.key || "main";

  return (
    <div className="space-y-3">
      <DetailTile
        label="Scope"
        value={scope === "workspace" ? "workspace" : "memory"}
        detail={
          scope === "workspace"
            ? "這裡先聚焦 Main 與 active agents 的核心工作文檔。"
            : "這裡聚焦 Main 與各 agent 的記憶檔案視圖。"
        }
      />
      <DetailTile
        label="Default facet"
        value={files ? humanizeFacetValue(defaultFacet, facetOptions) : "main"}
        detail="預設會先落在 Main，再讓你切到各 agent 視角。"
      />
      <DetailTile
        label="Visible / Total"
        value={files ? `${files.files.length} / ${files.count}` : "0 / 0"}
        detail="搜尋與 facet 切換都只在真實檔案清單上運作，不複製假資料。"
      />
      <DetailTile
        label="Access"
        value="Open JSON"
        detail="主畫面先做 focused browser；原始內容與來源路徑保留在次要 diagnostics。"
      />
    </div>
  );
}

function renderSettings(
  healthzState: Loadable<ControlCenterHealthzPayload>,
  diagnosticsState: Loadable<ControlCenterDiagnosticsResponse>
) {
  const healthz = healthzState.data;
  const diagnostics = diagnosticsState.data;

  return (
    <>
      <div className="grid gap-4 md:grid-cols-4">
        <StatBlock
          label="Readonly"
          value={healthz ? String(healthz.build.readonlyMode) : "--"}
          tone="bg-mint text-ink"
          detail="高風險寫操作預設應維持關閉。"
        />
        <StatBlock
          label="Approvals"
          value={healthz ? String(healthz.build.approvalActionsEnabled) : "--"}
          tone="bg-coral text-white"
          detail={healthz ? `dry-run ${String(healthz.build.approvalActionsDryRun)}` : "等待 healthz"}
        />
        <StatBlock
          label="Gateway"
          value={diagnostics?.diagnostics.gateway.overallStatus ?? (diagnosticsState.status === "loading" ? "loading" : "--")}
          tone="bg-teal text-white"
          detail={describeLoadable(diagnosticsState, diagnostics?.diagnostics.gateway.configuredUrl ?? "等待 diagnostics")}
        />
        <StatBlock
          label="OpenClaw"
          value={diagnostics?.diagnostics.openclaw.status ?? (diagnosticsState.status === "loading" ? "loading" : "--")}
          tone="bg-gold text-ink"
          detail={describeLoadable(diagnosticsState, diagnostics?.diagnostics.openclaw.currentVersion ?? "等待 diagnostics")}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <PixelCard title="Safety Posture" eyebrow="Settings">
          {renderLoadablePanel(healthzState, {
            loadingText: "正在同步 healthz 安全摘要...",
            emptyText: "目前還沒有 healthz 安全摘要。",
            render: (current) => (
              <div className="space-y-3 text-sm text-slate-700">
                <p>healthz：{current.status}</p>
                <p>readonly：{String(current.build.readonlyMode)}</p>
                <p>approvalActionsEnabled：{String(current.build.approvalActionsEnabled)}</p>
                <p>approvalActionsDryRun：{String(current.build.approvalActionsDryRun)}</p>
                <p>snapshot generated：{formatDateTime(current.snapshot.generatedAt)}</p>
                <p>monitor：{current.monitor.status}</p>
              </div>
            )
          })}
        </PixelCard>

        <PixelCard title="Diagnostics" eyebrow="Connections">
          {renderLoadablePanel(diagnosticsState, {
            loadingText: "正在同步 diagnostics bundle...",
            emptyText: "目前還沒有 diagnostics bundle。",
            render: (current) => (
              <div className="space-y-4">
                <div className="text-sm text-slate-700">
                  <p>Gateway：{current.diagnostics.gateway.configuredUrl}</p>
                  <p>Gateway status：{current.diagnostics.gateway.overallStatus}</p>
                  <p>OpenClaw status：{current.diagnostics.openclaw.status}</p>
                  <p>
                    版本：{current.diagnostics.openclaw.currentVersion ?? "unknown"} / latest{" "}
                    {current.diagnostics.openclaw.latestVersion ?? "unknown"}
                  </p>
                </div>
                <div className="space-y-2">
                  {current.diagnostics.tokens.entries.map((entry) => (
                    <article key={entry.key} className="border-4 border-ink bg-white p-3 text-sm text-slate-700">
                      <p className="font-black tracking-[0.08em]">{entry.key}</p>
                      <p className="mt-2">
                        {entry.present ? "present" : "missing"} · {entry.note}
                      </p>
                    </article>
                  ))}
                </div>
              </div>
            )
          })}
        </PixelCard>
      </div>

      <PixelCard title="Recent issues" eyebrow="Visibility">
        {renderLoadablePanel(diagnosticsState, {
          loadingText: "正在同步 recent issues...",
          emptyText: "目前還沒有 settings visibility bundle。",
          render: (current) => (
            <div className="grid gap-3">
              {current.diagnostics.recentIssues.map((issue) => (
                <article key={`${issue.timestamp}:${issue.action}`} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-black tracking-[0.08em] text-ink">{issue.action}</p>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{issue.severity}</span>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{issue.detail}</p>
                </article>
              ))}
              {current.diagnostics.recentIssues.length === 0 ? (
                <EmptyHint text="目前沒有近期異常，這通常代表接線完整度與安全預設都處於穩定狀態。" />
              ) : null}
            </div>
          )
        })}
      </PixelCard>
    </>
  );
}

function renderOverviewInspector(state: SectionState, onOpenTimedJobs: () => void) {
  const healthz = state.healthz.data;
  const cronOverview = state.cronOverview.data;
  const sessions = state.sessions.data;
  const firstTimedJobRow = Array.isArray(cronOverview?.rows) ? cronOverview.rows[0] : undefined;
  const timedJobsSummary =
    firstTimedJobRow
      ? `${firstTimedJobRow.owner} · ${firstTimedJobRow.purpose}`
      : healthz?.monitor.detail ?? "這裡會顯示哪個 agent 在什麼時間做什麼。";
  const tasks = state.tasks.data;

  return (
    <>
      <PixelCard title="Current status" eyebrow="Inspector">
        <div className="space-y-3 text-sm text-slate-700">
          <p>Health：{healthz?.status ?? readableLoadStatus(state.healthz.status)}</p>
          <p>Active sessions：{readSessionCount(sessions)}</p>
          <p>Tasks under watch：{tasks?.count ?? 0}</p>
          <p>Review queue：{state.hall.data?.count ?? 0}</p>
        </div>
      </PixelCard>

      <PixelCard title="Timed jobs and heartbeat" eyebrow="Inspector">
        <div className="space-y-3 text-sm text-slate-700">
          <div className="flex items-center justify-between gap-3">
            <p className="font-black tracking-[0.08em] text-slate-900">誰在什麼時間做什麼</p>
            <button
              type="button"
              onClick={onOpenTimedJobs}
              className="border-4 border-ink bg-white px-3 py-2 text-[11px] font-black tracking-[0.12em] text-slate-900 transition hover:-translate-y-px"
            >
              Open timed jobs
            </button>
          </div>
          <p>Timed jobs：{cronOverview?.overview.health.status ?? healthz?.snapshot.status ?? readableLoadStatus(state.healthz.status)}</p>
          <p>Heartbeat：{healthz?.monitor.status ?? readableLoadStatus(state.healthz.status)}</p>
          <p>
            Next：
            {cronOverview?.overview.nextRunAt
              ? formatDateTime(cronOverview.overview.nextRunAt)
              : healthz?.snapshot.generatedAt
                ? formatDateTime(healthz.snapshot.generatedAt)
                : "尚未取得 snapshot 時間"}
          </p>
          <p>{describeLoadable(state.cronOverview, timedJobsSummary)}</p>
        </div>
      </PixelCard>
    </>
  );
}

function TimedJobsModal({
  open,
  onClose,
  rows,
}: {
  open: boolean;
  onClose: () => void;
  rows: TimedJobRow[];
}) {
  if (!open) return null;

  const cronRows = rows.filter((row) => row.channel === "cron");
  const heartbeatRows = rows.filter((row) => row.channel === "heartbeat");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-6"
      onClick={onClose}
      data-testid="timed-jobs-overlay"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Timed jobs and heartbeat"
        className="max-h-[90vh] w-full max-w-6xl overflow-hidden border-4 border-ink bg-[#f8f1d4] shadow-[12px_12px_0_0_#1f2937]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b-4 border-ink bg-[#ffd95e] px-5 py-4">
          <div className="space-y-1">
            <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-700">Control Center</p>
            <h2 className="text-xl font-black tracking-[0.08em] text-slate-950">Timed jobs and heartbeat</h2>
            <p className="text-sm text-slate-700">一眼看懂誰在什麼時間做什麼。</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="border-4 border-ink bg-white px-3 py-2 text-[11px] font-black tracking-[0.12em] text-slate-900 transition hover:-translate-y-px"
          >
            Close
          </button>
        </div>

        <div className="max-h-[calc(90vh-84px)] space-y-6 overflow-y-auto px-5 py-5">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="border-4 border-ink bg-white p-4 text-sm text-slate-700">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Cron</p>
              <p className="mt-2">真正定時任務。這裡顯示排程責任、任務用途與可見的下一個時間點。</p>
            </div>
            <div className="border-4 border-ink bg-white p-4 text-sm text-slate-700">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Heartbeat</p>
              <p className="mt-2">系統巡檢與心跳檢查。用來確認 scheduler 與任務心跳是否還在正常工作。</p>
            </div>
          </div>

          <TimedJobsTable title="Cron" rows={cronRows} emptyText="目前沒有可見的 cron 定時任務。" />
          <TimedJobsTable title="Heartbeat" rows={heartbeatRows} emptyText="目前沒有可見的 heartbeat 檢查。" />
        </div>
      </div>
    </div>
  );
}

function TimedJobsTable({
  title,
  rows,
  emptyText,
}: {
  title: string;
  rows: TimedJobRow[];
  emptyText: string;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-black tracking-[0.08em] text-slate-950">{title}</h3>
        <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">{rows.length} visible</p>
      </div>
      {rows.length === 0 ? (
        <div className="border-4 border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">{emptyText}</div>
      ) : (
        <div className="overflow-x-auto border-4 border-ink bg-white">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-[#fff4bf]">
              <tr className="border-b-4 border-ink">
                <th className="px-4 py-3 font-black tracking-[0.08em] text-slate-900">誰</th>
                <th className="px-4 py-3 font-black tracking-[0.08em] text-slate-900">做什麼</th>
                <th className="px-4 py-3 font-black tracking-[0.08em] text-slate-900">時間表</th>
                <th className="px-4 py-3 font-black tracking-[0.08em] text-slate-900">下次執行</th>
                <th className="px-4 py-3 font-black tracking-[0.08em] text-slate-900">狀態</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-slate-200 align-top last:border-b-0">
                  <td className="px-4 py-3 font-black text-slate-900">{row.who}</td>
                  <td className="px-4 py-3 text-slate-700">
                    <p>{row.what}</p>
                    {row.note ? <p className="mt-1 text-xs text-slate-500">{row.note}</p> : null}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{row.schedule}</td>
                  <td className="px-4 py-3 text-slate-700">{row.nextRun}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex border-4 px-2 py-1 text-[11px] font-black uppercase tracking-[0.14em] ${timedJobStatusClassName(row.status)}`}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function buildTimedJobRows(
  cronOverviewState: Loadable<ControlCenterCronOverviewResponse>,
  healthzState: Loadable<ControlCenterHealthzPayload>
): TimedJobRow[] {
  const cronRows = cronOverviewState.data?.rows?.map((row) => ({
    id: row.jobId,
    channel: row.channel,
    who: row.owner || (row.channel === "heartbeat" ? "system-heartbeat" : "system-cron"),
    what: row.purpose || row.name,
    note: buildTimedJobNote(row.lastRunStatus, row.lastRunAt, row.lastError),
    schedule: row.schedule || "system interval",
    nextRun: row.nextRunAt ? formatDateTime(row.nextRunAt) : "-",
    status: normalizeTimedJobStatus(row.status),
  }));

  if (cronRows && cronRows.length > 0) {
    return cronRows.sort((left, right) => {
      if (left.channel !== right.channel) return left.channel === "cron" ? -1 : 1;
      if (left.nextRun === "-" && right.nextRun !== "-") return 1;
      if (left.nextRun !== "-" && right.nextRun === "-") return -1;
      return left.nextRun.localeCompare(right.nextRun);
    });
  }

  const healthz = healthzState.data;
  if (!healthz) return [];

  const rows: TimedJobRow[] = [
    {
      id: "runtime-cron-snapshot",
      channel: "cron",
      who: "system-cron",
      what: "刷新定時任務 snapshot 與全域可見性檢查",
      schedule: "system interval",
      nextRun: healthz.snapshot.generatedAt ? formatDateTime(healthz.snapshot.generatedAt) : "-",
      status: normalizeTimedJobStatus(healthz.snapshot.status),
    },
    {
      id: "runtime-heartbeat-monitor",
      channel: "heartbeat",
      who: "system-heartbeat",
      what: healthz.monitor.detail?.trim() || "執行心跳與 monitor 健康檢查",
      schedule: "system interval",
      nextRun: healthz.generatedAt ? formatDateTime(healthz.generatedAt) : "-",
      status: normalizeTimedJobStatus(healthz.monitor.status),
    },
  ];

  return rows.sort((left, right) => {
    if (left.channel !== right.channel) return left.channel === "cron" ? -1 : 1;
    if (left.nextRun === "-" && right.nextRun !== "-") return 1;
    if (left.nextRun !== "-" && right.nextRun === "-") return -1;
    return left.nextRun.localeCompare(right.nextRun);
  });
}

function normalizeTimedJobStatus(status?: string) {
  if (status === "ok") return "scheduled";
  if (status === "warn") return "due";
  if (status === "stale" || status === "missing") return "late";
  return status || "unknown";
}

function timedJobStatusClassName(status: string) {
  if (status === "scheduled") return "border-emerald-700 bg-emerald-100 text-emerald-900";
  if (status === "due") return "border-amber-700 bg-amber-100 text-amber-900";
  if (status === "late") return "border-coral bg-red-100 text-red-900";
  return "border-slate-500 bg-slate-100 text-slate-800";
}

function buildTimedJobNote(lastRunStatus?: string, lastRunAt?: string, lastError?: string) {
  if (!lastRunStatus && !lastRunAt && !lastError) return undefined;
  const parts: string[] = [];
  if (lastRunStatus) parts.push(`上次結果：${lastRunStatus}`);
  if (lastRunAt) parts.push(`上次執行：${formatDateTime(lastRunAt)}`);
  if (lastError) parts.push(`錯誤：${truncateTimedJobText(lastError, 140)}`);
  return parts.join(" · ");
}

function truncateTimedJobText(value: string, maxLength: number) {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1))}…`;
}

function resolveFileFacetOptions(files: ControlCenterFilesResponse) {
  const seen = new Set<string>();
  const options = [...(files.facetOptions ?? [])]
    .map((option) => ({
      key: normalizeFileFacetKey(option.key),
      label: option.label,
    }))
    .filter((option) => option.key.length > 0 && option.label.trim().length > 0)
    .filter((option) => {
      if (seen.has(option.key)) return false;
      seen.add(option.key);
      return true;
    });

  for (const file of files.files) {
    const key = normalizeFileFacetKey(file.facetKey);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    options.push({
      key,
      label: file.facetLabel?.trim() || humanizeFacetValue(key),
    });
  }

  return options.sort((a, b) => {
    if (a.key === "main") return -1;
    if (b.key === "main") return 1;
    return a.label.localeCompare(b.label, "zh-Hant");
  });
}

function resolveFileCategories(files: ControlCenterFilesResponse["files"], facetKey: string) {
  return [...new Set(
    files
      .filter((file) => normalizeFileFacetKey(file.facetKey) === facetKey)
      .map((file) => file.category?.trim())
      .filter((value): value is string => Boolean(value))
  )].sort((a, b) => a.localeCompare(b, "zh-Hant"));
}

function normalizeFileFacetKey(value?: string) {
  return value?.trim().toLowerCase() || "main";
}

function humanizeFacetValue(value: string, options?: Array<{ key: string; label: string }>) {
  const matched = options?.find((option) => option.key === value);
  if (matched) return matched.label;
  if (value === "main") return "Main";
  return value;
}

function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function formatFileSize(value?: number) {
  if (!value || !Number.isFinite(value) || value <= 0) return "size unknown";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function createInitialSectionState(section: ControlCenterSectionKey): SectionState {
  const state: SectionState = {
    healthz: idleLoadable(),
    cronOverview: idleLoadable(),
    usage: idleLoadable(),
    sessions: idleLoadable(),
    staffSummary: idleLoadable(),
    tasks: idleLoadable(),
    hall: idleLoadable(),
    workspaceFiles: idleLoadable(),
    memoryFiles: idleLoadable(),
    diagnostics: idleLoadable()
  };

  for (const key of sectionResourceKeys(section)) {
    state[key] = loadingLoadable();
  }

  return state;
}

function sectionResourceKeys(section: ControlCenterSectionKey): Array<keyof SectionState> {
  if (section === "overview") {
    return ["healthz", "cronOverview", "usage", "hall", "tasks", "sessions"];
  }
  if (section === "usage") return ["usage"];
  if (section === "staff") return ["staffSummary"];
  if (section === "collaboration" || section === "hall") return ["hall"];
  if (section === "tasks") return ["tasks"];
  if (section === "docs") return ["workspaceFiles"];
  if (section === "memory") return ["memoryFiles"];
  if (section === "settings") return ["healthz", "diagnostics"];
  return [];
}

function shouldShowLoadingBanner(section: ControlCenterSectionKey, state: SectionState) {
  const resources = sectionResourceKeys(section);
  if (resources.length === 0) return false;
  return resources.every((key) => state[key].status === "loading");
}

function idleLoadable<T>(): Loadable<T> {
  return { status: "idle" };
}

function loadingLoadable<T>(): Loadable<T> {
  return { status: "loading" };
}

function readyLoadable<T>(data: T): Loadable<T> {
  return { status: "ready", data };
}

function errorLoadable<T>(error: string): Loadable<T> {
  return { status: "error", error };
}

async function loadResource<T>(loader: () => Promise<T>, fallbackMessage: string) {
  try {
    return readyLoadable(await loader());
  } catch (error) {
    return errorLoadable<T>(normalizeErrorMessage(error, fallbackMessage));
  }
}

function fromSettledResult<T>(result: PromiseSettledResult<T>, fallbackMessage: string) {
  if (result.status === "fulfilled") {
    return readyLoadable(result.value);
  }

  return errorLoadable<T>(normalizeErrorMessage(result.reason, fallbackMessage));
}

function normalizeErrorMessage(error: unknown, fallbackMessage: string) {
  return error instanceof Error ? error.message : fallbackMessage;
}

function describeLoadable<T>(loadable: Loadable<T>, readyText: string) {
  if (loadable.status === "error") {
    return loadable.error ?? "資料同步失敗";
  }
  if (loadable.status === "loading") {
    return "正在同步最新資料...";
  }
  return readyText;
}

function readableLoadStatus(status: LoadStatus) {
  if (status === "loading") return "loading";
  if (status === "error") return "degraded";
  if (status === "ready") return "ready";
  return "idle";
}

function readSessionItems(sessions?: ControlCenterSessionsResponse) {
  if (!sessions) return [];
  const raw = (sessions as { sessions?: unknown }).sessions;
  return Array.isArray(raw) ? raw : [];
}

function readSessionCount(sessions?: ControlCenterSessionsResponse) {
  if (!sessions) return 0;
  return typeof sessions.count === "number" && Number.isFinite(sessions.count)
    ? sessions.count
    : readSessionItems(sessions).length;
}

function renderLoadablePanel<T>(
  loadable: Loadable<T>,
  options: {
    loadingText: string;
    emptyText: string;
    render: (data: T) => JSX.Element;
  }
) {
  if (loadable.status === "error") {
    return <ErrorHint text={loadable.error ?? options.emptyText} />;
  }
  if (loadable.status === "ready" && loadable.data) {
    return options.render(loadable.data);
  }
  if (loadable.status === "loading") {
    return <EmptyHint text={options.loadingText} />;
  }
  return <EmptyHint text={options.emptyText} />;
}

function StatBlock({
  label,
  value,
  detail,
  tone
}: {
  label: string;
  value: string;
  detail: string;
  tone: string;
}) {
  return (
    <article className={`border-4 border-ink p-4 ${tone}`}>
      <p className="text-[11px] uppercase tracking-[0.22em]">{label}</p>
      <p className="mt-3 text-3xl font-black">{value}</p>
      <p className="mt-2 text-sm">{detail}</p>
    </article>
  );
}

function QuickLink({ href, title, detail }: { href: string; title: string; detail: string }) {
  return (
    <Link href={href} className="pixel-button border-4 border-ink bg-white p-4 text-left">
      <h3 className="text-sm font-black tracking-[0.08em] text-ink">{title}</h3>
      <p className="mt-2 text-sm text-slate-600">{detail}</p>
    </Link>
  );
}

function DetailTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="border-4 border-ink bg-white p-4">
      <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-3 text-lg font-black tracking-[0.08em] text-ink">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p>
    </article>
  );
}

function DecisionHint({ title, detail }: { title: string; detail: string }) {
  return (
    <article className="border-4 border-ink bg-white p-4">
      <h3 className="text-sm font-black tracking-[0.08em] text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-7 text-slate-700">{detail}</p>
    </article>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
      {text}
    </div>
  );
}

function ErrorHint({ text }: { text: string }) {
  return <div className="border-4 border-coral bg-coral/10 p-4 text-sm text-coral">{text}</div>;
}
