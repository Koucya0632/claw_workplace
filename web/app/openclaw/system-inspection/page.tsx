"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { WorkflowEventTimeline } from "@/components/workflow-event-timeline";
import { WorkflowReportPanel } from "@/components/workflow-report-panel";
import { WorkflowRunList } from "@/components/workflow-run-list";
import { WorkflowStageBoard } from "@/components/workflow-stage-board";
import { summarizeWorkflowRuntimeIssue } from "@/lib/workflow-payloads";
import {
  createSystemInspectionWorkflow,
  fetchOpenClawInstances,
  fetchOpenClawSystemInspectionConfig,
  fetchWorkflowRun,
  fetchWorkflowRuns,
  updateOpenClawSystemInspectionConfig
} from "@/lib/api";
import type { OpenClawInstanceResponse, OpenClawSystemInspectionConfigResponse, WorkflowRunResponse } from "@/lib/types";

const DEFAULT_CONFIG: OpenClawSystemInspectionConfigResponse = {
  instance_id: "",
  enabled: false,
  schedule_timezone: "Asia/Tokyo",
  schedule_time: "09:30",
  delivery_channel: "telegram",
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
  updated_at: new Date(0).toISOString()
};

const INSPECTION_ROLES = [
  { name: "Controller", tagline: "主控秘書", status: "running", quote: "我會收集快照、安排巡檢、整合版本與日誌風險，並在必要時升級人工處理。" },
  { name: "System Inspection", tagline: "巡檢專職", status: "ready", quote: "我會分析官方版本變更、聚合高頻錯誤、排序風險，並給出具體修復方案。" },
  { name: "Delivery", tagline: "Telegram / Discord 摘要", status: "ready", quote: "巡檢完成後可把摘要推送到 Telegram 或 Discord，讓你快速知道是否升級與先修什麼。" }
];

function formatInspectionError(error: unknown, fallback: string) {
  if (!(error instanceof Error)) return fallback;
  return summarizeWorkflowRuntimeIssue(error.message, "System Inspection agent") ?? error.message;
}

export default function OpenClawSystemInspectionPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [config, setConfig] = useState<OpenClawSystemInspectionConfigResponse>(DEFAULT_CONFIG);
  const [runs, setRuns] = useState<WorkflowRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("你可以手動執行一次巡檢；固定時間的自動巡檢由 OpenClaw cron 觸發。");
  const [isPending, startTransition] = useTransition();
  const hasInstances = instances.length > 0;
  const canManageInspection = Boolean(selectedInstanceId);

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        setSelectedInstanceId((current) => current || instancePayload[0]?.id || "");
        if (instancePayload.length === 0) {
          setConfig(DEFAULT_CONFIG);
          setRuns([]);
          setActiveRun(null);
          setMessage("先建立 OpenClaw Instance，再設定 System Inspection。");
        }
      } catch (requestError) {
        setError(formatInspectionError(requestError, "無法載入 OpenClaw Instances"));
      }
    });
  }, [startTransition]);

  useEffect(() => {
    if (!selectedInstanceId) {
      setConfig(DEFAULT_CONFIG);
      setRuns([]);
      setActiveRun(null);
      return;
    }
    startTransition(async () => {
      try {
        const [configResult, runResult] = await Promise.allSettled([
          fetchOpenClawSystemInspectionConfig(selectedInstanceId),
          fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: "system_inspection", limit: 8 })
        ]);
        let nextError = "";

        if (configResult.status === "fulfilled") {
          setConfig(configResult.value);
        } else {
          setConfig({ ...DEFAULT_CONFIG, instance_id: selectedInstanceId });
          setMessage("此 Instance 尚未設定 System Inspection，已帶入預設值。");
        }
        if (runResult.status === "fulfilled") {
          setRuns(runResult.value);
          setActiveRun(runResult.value[0] ?? null);
        } else {
          setRuns([]);
          setActiveRun(null);
          nextError = formatInspectionError(runResult.reason, "無法載入系統巡檢資料");
        }
        setError(nextError);
      } catch (requestError) {
        setError(formatInspectionError(requestError, "無法載入系統巡檢資料"));
      }
    });
  }, [selectedInstanceId, startTransition]);

  useEffect(() => {
    if (!activeRun || !["pending", "running"].includes(activeRun.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const nextRun = await fetchWorkflowRun(activeRun.id);
        setActiveRun(nextRun);
        setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: "system_inspection", limit: 8 }));
      } catch (requestError) {
        setError(formatInspectionError(requestError, "輪詢巡檢 run 失敗"));
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [activeRun, selectedInstanceId]);

  async function handleSave() {
    if (!selectedInstanceId) return;
    setError("");
    setMessage("");
    startTransition(async () => {
      try {
        const saved = await updateOpenClawSystemInspectionConfig({
          instance_id: selectedInstanceId,
          enabled: config.enabled,
          schedule_timezone: config.schedule_timezone,
          schedule_time: config.schedule_time,
          delivery_channel: config.delivery_channel,
          telegram_target: config.telegram_target,
          discord_channel_id: config.discord_channel_id,
          version_check_enabled: config.version_check_enabled,
          log_review_enabled: config.log_review_enabled,
          log_review_window_hours: config.log_review_window_hours,
          log_review_limit: config.log_review_limit,
          official_release_url: config.official_release_url
        });
        setConfig(saved);
        setMessage("System Inspection 設定已更新。");
      } catch (requestError) {
        setError(formatInspectionError(requestError, "儲存巡檢設定失敗"));
      }
    });
  }

  async function handleRunNow() {
    if (!selectedInstanceId) return;
    setError("");
    setMessage("正在執行系統巡檢與風險評估...");
    startTransition(async () => {
      try {
        const run = await createSystemInspectionWorkflow({ instance_id: selectedInstanceId });
        setActiveRun(run);
        setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: "system_inspection", limit: 8 }));
      } catch (requestError) {
        setError(formatInspectionError(requestError, "手動執行巡檢失敗"));
      }
    });
  }

  return (
    <OpenClawPageShell
      title="System Inspection"
      description="System Inspection 是 OpenClaw Control Center 內的 Admin Tools 分區，持續檢查版本、workflow、plugin、operation logs 與 gateway 異常。"
      roles={INSPECTION_ROLES}
      sectionGroup="Admin Tools"
      sectionLabel="System Inspection"
    >
      <PixelCard title="巡檢設定" eyebrow="Config">
        <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
          <OpenClawInstancePicker
            instances={instances}
            value={selectedInstanceId}
            onChange={setSelectedInstanceId}
            disabled={!hasInstances || isPending}
          />
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm leading-7 text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message}
          </div>
        </div>
        <div className="mt-3 border-4 border-ink bg-sand px-4 py-3 text-sm font-medium text-slate-700">
          定時來源：OpenClaw cron。手動執行不受每日自動排程去重限制。
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[220px_220px_minmax(0,1fr)]">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">時區</span>
            <input value={config.schedule_timezone} onChange={(event) => setConfig((current) => ({ ...current, schedule_timezone: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">時間</span>
            <input value={config.schedule_time} onChange={(event) => setConfig((current) => ({ ...current, schedule_time: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">官方版本來源</span>
            <input value={config.official_release_url} onChange={(event) => setConfig((current) => ({ ...current, official_release_url: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_220px]">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">投遞通道</span>
            <select value={config.delivery_channel} onChange={(event) => setConfig((current) => ({ ...current, delivery_channel: event.target.value as "telegram" | "discord" }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none">
              <option value="telegram">Telegram</option>
              <option value="discord">Discord</option>
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">
              {config.delivery_channel === "discord" ? "Discord Channel ID" : "Telegram 目標"}
            </span>
            <input
              value={config.delivery_channel === "discord" ? config.discord_channel_id : config.telegram_target}
              onChange={(event) =>
                setConfig((current) => (
                  current.delivery_channel === "discord"
                    ? { ...current, discord_channel_id: event.target.value }
                    : { ...current, telegram_target: event.target.value }
                ))
              }
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">日誌視窗（小時）</span>
            <input type="number" min={1} max={168} value={config.log_review_window_hours} onChange={(event) => setConfig((current) => ({ ...current, log_review_window_hours: Number(event.target.value) || 24 }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">日誌數量上限</span>
            <input type="number" min={50} max={5000} value={config.log_review_limit} onChange={(event) => setConfig((current) => ({ ...current, log_review_limit: Number(event.target.value) || 500 }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
        </div>

        <div className="mt-4 grid gap-3 xl:grid-cols-3">
          <label className="flex items-center gap-3 border-4 border-ink bg-sand px-4 py-3">
            <input type="checkbox" checked={config.enabled} onChange={(event) => setConfig((current) => ({ ...current, enabled: event.target.checked }))} className="h-4 w-4" />
            <span className="text-sm font-black tracking-[0.08em]">啟用每日巡檢</span>
          </label>
          <label className="flex items-center gap-3 border-4 border-ink bg-sand px-4 py-3">
            <input type="checkbox" checked={config.version_check_enabled} onChange={(event) => setConfig((current) => ({ ...current, version_check_enabled: event.target.checked }))} className="h-4 w-4" />
            <span className="text-sm font-black tracking-[0.08em]">啟用版本檢查</span>
          </label>
          <label className="flex items-center gap-3 border-4 border-ink bg-sand px-4 py-3">
            <input type="checkbox" checked={config.log_review_enabled} onChange={(event) => setConfig((current) => ({ ...current, log_review_enabled: event.target.checked }))} className="h-4 w-4" />
            <span className="text-sm font-black tracking-[0.08em]">啟用日誌巡檢</span>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" onClick={handleSave} disabled={isPending || !canManageInspection} className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60">
            {isPending ? "儲存中..." : "儲存設定"}
          </button>
          <button type="button" onClick={handleRunNow} disabled={isPending || !canManageInspection} className="pixel-button bg-ink px-4 py-3 text-sm font-black tracking-[0.08em] text-sand disabled:opacity-60">
            {isPending ? "執行中..." : "手動執行巡檢"}
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
