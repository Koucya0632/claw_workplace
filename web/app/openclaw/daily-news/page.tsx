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
  createNewsBriefWorkflow,
  fetchOpenClawDailyNewsConfig,
  fetchOpenClawInstances,
  fetchWorkflowRun,
  fetchWorkflowRuns,
  updateOpenClawDailyNewsConfig
} from "@/lib/api";
import type { OpenClawDailyNewsConfigResponse, OpenClawInstanceResponse, WorkflowRunResponse } from "@/lib/types";

const DEFAULT_CONFIG: OpenClawDailyNewsConfigResponse = {
  instance_id: "",
  enabled: false,
  brief_name: "Daily News Brief",
  topic: "",
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
  output_format: "summary",
  delivery_channel: "telegram",
  telegram_target: "",
  discord_channel_id: "",
  schedule_timezone: "Asia/Tokyo",
  schedule_time: "09:00",
  last_scheduled_date: null,
  last_run_id: null,
  last_delivery_status: null,
  last_delivery_error: null,
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString()
};

const DAILY_NEWS_ROLES = [
  { name: "Controller", tagline: "主控秘書", status: "running", quote: "我會接手每日新聞任務、追蹤排程與投遞狀態，必要時升級人工處理。" },
  { name: "Daily News Brief", tagline: "新聞專職", status: "ready", quote: "我會監控、去重、排序並生成高品質 Daily News Brief。" },
  { name: "Delivery", tagline: "Telegram / Discord 推送", status: "ready", quote: "簡報完成後會推送到你指定的 Telegram 或 Discord 目標，並保留完整鏈路供回看。" }
];

function formatDailyNewsError(error: unknown, fallback: string) {
  if (!(error instanceof Error)) return fallback;
  return summarizeWorkflowRuntimeIssue(error.message, "Daily News Brief agent") ?? error.message;
}

function toLines(value: string[]) {
  return value.join("\n");
}

function fromLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function OpenClawDailyNewsPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [config, setConfig] = useState<OpenClawDailyNewsConfigResponse>(DEFAULT_CONFIG);
  const [runs, setRuns] = useState<WorkflowRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("設定 Daily News Brief 條件後，可手動執行一次；自動排程則由 OpenClaw cron 每天觸發。");
  const [isPending, startTransition] = useTransition();
  const hasInstances = instances.length > 0;
  const canManageDailyNews = Boolean(selectedInstanceId);

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
          setMessage("先建立 OpenClaw Instance，再設定 Daily News Brief。");
        }
      } catch (requestError) {
        setError(formatDailyNewsError(requestError, "無法載入 OpenClaw Instances"));
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
          fetchOpenClawDailyNewsConfig(selectedInstanceId),
          fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: "news_brief", limit: 8 })
        ]);
        let nextError = "";
        if (configResult.status === "fulfilled") {
          setConfig(configResult.value);
        } else {
          setConfig({ ...DEFAULT_CONFIG, instance_id: selectedInstanceId });
          setMessage("此 Instance 尚未設定 Daily News Brief，已帶入空白預設值。");
        }
        if (runResult.status === "fulfilled") {
          setRuns(runResult.value);
          setActiveRun(runResult.value[0] ?? null);
        } else {
          setRuns([]);
          setActiveRun(null);
          nextError = formatDailyNewsError(runResult.reason, "無法載入 Daily News 資料");
        }
        setError(nextError);
      } catch (requestError) {
        setError(formatDailyNewsError(requestError, "無法載入 Daily News 資料"));
      }
    });
  }, [selectedInstanceId, startTransition]);

  useEffect(() => {
    if (!activeRun || !["pending", "running"].includes(activeRun.status)) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const nextRun = await fetchWorkflowRun(activeRun.id);
        setActiveRun(nextRun);
        setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: "news_brief", limit: 8 }));
      } catch (requestError) {
        setError(formatDailyNewsError(requestError, "輪詢 Daily News run 失敗"));
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [activeRun, selectedInstanceId]);

  function updateListField(key: keyof OpenClawDailyNewsConfigResponse, value: string) {
    setConfig((current) => ({ ...current, [key]: fromLines(value) }));
  }

  async function handleSave() {
    if (!selectedInstanceId) return;
    setError("");
    setMessage("");
    startTransition(async () => {
      try {
        const saved = await updateOpenClawDailyNewsConfig({
          instance_id: selectedInstanceId,
          enabled: config.enabled,
          brief_name: config.brief_name,
          topic: config.topic,
          keywords: config.keywords,
          industries: config.industries,
          regions: config.regions,
          people: config.people,
          companies: config.companies,
          source_domains: config.source_domains,
          source_urls: config.source_urls,
          must_include: config.must_include,
          must_exclude: config.must_exclude,
          focus_points: config.focus_points,
          output_format: config.output_format,
          delivery_channel: config.delivery_channel,
          telegram_target: config.telegram_target,
          discord_channel_id: config.discord_channel_id,
          schedule_timezone: config.schedule_timezone,
          schedule_time: config.schedule_time
        });
        setConfig(saved);
        setMessage("Daily News Brief 設定已更新。");
      } catch (requestError) {
        setError(formatDailyNewsError(requestError, "儲存 Daily News 設定失敗"));
      }
    });
  }

  async function handleRunNow() {
    if (!selectedInstanceId) return;
    setError("");
    setMessage("正在手動執行 Daily News Brief...");
    startTransition(async () => {
      try {
        const run = await createNewsBriefWorkflow({ instance_id: selectedInstanceId });
        setActiveRun(run);
        setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: "news_brief", limit: 8 }));
      } catch (requestError) {
        setError(formatDailyNewsError(requestError, "手動執行 Daily News Brief 失敗"));
      }
    });
  }

  return (
    <OpenClawPageShell
      title="Daily News Brief"
      description="Daily News Brief 是 OpenClaw Control Center 內的 Admin Tools 分區，集中設定每日新聞監控條件、投遞通道與最近一次簡報結果。"
      roles={DAILY_NEWS_ROLES}
      sectionGroup="Admin Tools"
      sectionLabel="Daily News Brief"
    >
      <PixelCard title="Daily News 設定" eyebrow="Config">
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

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_220px]">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Brief 名稱</span>
            <input value={config.brief_name} onChange={(event) => setConfig((current) => ({ ...current, brief_name: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">時區</span>
            <input value={config.schedule_timezone} onChange={(event) => setConfig((current) => ({ ...current, schedule_timezone: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">時間</span>
            <input value={config.schedule_time} onChange={(event) => setConfig((current) => ({ ...current, schedule_time: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
          </label>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">新聞主題</span>
            <textarea value={config.topic} onChange={(event) => setConfig((current) => ({ ...current, topic: event.target.value }))} rows={3} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
          </label>
          <div className="space-y-3">
            <label className="flex items-center gap-3 border-4 border-ink bg-sand px-4 py-3">
              <input type="checkbox" checked={config.enabled} onChange={(event) => setConfig((current) => ({ ...current, enabled: event.target.checked }))} className="h-4 w-4" />
              <span className="text-sm font-black tracking-[0.08em]">啟用每日新聞簡報</span>
            </label>
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
              <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">輸出格式</span>
              <select value={config.output_format} onChange={(event) => setConfig((current) => ({ ...current, output_format: event.target.value as OpenClawDailyNewsConfigResponse["output_format"] }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none">
                <option value="summary">摘要</option>
                <option value="bullets">條列</option>
                <option value="table">表格</option>
                <option value="comparison">比較</option>
              </select>
            </label>
          </div>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          <NewsTextArea label="關鍵字" value={toLines(config.keywords)} onChange={(value) => updateListField("keywords", value)} />
          <NewsTextArea label="產業" value={toLines(config.industries)} onChange={(value) => updateListField("industries", value)} />
          <NewsTextArea label="地區" value={toLines(config.regions)} onChange={(value) => updateListField("regions", value)} />
          <NewsTextArea label="人物" value={toLines(config.people)} onChange={(value) => updateListField("people", value)} />
          <NewsTextArea label="公司" value={toLines(config.companies)} onChange={(value) => updateListField("companies", value)} />
          <NewsTextArea label="來源網域" value={toLines(config.source_domains)} onChange={(value) => updateListField("source_domains", value)} />
          <NewsTextArea label="來源網址" value={toLines(config.source_urls)} onChange={(value) => updateListField("source_urls", value)} />
          <NewsTextArea label="必須包含" value={toLines(config.must_include)} onChange={(value) => updateListField("must_include", value)} />
          <NewsTextArea label="必須排除" value={toLines(config.must_exclude)} onChange={(value) => updateListField("must_exclude", value)} />
        </div>

        <div className="mt-4">
          <NewsTextArea label="需要重點整理的資訊" value={toLines(config.focus_points)} onChange={(value) => updateListField("focus_points", value)} rows={4} />
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" onClick={handleSave} disabled={!canManageDailyNews || isPending} className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60">
            {isPending ? "儲存中..." : "儲存設定"}
          </button>
          <button type="button" onClick={handleRunNow} disabled={isPending || !canManageDailyNews} className="pixel-button bg-ink px-4 py-3 text-sm font-black tracking-[0.08em] text-sand disabled:opacity-60">
            {isPending ? "執行中..." : "手動執行今日簡報"}
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

function NewsTextArea({
  label,
  value,
  onChange,
  rows = 4
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
}) {
  return (
    <label className="space-y-2">
      <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={rows} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
    </label>
  );
}
