"use client";

import { Suspense, useEffect, useState, useTransition } from "react";
import { useSearchParams } from "next/navigation";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { WorkflowEventTimeline } from "@/components/workflow-event-timeline";
import { WorkflowReportPanel } from "@/components/workflow-report-panel";
import { WorkflowRunList } from "@/components/workflow-run-list";
import { WorkflowStageBoard } from "@/components/workflow-stage-board";
import {
  createDevelopmentExecutionWorkflow,
  fetchOpenClawDevelopmentConfig,
  fetchOpenClawInstances,
  fetchWorkflowRun,
  fetchWorkflowRuns,
  updateOpenClawDevelopmentConfig
} from "@/lib/api";
import type {
  OpenClawDevelopmentConfigResponse,
  OpenClawInstanceResponse,
  WorkflowDevelopmentExecutionCreateRequest,
  WorkflowRunResponse
} from "@/lib/types";

const DEVELOPMENT_ROLES = [
  {
    name: "Main Agent",
    tagline: "任務 Intake / 最終接收",
    status: "running",
    quote: "我會接需求、建立工程 workflow，並在 handoff 階段接收全端工程師的結構化報告。"
  },
  {
    name: "Fullstack Engineer",
    tagline: "唯一執行入口",
    status: "ready",
    quote: "我會依序完成問題定義、需求分析、方案設計、技術選型、排期、開發、測試與優化。"
  },
  {
    name: "Traceable Workflow",
    tagline: "可追蹤 / 可回看",
    status: "ready",
    quote: "所有工程階段都會保留 stage board、timeline 與最終報告，方便回看與後續迭代。"
  }
];

const DEFAULT_FORM: WorkflowDevelopmentExecutionCreateRequest = {
  instance_id: "",
  task_name: "",
  problem_background: "",
  goal: "",
  constraints: [],
  success_criteria: [],
  context: "",
  attachments: [],
  references: []
};

const DEFAULT_DEVELOPMENT_CONFIG: OpenClawDevelopmentConfigResponse = {
  instance_id: "",
  enabled: false,
  delivery_channel: "discord",
  discord_channel_id: "",
  last_run_id: null,
  last_delivery_status: null,
  last_delivery_error: null,
  config_source: "default",
  effective_delivery_source: "none",
  effective_discord_channel_id: null,
  effective_delivery_reason: "未找到 Development 專屬設定，且 runtime route 未配置 fullstack-engineer-agent 的 Discord channel。",
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString()
};

function parseLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function describeDevelopmentDeliveryConfig(config: OpenClawDevelopmentConfigResponse) {
  if (config.config_source === "stored" && config.enabled && config.discord_channel_id.trim()) {
    return `目前使用 Development 專屬 Discord 設定（${config.discord_channel_id.trim()}）。`;
  }
  if (config.effective_delivery_source === "runtime_route" && config.effective_discord_channel_id) {
    return `此 Instance 尚未設定 Development Discord 匯報，將回退使用 Discord #develop route（${config.effective_discord_channel_id}）。`;
  }
  return config.effective_delivery_reason ?? "目前未設定 Development Discord 匯報，完成後會顯示 skipped。";
}

function OpenClawDevelopmentPageContent() {
  const searchParams = useSearchParams();
  const linkedInstanceId = searchParams.get("instanceId")?.trim() ?? "";
  const linkedRunId = searchParams.get("runId")?.trim() ?? "";
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [deliveryConfig, setDeliveryConfig] = useState<OpenClawDevelopmentConfigResponse>(DEFAULT_DEVELOPMENT_CONFIG);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [constraintsText, setConstraintsText] = useState("");
  const [successCriteriaText, setSuccessCriteriaText] = useState("");
  const [attachmentsText, setAttachmentsText] = useState("");
  const [referencesText, setReferencesText] = useState("");
  const [runs, setRuns] = useState<WorkflowRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("這裡會把工程任務交給 fullstack-engineer-agent，並強制保留分析、設計、測試與匯報鏈路。");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        const nextInstanceId =
          instancePayload.find((item) => item.id === linkedInstanceId)?.id ??
          instancePayload[0]?.id ??
          "";
        setSelectedInstanceId((current) => current || nextInstanceId);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw Instances");
      }
    });
  }, [linkedInstanceId, startTransition]);

  useEffect(() => {
    setForm((current) => ({ ...current, instance_id: selectedInstanceId }));
    if (!selectedInstanceId) return;
    startTransition(async () => {
      try {
        const [configPayload, runPayload] = await Promise.allSettled([
          fetchOpenClawDevelopmentConfig(selectedInstanceId),
          fetchWorkflowRuns({
            instanceId: selectedInstanceId,
            workflowType: "development_execution",
            limit: 8
          })
        ]);
        const shouldApplyDeepLink = Boolean(linkedRunId) && (!linkedInstanceId || linkedInstanceId === selectedInstanceId);
        let nextRuns = runPayload.status === "fulfilled" ? runPayload.value : [];
        let nextActiveRun = nextRuns[0] ?? null;
        let nextMessage = "";

        if (configPayload.status === "fulfilled" && configPayload.value) {
          setDeliveryConfig(configPayload.value);
          nextMessage = describeDevelopmentDeliveryConfig(configPayload.value);
        } else {
          const fallbackConfig = { ...DEFAULT_DEVELOPMENT_CONFIG, instance_id: selectedInstanceId };
          setDeliveryConfig(fallbackConfig);
          nextMessage = describeDevelopmentDeliveryConfig(fallbackConfig);
        }

        if (shouldApplyDeepLink) {
          const linkedRun = nextRuns.find((item) => item.id === linkedRunId);
          if (linkedRun) {
            nextActiveRun = linkedRun;
            nextMessage = "已定位到 System Inspection 自動交辦的工程流程。";
          } else {
            try {
              const fetchedRun = await fetchWorkflowRun(linkedRunId);
              if (fetchedRun.workflow_type === "development_execution" && fetchedRun.instance_id === selectedInstanceId) {
                nextActiveRun = fetchedRun;
                nextRuns = [fetchedRun, ...nextRuns.filter((item) => item.id !== fetchedRun.id)];
                nextMessage = "已定位到 System Inspection 自動交辦的工程流程。";
              } else {
                nextMessage = "找不到指定的 Development Workflow，已回到最新工程流程。";
              }
            } catch {
              nextMessage = "找不到指定的 Development Workflow，已回到最新工程流程。";
            }
          }
        }

        setRuns(nextRuns);
        setActiveRun(nextActiveRun);
        if (runPayload.status !== "fulfilled") {
          setError(runPayload.reason instanceof Error ? runPayload.reason.message : "無法載入 Development workflow");
        } else {
          setError("");
        }
        if (nextMessage) {
          setMessage(nextMessage);
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 Development workflow");
      }
    });
  }, [linkedInstanceId, linkedRunId, selectedInstanceId, startTransition]);

  useEffect(() => {
    if (!activeRun || !["pending", "running"].includes(activeRun.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const nextRun = await fetchWorkflowRun(activeRun.id);
        setActiveRun(nextRun);
        setRuns(
          await fetchWorkflowRuns({
            instanceId: selectedInstanceId,
            workflowType: "development_execution",
            limit: 8
          })
        );
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "輪詢工程 workflow 失敗");
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [activeRun, selectedInstanceId]);

  async function handleCreateRun() {
    if (!selectedInstanceId || !form.task_name.trim() || !form.problem_background.trim() || !form.goal.trim()) {
      setError("請至少填寫 Instance、任務名稱、問題背景與目標。");
      return;
    }
    setError("");
    setMessage("正在交由 fullstack-engineer-agent 建立標準化工程執行流程...");
    startTransition(async () => {
      try {
        const payload: WorkflowDevelopmentExecutionCreateRequest = {
          instance_id: selectedInstanceId,
          task_name: form.task_name.trim(),
          problem_background: form.problem_background.trim(),
          goal: form.goal.trim(),
          constraints: parseLines(constraintsText),
          success_criteria: parseLines(successCriteriaText),
          context: form.context.trim(),
          attachments: parseLines(attachmentsText),
          references: parseLines(referencesText)
        };
        const run = await createDevelopmentExecutionWorkflow(payload);
        setActiveRun(run);
        setRuns(
          await fetchWorkflowRuns({
            instanceId: selectedInstanceId,
            workflowType: "development_execution",
            limit: 8
          })
        );
        setMessage("工程任務已建立，現在會依序執行問題定義、設計、排期、開發、測試與匯報。");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立 Development workflow 失敗");
      }
    });
  }

  async function handleSaveDeliveryConfig() {
    if (!selectedInstanceId) return;
    setError("");
    setMessage("正在更新 Development Discord 匯報設定...");
    startTransition(async () => {
      try {
        const saved = await updateOpenClawDevelopmentConfig({
          instance_id: selectedInstanceId,
          enabled: deliveryConfig.enabled,
          delivery_channel: "discord",
          discord_channel_id: deliveryConfig.discord_channel_id,
        });
        setDeliveryConfig(saved);
        setMessage("Development Discord 匯報設定已更新。");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "儲存 Development Discord 設定失敗");
      }
    });
  }

  return (
    <OpenClawPageShell
      title="Development"
      description="Development 是 OpenClaw Control Center 內的 Admin Tools 分區，負責把工程任務交給 fullstack-engineer-agent，並保留完整執行鏈路。"
      roles={DEVELOPMENT_ROLES}
      sectionGroup="Admin Tools"
      sectionLabel="Development"
    >
      <PixelCard title="工程任務建立" eyebrow="Development Workflow">
        <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
          <OpenClawInstancePicker instances={instances} value={selectedInstanceId} onChange={setSelectedInstanceId} />
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm leading-7 text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message}
          </div>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_240px]">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Discord Channel ID</span>
            <input
              value={deliveryConfig.discord_channel_id}
              onChange={(event) => setDeliveryConfig((current) => ({ ...current, discord_channel_id: event.target.value }))}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
          </label>
          <label className="flex items-center gap-3 border-4 border-ink bg-sand px-4 py-3">
            <input
              type="checkbox"
              checked={deliveryConfig.enabled}
              onChange={(event) => setDeliveryConfig((current) => ({ ...current, enabled: event.target.checked }))}
              className="h-4 w-4"
            />
            <span className="text-sm font-black tracking-[0.08em]">啟用 Development Discord 匯報</span>
          </label>
        </div>

        <div className="mt-3 grid gap-3 xl:grid-cols-3">
          <div className="border-4 border-ink bg-sand px-4 py-3 text-sm leading-7 text-slate-700">
            最近投遞狀態：{deliveryConfig.last_delivery_status ?? "尚未投遞"}
          </div>
          <div className="border-4 border-ink bg-sand px-4 py-3 text-sm leading-7 text-slate-700">
            最近 Run：{deliveryConfig.last_run_id ?? "尚無紀錄"}
          </div>
          <div className="border-4 border-ink bg-sand px-4 py-3 text-sm leading-7 text-slate-700">
            最近錯誤：{deliveryConfig.last_delivery_error ?? "無"}
          </div>
        </div>

        <div className="mt-3 border-4 border-ink bg-white px-4 py-3 text-sm leading-7 text-slate-700">
          <p>有效來源：{deliveryConfig.effective_delivery_source}</p>
          {deliveryConfig.effective_discord_channel_id ? <p>有效目標：{deliveryConfig.effective_discord_channel_id}</p> : null}
          {deliveryConfig.effective_delivery_reason ? <p>說明：{deliveryConfig.effective_delivery_reason}</p> : null}
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">任務名稱</span>
            <input
              value={form.task_name}
              onChange={(event) => setForm((current) => ({ ...current, task_name: event.target.value }))}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">目標</span>
            <input
              value={form.goal}
              onChange={(event) => setForm((current) => ({ ...current, goal: event.target.value }))}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
          </label>
        </div>

        <div className="mt-4 grid gap-4">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">問題背景</span>
            <textarea
              value={form.problem_background}
              onChange={(event) => setForm((current) => ({ ...current, problem_background: event.target.value }))}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">上下文 / 補充說明</span>
            <textarea
              value={form.context}
              onChange={(event) => setForm((current) => ({ ...current, context: event.target.value }))}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">限制條件（每行一條）</span>
            <textarea
              value={constraintsText}
              onChange={(event) => setConstraintsText(event.target.value)}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">成功標準（每行一條）</span>
            <textarea
              value={successCriteriaText}
              onChange={(event) => setSuccessCriteriaText(event.target.value)}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">附件（每行一條）</span>
            <textarea
              value={attachmentsText}
              onChange={(event) => setAttachmentsText(event.target.value)}
              rows={4}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">參考資料（每行一條）</span>
            <textarea
              value={referencesText}
              onChange={(event) => setReferencesText(event.target.value)}
              rows={4}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleSaveDeliveryConfig}
            disabled={isPending || !selectedInstanceId}
            className="pixel-button bg-ink px-4 py-3 text-sm font-black tracking-[0.08em] text-sand disabled:opacity-60"
          >
            {isPending ? "儲存中..." : "儲存 Discord 設定"}
          </button>
          <button
            type="button"
            onClick={handleCreateRun}
            disabled={isPending || !selectedInstanceId}
            className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
          >
            {isPending ? "建立中..." : "建立工程任務"}
          </button>
        </div>
      </PixelCard>

      <WorkflowStageBoard run={activeRun} />

      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <WorkflowRunList runs={runs} activeRunId={activeRun?.id} onSelect={async (runId) => setActiveRun(await fetchWorkflowRun(runId))} />
        <WorkflowEventTimeline events={activeRun?.events ?? []} />
      </div>

      <WorkflowReportPanel run={activeRun} />
    </OpenClawPageShell>
  );
}

export default function OpenClawDevelopmentPage() {
  return (
    <Suspense fallback={null}>
      <OpenClawDevelopmentPageContent />
    </Suspense>
  );
}
